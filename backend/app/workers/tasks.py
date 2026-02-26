from celery.utils.log import get_task_logger

from app.config import settings
from app.logging import get_logger
from app.utils.timing import time_span
from app.services.llm.dspy_client import configure_dspy
from app.services.llm.sku_filter import filter_skus
from app.services.llm.sku_size_converter import convert_sku_size
from app.services.sku.instacart_client import instacart_client
from app.storage.db import get_session
from app.storage.repositories import get_ingredient_by_id, set_ingredient_sku_unavailable, upsert_skus
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
app_logger = get_logger(__name__)


@celery_app.task(bind=True)
def fetch_skus_for_ingredient(self, ingredient_id: int, ingredient_name: str, postal_code: str | None = None):
    task_id = self.request.id
    postal_code = postal_code or settings.default_postal_code
    app_logger.info(
        "sku.fetch.start task_id=%s ingredient_id=%s name=%s postal=%s",
        task_id,
        ingredient_id,
        ingredient_name,
        postal_code,
    )
    with time_span("sku.fetch.total", task_id=task_id, ingredient_id=ingredient_id):
        try:
            configure_dspy()
            stores = instacart_client.get_stores(postal_code=postal_code)
            store = stores["data"]["stores"][0]
            retailer_slug = store["slug"]

            search = instacart_client.search_products(
                query=ingredient_name,
                postal_code=postal_code,
                retailer_slug=retailer_slug,
                limit=5,
            )
            candidates = search["data"]["products"]
            retailer_slug = search["data"].get("retailer", retailer_slug)
            filtered = filter_skus(query=ingredient_name, candidates=candidates)
            candidate_by_id = {c.get("id"): c for c in candidates if c.get("id")}
            for sku in filtered:
                orig = candidate_by_id.get(sku.get("id"))
                if orig and "retailer_slug" in orig:
                    sku["retailer_slug"] = orig["retailer_slug"]
            # Fallback when LLM returns truncated/unparseable JSON: simple keyword match
            if not filtered and candidates:
                q = ingredient_name.lower()
                filtered = [c for c in candidates if q in (c.get("name") or "").lower()]
                if filtered:
                    app_logger.info("sku.fetch.llm_fallback keyword_match count=%s", len(filtered))
            with get_session() as session:
                ingredient = get_ingredient_by_id(session, ingredient_id)
                if not ingredient:
                    app_logger.warning(
                        "sku.fetch.skip ingredient_id=%s not found (FK); likely stale task or DB reset",
                        ingredient_id,
                    )
                    return {"status": "skipped", "ingredient_id": ingredient_id, "reason": "ingredient_not_found"}
                base_unit = (ingredient.base_unit or "").strip().lower() or "count"
                count = len(filtered)
                if count == 0:
                    set_ingredient_sku_unavailable(session, ingredient_id, unavailable=True)
                    app_logger.info(
                        "sku.fetch.success task_id=%s ingredient_id=%s count=0 retailer=%s (marked sku_unavailable)",
                        task_id,
                        ingredient_id,
                        retailer_slug,
                    )
                    return {"status": "success", "ingredient_id": ingredient_id, "count": 0}
                skus_to_upsert = []
                for sku in filtered:
                    size_str = sku.get("size") or ""
                    product_name = sku.get("name") or ""
                    qty, display = convert_sku_size(size_str, base_unit, product_name)
                    skus_to_upsert.append({
                        "name": sku.get("name"),
                        "brand": sku.get("brand"),
                        "size": sku.get("size"),
                        "price": _parse_price(sku.get("price")),
                        "price_per_unit": sku.get("price_per_unit"),
                        "quantity_in_base_unit": qty,
                        "size_display": display or size_str,
                    })
                upsert_skus(
                    session=session,
                    ingredient_id=ingredient_id,
                    skus=skus_to_upsert,
                    retailer_slug=retailer_slug,
                    postal_code=postal_code,
                )
                set_ingredient_sku_unavailable(session, ingredient_id, unavailable=False)
            app_logger.info(
                "sku.fetch.success task_id=%s ingredient_id=%s count=%s retailer=%s",
                task_id,
                ingredient_id,
                len(filtered),
                retailer_slug,
            )
            return {"status": "success", "ingredient_id": ingredient_id, "count": len(filtered)}
        except Exception as exc:
            app_logger.error(
                "sku.fetch.failure task_id=%s ingredient_id=%s name=%s error=%s",
                task_id,
                ingredient_id,
                ingredient_name,
                exc,
                exc_info=True,
            )
            raise


@celery_app.task
def refresh_expired_skus(ingredient_ids: list[int] | None = None, postal_code: str | None = None):
    """
    Find ingredients with no valid (non-expired) SKUs and re-enqueue fetch jobs.
    Run periodically (e.g. every 30 min) via Celery Beat, or manually via API.
    - ingredient_ids: optional, limit to these IDs; None = all needing refresh
    - postal_code: optional, default_postal_code used if not provided
    """
    from app.storage.repositories import get_ingredients_needing_sku_refresh

    postal = postal_code or settings.default_postal_code
    with get_session() as session:
        ingredients = get_ingredients_needing_sku_refresh(session, ingredient_ids)
    count = 0
    for ing in ingredients:
        fetch_skus_for_ingredient.delay(ing.id, ing.canonical_name, postal)
        count += 1
    app_logger.info("sku.refresh_expired queued=%s ingredient_ids=%s", count, [i.id for i in ingredients])
    return {"queued": count, "ingredient_ids": [i.id for i in ingredients]}


def _parse_price(price: str | None) -> float | None:
    if not price:
        return None
    try:
        s = price.replace("$", "").replace(",", "").strip()
        return float(s) if s else None
    except ValueError:
        return None
