from celery import Celery

from app.config import settings
from app.logging import configure_logging, get_logger


celery_app = Celery("tandem", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "celery"}}
celery_app.conf.worker_concurrency = settings.celery_worker_concurrency

# Celery Beat: refresh expired SKUs every 30 minutes
celery_app.conf.beat_schedule = {
    "refresh-expired-skus": {
        "task": "app.workers.tasks.refresh_expired_skus",
        "schedule": 1800.0,  # 30 minutes in seconds
        "options": {"queue": "celery"},
    },
}

# Import tasks so they are registered with the worker
from app.workers import tasks  # noqa: F401

configure_logging()
logger = get_logger(__name__)
logger.info(
    "celery.configured broker=%s worker_concurrency=%s (fetch_skus_for_ingredient workers)",
    settings.redis_url,
    settings.celery_worker_concurrency,
)
