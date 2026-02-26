from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.optimize import router as optimize_router
from app.api.recipes import router as recipes_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(recipes_router)
router.include_router(optimize_router)
