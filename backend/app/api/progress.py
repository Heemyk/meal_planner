"""SSE streaming for upload and SKU progress."""

import asyncio
import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from app.logging import get_logger
from app.services.graph.graph_queries import link_recipe_ingredient, upsert_ingredient, upsert_recipe
from app.services.llm.dspy_client import configure_dspy
from app.services.llm.ingredient_matcher import match_ingredient
from app.services.llm.unit_normalizer import normalize_units
from app.services.allergens import infer_allergens_from_ingredients
from app.services.parsing.recipe_parser import infer_meal_type, parse_recipe_text
from app.storage.db import get_session
from app.storage.models import Ingredient, Recipe, RecipeIngredient, SKU
from app.storage.repositories import create_recipe, create_recipe_ingredients, get_ingredients, get_or_create_ingredient
from app.workers.tasks import fetch_skus_for_ingredient
from sqlmodel import select

router = APIRouter()
logger = get_logger(__name__)

SKU_POLL_INTERVAL = 1.5
SKU_POLL_TIMEOUT = 300  # 5 min


def _match_and_normalize(ingredient_text: str, existing_names: list[str]):
    from app.services.llm.ingredient_matcher import match_ingredient
    from app.services.llm.unit_normalizer import normalize_units
    match = match_ingredient(ingredient_text, existing_names)
    normalized = normalize_units(ingredient_text)
    return match, normalized


def _get_sku_progress() -> dict:
    with get_session() as session:
        ingredients = list(session.exec(select(Ingredient)))
        skus = list(session.exec(select(SKU)))
        now = datetime.utcnow()
        ingredient_ids_with_skus = {s.ingredient_id for s in skus if s.expires_at > now}
        with_skus_count = sum(1 for i in ingredients if i.id in ingredient_ids_with_skus)
    return {
        "ingredients_total": len(ingredients),
        "ingredients_with_skus": with_skus_count,
        "skus_total": len([s for s in skus if s.expires_at > now]),
    }


def _emit_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _expand_files(content: bytes, filename: str) -> list[tuple[bytes, str]]:
    """Expand upload into list of (content, filename). Extracts .zip files."""
    if filename.lower().endswith(".zip"):
        out = []
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                for name in zf.namelist():
                    if name.endswith("/") or not name.lower().endswith(".txt"):
                        continue
                    data = zf.read(name)
                    base = name.split("/")[-1]
                    out.append((data, base or name))
            return out
        except zipfile.BadZipFile:
            logger.warning("progress: bad zip file, skipping: %s", filename)
            return []
    return [(content, filename)]


@router.post("/recipes/upload/stream")
async def upload_recipes_stream(
    files: list[UploadFile] = File(...),
    postal_code: str | None = Form(default=None),
):
    """
    Upload recipes and stream progress via SSE.
    Events: ingredient_added, upload_complete, sku_progress, stream_complete
    postal_code: Optional. Used for Instacart price lookup. If omitted, uses server default.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from app.config import settings

    effective_postal = (postal_code or "").strip() or settings.default_postal_code

    # Read files in request scope so UploadFiles stay valid. Expand .zip into .txt entries.
    file_contents = []
    for upload in files:
        content = await upload.read()
        fn = upload.filename or "upload"
        for c, name in _expand_files(content, fn):
            file_contents.append((c, name))

    async def generate():
        # Process inside generator so we can yield as we go
        from concurrent.futures import ThreadPoolExecutor, as_completed

        configure_dspy()
        recipes_created = 0
        ingredients_created = 0
        sku_jobs = 0

        with get_session() as session:
            existing = get_ingredients(session)
            existing_names = [ing.canonical_name for ing in existing]
            existing_lookup = {ing.canonical_name: ing for ing in existing}

            for content, source_filename in file_contents:
                parsed_recipes = parse_recipe_text(content.decode("utf-8"))

                for parsed in parsed_recipes:
                    meal_type = infer_meal_type(parsed.name, parsed.instructions)
                    recipe = create_recipe(
                        session,
                        Recipe(
                            name=parsed.name,
                            servings=parsed.servings,
                            instructions=parsed.instructions,
                            source_file=source_filename,
                            meal_type=meal_type,
                        ),
                    )
                    recipes_created += 1
                    upsert_recipe(recipe_id=recipe.id, name=recipe.name, servings=recipe.servings)

                    recipe_ingredients = []
                    recipe_ingredient_names = []
                    current_existing = list(existing_names)
                    # ThreadPoolExecutor: threads (true parallelism for I/O-bound LLM calls), not asyncio
                    max_workers = min(
                        settings.ingredient_batch_max_workers,
                        max(1, len(parsed.ingredients)),
                    )
                    logger.info(
                        "ingredient.batch.start recipe=%s workers=%s count=%s",
                        parsed.name,
                        max_workers,
                        len(parsed.ingredients),
                    )
                    results = {}
                    with ThreadPoolExecutor(max_workers=max_workers) as ex:
                        futures = {
                            ex.submit(_match_and_normalize, it, current_existing): it
                            for it in parsed.ingredients
                        }
                        for fut in as_completed(futures):
                            it = futures[fut]
                            try:
                                results[it] = fut.result()
                            except Exception as e:
                                logger.warning("ingredient.parse_failed text=%s error=%s", it, e)

                    for ingredient_text in parsed.ingredients:
                        if ingredient_text not in results:
                            continue
                        match, normalized = results[ingredient_text]
                        canonical_name = (match["canonical_name"] or "").strip().lower() or "unknown"
                        ingredient = existing_lookup.get(canonical_name)
                        if not ingredient:
                            ingredient = get_or_create_ingredient(
                                session,
                                name=canonical_name,
                                canonical_name=canonical_name,
                                base_unit=normalized["base_unit"],
                                base_unit_qty=normalized["base_unit_qty"],
                            )
                            existing_lookup[canonical_name] = ingredient
                            existing_names.append(canonical_name)
                            ingredients_created += 1
                            fetch_skus_for_ingredient.delay(
                                ingredient.id, canonical_name, effective_postal
                            )
                            sku_jobs += 1
                            # Yield immediately so client sees progress
                            yield _emit_sse("ingredient_added", {
                                "ingredients_added": ingredients_created,
                                "ingredients_total": ingredients_created,
                                "name": canonical_name,
                            })

                        recipe_ingredients.append(
                            RecipeIngredient(
                                recipe_id=recipe.id,
                                ingredient_id=ingredient.id,
                                quantity=normalized["normalized_qty"],
                                unit=normalized["normalized_unit"],
                                original_text=ingredient_text,
                            )
                        )
                        recipe_ingredient_names.append(canonical_name)
                        upsert_ingredient(ingredient_id=ingredient.id, name=ingredient.canonical_name)
                        link_recipe_ingredient(
                            recipe_id=recipe.id,
                            ingredient_id=ingredient.id,
                            qty=normalized["normalized_qty"],
                        )

                    create_recipe_ingredients(session, recipe_ingredients)

                    # Set allergens from ingredients (meal initialisation)
                    recipe.allergens = infer_allergens_from_ingredients(recipe_ingredient_names)
                    session.add(recipe)
                    session.commit()

        yield _emit_sse("upload_complete", {
            "recipes_created": recipes_created,
            "ingredients_created": ingredients_created,
            "sku_jobs_enqueued": sku_jobs,
        })
        elapsed = 0
        last_progress = {}
        while elapsed < SKU_POLL_TIMEOUT:
            await asyncio.sleep(SKU_POLL_INTERVAL)
            elapsed += SKU_POLL_INTERVAL
            prog = _get_sku_progress()
            if prog != last_progress:
                last_progress = prog
                yield _emit_sse("sku_progress", prog)
            if prog["ingredients_total"] == 0:
                break
            if prog["ingredients_with_skus"] >= prog["ingredients_total"]:
                break
        yield _emit_sse("stream_complete", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
