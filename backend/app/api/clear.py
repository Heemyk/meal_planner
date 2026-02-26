"""Clear all databases: Postgres tables and Redis."""

from fastapi import APIRouter
from redis import Redis
from sqlalchemy import text

from app.config import settings
from app.logging import get_logger
from app.storage.db import engine

router = APIRouter()
logger = get_logger(__name__)


@router.post("/clear")
def clear_all() -> dict:
    """Truncate Postgres tables and flush Redis. Destructive; use for dev/reset."""
    logger.info("clear_all.start")

    # Postgres: truncate in FK-safe order
    with engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE sku, recipeingredient, menuplan, llmcalllog, recipe, ingredient "
                "RESTART IDENTITY CASCADE"
            )
        )
        conn.commit()
    logger.info("clear_all.postgres_done")

    # Redis: flush all (Celery queue, caches, locks)
    try:
        redis_client = Redis.from_url(settings.redis_url)
        redis_client.flushall()
        redis_client.close()
        logger.info("clear_all.redis_done")
    except Exception as e:
        logger.warning("clear_all.redis_failed %s", e)

    return {"ok": True, "message": "All databases cleared."}
