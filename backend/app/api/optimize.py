import re
from datetime import datetime

from fastapi import APIRouter
from sqlmodel import select

from app.logging import get_logger
from app.schemas.plan import PlanRequest, PlanResponse
from app.utils.timing import time_span
from app.services.optimization.ilp_solver import IngredientOption, RecipeOption, solve_ilp
from app.storage.db import get_session
from app.storage.models import Ingredient, Recipe, RecipeIngredient, SKU
from app.storage.repositories import create_menu_plan

router = APIRouter()
logger = get_logger(__name__)

PLACEHOLDER_COST = 1.0
PLACEHOLDER_QTY = 999999.0


@router.get("/sku-status")
def sku_status() -> dict:
    """Report which ingredients have SKUs and which are still pending (worker not done)."""
    with get_session() as session:
        ingredients = list(session.exec(select(Ingredient)))
        skus = list(session.exec(select(SKU)))
        now = datetime.utcnow()
        ingredient_ids_with_skus = {s.ingredient_id for s in skus if s.expires_at > now}
        with_skus = [i.canonical_name for i in ingredients if i.id in ingredient_ids_with_skus]
        without_skus = [i.canonical_name for i in ingredients if i.id not in ingredient_ids_with_skus]
    return {
        "ingredients_with_skus": with_skus,
        "ingredients_without_skus": without_skus,
        "total_skus": len(skus),
    }


@router.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    with time_span("plan.total", servings=request.target_servings):
        logger.info("plan.start servings=%s", request.target_servings)
        with get_session() as session:
            recipes = list(session.exec(select(Recipe)))
            recipe_ingredients = list(session.exec(select(RecipeIngredient)))
            skus = list(session.exec(select(SKU)))
            now = datetime.utcnow()
            valid_skus = [s for s in skus if s.expires_at > now]

            recipe_options = []
            all_required_ingredient_ids = set()
            for recipe in recipes:
                requirements = {
                    ri.ingredient_id: ri.quantity
                    for ri in recipe_ingredients
                    if ri.recipe_id == recipe.id
                }
                all_required_ingredient_ids.update(requirements)
                recipe_options.append(
                    RecipeOption(
                        recipe_id=recipe.id,
                        servings=recipe.servings,
                        ingredient_requirements=requirements,
                    )
                )

            sku_options = []
            ingredient_ids_with_options = set()
            for sku in valid_skus:
                sku_options.append(
                    IngredientOption(
                        ingredient_id=sku.ingredient_id,
                        sku_id=sku.id,
                        quantity=_parse_size(sku.size),
                        cost=sku.price or 0.0,
                    )
                )
                ingredient_ids_with_options.add(sku.ingredient_id)

            PLACEHOLDER_ID_BASE = 1_000_000
            missing = all_required_ingredient_ids - ingredient_ids_with_options
            if missing:
                logger.warning("plan.missing_skus ingredient_ids=%s using placeholders", list(missing))
                for i, ingredient_id in enumerate(missing):
                    sku_options.append(
                        IngredientOption(
                            ingredient_id=ingredient_id,
                            sku_id=PLACEHOLDER_ID_BASE + ingredient_id,
                            quantity=PLACEHOLDER_QTY,
                            cost=PLACEHOLDER_COST,
                        )
                    )

            result = solve_ilp(request.target_servings, recipe_options, sku_options)
            plan_payload = {
                "recipes": {str(k): int(v) if v is not None else 0 for k, v in (result["recipes"] or {}).items()},
                "skus": {str(k): int(v) if v is not None else 0 for k, v in (result["skus"] or {}).items()},
            }
            create_menu_plan(session, request.target_servings, str(plan_payload))

            # Build sku_details for display (name, brand, retailer)
            sku_by_id = {str(s.id): s for s in valid_skus}
            sku_details: dict[str, dict] = {}
            for sku_id_str, qty in (plan_payload.get("skus") or {}).items():
                if qty and sku_id_str in sku_by_id:
                    s = sku_by_id[sku_id_str]
                    sku_details[sku_id_str] = {
                        "name": s.name,
                        "brand": s.brand,
                        "retailer": s.retailer_slug,
                        "price": s.price,
                        "size": s.size,
                        "quantity": int(qty),
                    }

        objective_val = result.get("objective")
        if objective_val is None:
            objective_val = 0.0
        logger.info("plan.end status=%s objective=%s", result["status"], objective_val)
        return PlanResponse(
            status=result["status"],
            objective=float(objective_val),
            plan_payload=plan_payload,
            sku_details=sku_details,
        )


def _parse_size(size: str | None) -> float:
    if not size:
        return 1.0
    match = re.search(r"([\d\.]+)", size)
    if not match:
        return 1.0
    return float(match.group(1))
