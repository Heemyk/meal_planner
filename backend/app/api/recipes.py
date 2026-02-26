import io
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

from fastapi import APIRouter, File, Form, UploadFile
from sqlmodel import select

from app.config import settings
from app.logging import get_logger
from app.utils.timing import time_span
from app.schemas.recipe import RecipeUploadResponse
from app.services.graph.graph_queries import link_recipe_ingredient, upsert_ingredient, upsert_recipe
from app.services.llm.dspy_client import configure_dspy
from app.services.llm.ingredient_matcher import match_ingredient
from app.services.llm.unit_normalizer import normalize_units
from app.services.allergens import infer_allergens_from_ingredients
from app.services.parsing.recipe_parser import infer_meal_type, parse_recipe_text
from app.storage.db import get_session
from app.storage.models import Ingredient, Recipe, RecipeIngredient
from app.storage.repositories import create_recipe, create_recipe_ingredients, get_ingredients, get_or_create_ingredient
from app.workers.tasks import fetch_skus_for_ingredient

router = APIRouter()
logger = get_logger(__name__)


def _match_and_normalize(ingredient_text: str, existing_names: list[str]) -> Tuple[dict, dict]:
    match = match_ingredient(ingredient_text, existing_names)
    canonical_name = (match.get("canonical_name") or "").strip().lower() or "unknown"
    normalized = normalize_units(ingredient_text, canonical_name=canonical_name)
    return match, normalized


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
            logger.warning("recipes: bad zip file, skipping: %s", filename)
            return []
    return [(content, filename)]


@router.post("/recipes/upload/sync", response_model=RecipeUploadResponse)
async def upload_recipes(
    files: list[UploadFile] = File(...),
    postal_code: str | None = Form(default=None),
) -> RecipeUploadResponse:
    with time_span("recipes.upload.total", files=len(files)):
        configure_dspy()
        effective_postal = (postal_code or "").strip() or settings.default_postal_code
        recipes_created = 0
        ingredients_created = 0
        sku_jobs = 0
        logger.info("recipes.upload.start files=%s postal=%s", len(files), effective_postal)

        with get_session() as session:
            existing = get_ingredients(session)
            existing_names = [ing.canonical_name for ing in existing]
            existing_lookup = {ing.canonical_name: ing for ing in existing}

            for upload in files:
                content = await upload.read()
                fn = upload.filename or "upload"
                for file_content, source_name in _expand_files(content, fn):
                    parsed_recipes = parse_recipe_text(file_content.decode("utf-8"))
                    for parsed in parsed_recipes:
                        meal_type = infer_meal_type(parsed.name, parsed.instructions)
                        recipe = create_recipe(
                            session,
                            Recipe(
                                name=parsed.name,
                                servings=parsed.servings,
                                instructions=parsed.instructions,
                                source_file=source_name,
                                meal_type=meal_type,
                            ),
                        )
                        recipes_created += 1
                        upsert_recipe(recipe_id=recipe.id, name=recipe.name, servings=recipe.servings)

                        recipe_ingredients: list[RecipeIngredient] = []
                        recipe_ingredient_names: list[str] = []
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
                        results: dict[str, Tuple[dict, dict]] = {}
                        with time_span("ingredient.batch.parallel", recipe=parsed.name, workers=max_workers, count=len(parsed.ingredients)):
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
                            canonical_name = match["canonical_name"].strip().lower()
                            if not canonical_name:
                                canonical_name = "unknown"
                            ingredient = existing_lookup.get(canonical_name)
                            if not ingredient:
                                base_unit = normalized.get("base_unit") or "count"
                                ingredient = get_or_create_ingredient(
                                    session,
                                    name=canonical_name,
                                    canonical_name=canonical_name,
                                    base_unit=base_unit,
                                    base_unit_qty=normalized.get("base_unit_qty", 1.0),
                                )
                                existing_lookup[canonical_name] = ingredient
                                existing_names.append(canonical_name)
                                ingredients_created += 1
                                logger.info(
                                    "ingredient.created id=%s name=%s base_unit=%s",
                                    ingredient.id,
                                    ingredient.canonical_name,
                                    ingredient.base_unit,
                                )
                                fetch_skus_for_ingredient.delay(
                                    ingredient.id, canonical_name, effective_postal
                                )
                                sku_jobs += 1

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
                                recipe_id=recipe.id, ingredient_id=ingredient.id, qty=normalized["normalized_qty"]
                            )

                        create_recipe_ingredients(session, recipe_ingredients)

                        # Set allergens from ingredients (meal initialisation)
                        recipe.allergens = infer_allergens_from_ingredients(recipe_ingredient_names)
                        session.add(recipe)
                        session.commit()

            total_recipes = len(list(session.exec(select(Recipe))))
            total_ingredients = len(list(session.exec(select(Ingredient))))
            total_recipe_links = len(list(session.exec(select(RecipeIngredient))))
            logger.info(
                "db.state postgres: recipes=%s ingredients=%s recipe_links=%s | neo4j: mirrored for synergy",
                total_recipes,
                total_ingredients,
                total_recipe_links,
            )

        logger.info(
            "recipes.upload.end recipes=%s ingredients=%s sku_jobs=%s",
            recipes_created,
            ingredients_created,
            sku_jobs,
        )
        return RecipeUploadResponse(
            recipes_created=recipes_created,
            ingredients_created=ingredients_created,
            sku_jobs_enqueued=sku_jobs,
        )
