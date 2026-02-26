"""SSE streaming for upload and SKU progress.

Clean architecture:
- POST /recipes/upload: Accepts files, returns 202 + job_id immediately after reading body.
  Spawns background task. Ingredient counts come from fast structural parse (no LLM).
- GET /recipes/upload/stream/{job_id}: SSE stream. Yields events as they happen (per ingredient).
"""

import asyncio
import io
import json
import queue
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from app.logging import get_logger
from app.services.graph.graph_queries import link_recipe_ingredient, upsert_ingredient, upsert_recipe
from app.services.llm.dspy_client import configure_dspy
from app.services.parsing.recipe_parser import count_ingredients_in_text, infer_meal_type, parse_recipe_text
from app.services.allergens import infer_allergens_from_ingredients
from app.storage.db import get_session
from app.storage.models import Ingredient, Recipe, RecipeIngredient, SKU
from app.storage.repositories import (
    create_recipe,
    create_recipe_ingredients,
    get_ingredients,
    get_or_create_ingredient,
)
from app.workers.tasks import fetch_skus_for_ingredient
from sqlmodel import select

router = APIRouter()
logger = get_logger(__name__)

SKU_POLL_INTERVAL = 1.5
SKU_POLL_TIMEOUT = 300

# job_id -> thread-safe queue of (event, data) for SSE consumers
job_event_queues: dict[str, queue.Queue] = {}
# job_id -> latest progress dict (for GET /progress)
job_progress_store: dict[str, dict] = {}


def _emit_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _expand_files(content: bytes, filename: str) -> list[tuple[bytes, str]]:
    if filename.lower().endswith(".zip"):
        out = []
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                for name in zf.namelist():
                    if name.endswith("/") or not name.lower().endswith(".txt"):
                        continue
                    out.append((zf.read(name), name.split("/")[-1] or name))
            return out
        except zipfile.BadZipFile:
            logger.warning("progress: bad zip file %s", filename)
            return []
    return [(content, filename)]


def _get_sku_progress() -> dict:
    with get_session() as session:
        ingredients = list(session.exec(select(Ingredient)))
        skus = list(session.exec(select(SKU)))
        now = datetime.utcnow()
        ids_with_skus = {s.ingredient_id for s in skus if s.expires_at > now}
        with_skus = sum(1 for i in ingredients if i.id in ids_with_skus)
    return {
        "ingredients_total": len(ingredients),
        "ingredients_with_skus": with_skus,
    }


def _get_ingredient_ids_with_skus() -> set:
    with get_session() as session:
        skus = list(session.exec(select(SKU)))
        now = datetime.utcnow()
        return {s.ingredient_id for s in skus if s.expires_at > now}


def _get_ingredient_ids_unavailable() -> set:
    """Ingredient IDs explicitly marked sku_unavailable (SKU fetch returned 0)."""
    with get_session() as session:
        ingredients = list(session.exec(select(Ingredient)))
        return {i.id for i in ingredients if getattr(i, "sku_unavailable", False)}


def _match_and_normalize(ingredient_text: str, existing_names: list[str]):
    from app.services.llm.ingredient_matcher import match_ingredient
    from app.services.llm.unit_normalizer import normalize_units
    match = match_ingredient(ingredient_text, existing_names)
    normalized = normalize_units(ingredient_text)
    return match, normalized


def _run_processing(
    job_id: str,
    file_contents: list[tuple[bytes, str]],
    ingredient_totals: dict[str, int],
    effective_postal: str,
    event_queue: queue.Queue,
):
    """Sync processing loop. Puts (event, data) on queue after each significant step."""
    from app.config import settings

    configure_dspy()
    files_progress = [
        {
            "name": name,
            "ingredients_added": 0,
            "ingredients_total": ingredient_totals.get(name, 1),
            "ingredients_with_skus": 0,
            "ingredients_unavailable": 0,
            "sku_total": 0,
            "ingredient_ids": [],
        }
        for _, name in file_contents
    ]

    def _put(event: str, data: dict):
        event_queue.put_nowait((event, data))
        snap = [{"name": f["name"], "ingredients_added": f["ingredients_added"], "ingredients_total": f["ingredients_total"], "ingredients_with_skus": f["ingredients_with_skus"], "ingredients_unavailable": f.get("ingredients_unavailable", 0), "sku_total": len(set(f.get("ingredient_ids") or []))} for f in files_progress]
        job_progress_store[job_id] = {"files": snap, "complete": event == "stream_complete"}

    _put("upload_started", {"files": [{"name": f["name"], "ingredients_added": 0, "ingredients_total": f["ingredients_total"], "ingredients_with_skus": 0, "ingredients_unavailable": 0, "sku_total": 0} for f in files_progress]})

    parsing_done = threading.Event()

    def _sku_poll_loop():
        import time
        last_job_with_skus = -1
        last_job_unavailable = -1
        elapsed = 0
        while elapsed < SKU_POLL_TIMEOUT:
            time.sleep(SKU_POLL_INTERVAL)
            elapsed += SKU_POLL_INTERVAL
            job_ingredient_ids = set()
            for f in files_progress:
                job_ingredient_ids.update(f.get("ingredient_ids") or [])
            job_sku_total = len(job_ingredient_ids)
            for f in files_progress:
                f["sku_total"] = len(set(f.get("ingredient_ids") or []))
            ids_with_skus = _get_ingredient_ids_with_skus()
            ids_unavailable = _get_ingredient_ids_unavailable()
            for f in files_progress:
                ing_ids = set(f.get("ingredient_ids") or [])
                f["ingredients_with_skus"] = sum(1 for iid in ing_ids if iid in ids_with_skus)
                f["ingredients_unavailable"] = sum(1 for iid in ing_ids if iid in ids_unavailable)
            job_with_skus = sum(1 for iid in job_ingredient_ids if iid in ids_with_skus)
            job_unavailable = sum(1 for iid in job_ingredient_ids if iid in ids_unavailable)
            snap = [{"name": fp["name"], "ingredients_added": fp["ingredients_added"], "ingredients_total": fp["ingredients_total"], "ingredients_with_skus": fp["ingredients_with_skus"], "ingredients_unavailable": fp.get("ingredients_unavailable", 0), "sku_total": fp.get("sku_total", 0)} for fp in files_progress]
            job_progress_store[job_id] = {"files": snap, "complete": False}
            if job_with_skus != last_job_with_skus or job_unavailable != last_job_unavailable:
                last_job_with_skus = job_with_skus
                last_job_unavailable = job_unavailable
                _put("sku_progress", {"job_ingredients_with_skus": job_with_skus, "job_ingredients_unavailable": job_unavailable, "job_sku_total": job_sku_total, "files": snap})
            done = parsing_done.is_set() and (job_sku_total == 0 or job_with_skus + job_unavailable >= job_sku_total)
            if done:
                break

    sku_poll_thread = threading.Thread(target=_sku_poll_loop, daemon=True)
    sku_poll_thread.start()

    recipes_created = 0
    ingredients_created = 0
    sku_jobs = 0

    with get_session() as session:
        existing = get_ingredients(session)
        existing_names = [ing.canonical_name for ing in existing]
        existing_lookup = {ing.canonical_name: ing for ing in existing}

        for file_idx, (content, source_filename) in enumerate(file_contents):
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
                max_workers = min(settings.ingredient_batch_max_workers, max(1, len(parsed.ingredients)))

                results = {}
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futures = {ex.submit(_match_and_normalize, it, current_existing): it for it in parsed.ingredients}
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
                    canonical_name = (match.get("canonical_name") or "").strip().lower() or "unknown"
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
                    fetch_skus_for_ingredient.delay(ingredient.id, canonical_name, effective_postal)
                    sku_jobs += 1
                    files_progress[file_idx]["ingredients_added"] += 1
                    files_progress[file_idx]["ingredient_ids"].append(ingredient.id)

                    _put("ingredient_added", {
                        "ingredients_added": ingredients_created,
                        "name": canonical_name,
                        "files": [{"name": f["name"], "ingredients_added": f["ingredients_added"], "ingredients_total": f["ingredients_total"], "ingredients_with_skus": f["ingredients_with_skus"], "ingredients_unavailable": f.get("ingredients_unavailable", 0), "sku_total": len(set(f.get("ingredient_ids") or []))} for f in files_progress],
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
                recipe.allergens = infer_allergens_from_ingredients(recipe_ingredient_names)
                session.add(recipe)
                session.commit()

    for f in files_progress:
        f["sku_total"] = len(set(f.get("ingredient_ids") or []))

    _put("upload_complete", {
        "recipes_created": recipes_created,
        "ingredients_created": ingredients_created,
        "sku_jobs_enqueued": sku_jobs,
        "files": [{"name": fp["name"], "ingredients_added": fp["ingredients_added"], "ingredients_total": fp["ingredients_total"], "ingredients_with_skus": fp["ingredients_with_skus"], "ingredients_unavailable": fp.get("ingredients_unavailable", 0), "sku_total": fp["sku_total"]} for fp in files_progress],
    })

    parsing_done.set()
    sku_poll_thread.join(timeout=SKU_POLL_TIMEOUT)

    final_snap = [{"name": fp["name"], "ingredients_added": fp["ingredients_added"], "ingredients_total": fp["ingredients_total"], "ingredients_with_skus": fp["ingredients_with_skus"], "ingredients_unavailable": fp.get("ingredients_unavailable", 0), "sku_total": fp.get("sku_total", 0)} for fp in files_progress]
    _put("stream_complete", {})
    job_progress_store[job_id] = {"files": final_snap, "complete": True}
    try:
        del job_event_queues[job_id]
    except KeyError:
        pass


@router.get("/progress/{job_id}")
def get_progress(job_id: str) -> dict:
    return job_progress_store.get(job_id, {"files": [], "complete": False})


@router.get("/utilization")
def get_utilization() -> dict:
    """
    Parallelization and utilization visibility.
    - ingredient_workers: max parallelism for LLM ingredient matching (per recipe).
    - sku_workers: Celery concurrency for SKU fetching.
    - sku_queue_length: pending SKU tasks in Redis (approximate).
    - timing_hint: grep '[TIMING]' in logs to see actual runtimes.
    """
    from app.config import settings
    from app.workers.celery_app import celery_app

    out = {
        "ingredient_workers": {
            "max_per_recipe": settings.ingredient_batch_max_workers,
            "env_override": "INGREDIENT_BATCH_MAX_WORKERS",
            "tuning": "Increase if LLM calls are the bottleneck (grep [TIMING] ingredient.batch.parallel). Rule of thumb: 2–4× CPU cores for I/O-bound. Max ~16 to avoid rate limits.",
        },
        "sku_workers": {
            "celery_concurrency": settings.celery_worker_concurrency,
            "env_override": "CELERY_WORKER_CONCURRENCY",
            "tuning": "Increase if sku_queue_length stays high and active_tasks < concurrency. Each task does Instacart API + LLM filter. Rule of thumb: 10–20 for fast refresh.",
        },
        "batching": {
            "ingredient_match": "ThreadPoolExecutor parallelizes match+normalize per recipe (no batch LLM calls)",
            "sku_fetch": "One Celery task per ingredient; Instacart API is per-query (no batch endpoint)",
        },
    }
    try:
        from redis import Redis
        conn = Redis.from_url(settings.redis_url)
        out["sku_queue_length"] = conn.llen("celery")
    except Exception:
        out["sku_queue_length"] = None
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            total_active = sum(len(tasks) for tasks in active.values())
            out["sku_workers"]["active_tasks"] = total_active
    except Exception:
        out["sku_workers"]["active_tasks"] = None
    return out


@router.post("/recipes/upload", status_code=202)
async def upload_recipes(
    files: list[UploadFile] = File(...),
    postal_code: str | None = Form(default=None),
):
    """
    Upload recipes. Returns 202 immediately with job_id and files (real ingredient counts from structural parse).
    Processing runs in background. Connect to GET /recipes/upload/stream/{job_id} for SSE events.
    """
    from app.config import settings

    effective_postal = (postal_code or "").strip() or settings.default_postal_code
    job_id = str(uuid.uuid4())

    file_contents = []
    for upload in files:
        content = await upload.read()
        fn = upload.filename or "upload"
        for c, name in _expand_files(content, fn):
            file_contents.append((c, name))

    # Fast structural parse only (no LLM) to get real ingredient counts
    ingredient_totals = {}
    for content, name in file_contents:
        try:
            ingredient_totals[name] = count_ingredients_in_text(content.decode("utf-8"))
        except Exception:
            ingredient_totals[name] = 1

    files_progress = [
        {"name": name, "ingredients_added": 0, "ingredients_total": ingredient_totals.get(name, 1), "ingredients_with_skus": 0, "ingredients_unavailable": 0, "sku_total": 0}
        for _, name in file_contents
    ]
    job_progress_store[job_id] = {"files": files_progress, "complete": False}
    event_queue = queue.Queue()
    job_event_queues[job_id] = event_queue

    asyncio.get_event_loop().run_in_executor(
        None,
        _run_processing,
        job_id,
        file_contents,
        ingredient_totals,
        effective_postal,
        event_queue,
    )

    return {"job_id": job_id, "files": files_progress}


@router.get("/recipes/upload/stream/{job_id}")
async def stream_upload_progress(job_id: str):
    """
    SSE stream for upload progress. Yields events as they happen (per ingredient).
    Connect after receiving job_id from POST /recipes/upload.
    """
    ev_queue = job_event_queues.get(job_id)
    if not ev_queue:
        progress = job_progress_store.get(job_id)
        if progress and progress.get("complete"):
            async def finished():
                yield _emit_sse("stream_complete", {})
            return StreamingResponse(
                finished(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Job not found or expired"}, status_code=404)

    async def generate():
        poll_interval = 0.05
        while True:
            try:
                event, data = ev_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(poll_interval)
                continue
            yield _emit_sse(event, data)
            if event == "stream_complete":
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
