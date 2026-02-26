import re
from datetime import datetime

from fastapi import APIRouter, Body
from sqlmodel import select

from app.logging import get_logger
from app.schemas.plan import PlanRequest, PlanResponse
from app.utils.timing import time_span
from app.services.optimization.ilp_solver import ILPSolverOptions, IngredientOption, RecipeOption, solve_ilp
from app.storage.db import get_session
from app.storage.models import Ingredient, Recipe, RecipeIngredient, SKU
from app.services.allergens import get_all_allergen_codes
from app.services.llm.sku_size_converter import convert_sku_size
from app.storage.repositories import create_menu_plan

router = APIRouter()
logger = get_logger(__name__)


@router.get("/allergens")
def list_allergens():
    """Return allergen codes for filter UI."""
    return {"allergens": get_all_allergen_codes()}


@router.get("/stores")
def list_stores(postal_code: str | None = None):
    """Return available stores for store filter dropdown. Uses postal for Instacart availability."""
    from app.services.sku.instacart_client import instacart_client
    from app.config import settings
    pc = (postal_code or "").strip() or settings.default_postal_code
    try:
        data = instacart_client.get_stores(pc)
        stores = (data.get("data") or {}).get("stores") or []
    except Exception as e:
        logger.warning("stores.fetch_failed postal=%s error=%s", pc, e)
        stores = []
    return {"stores": [{"slug": s.get("slug"), "name": s.get("name", s.get("slug", ""))} for s in stores if s.get("slug")]}


PLACEHOLDER_COST = 1.0
PLACEHOLDER_QTY = 999999.0


@router.get("/recipes")
def list_recipes(exclude_allergens: str | None = None):
    """
    Return all recipes for display.
    exclude_allergens: comma-separated allergen codes to filter out (e.g. nuts,milk).
    Recipes with ingredients marked sku_unavailable get has_unavailable_ingredients=True
    and unavailable_ingredient_names=[...]; display them greyed out, exclude from plan.
    """
    with get_session() as session:
        recipes = list(session.exec(select(Recipe)))
        recipe_ingredients = list(session.exec(select(RecipeIngredient)))
        ingredients = {i.id: i for i in session.exec(select(Ingredient))}
        # Map recipe_id -> set of ingredient canonical_names that are sku_unavailable
        unavailable_by_recipe: dict[int, list[str]] = {}
        for ri in recipe_ingredients:
            ing = ingredients.get(ri.ingredient_id)
            if ing and getattr(ing, "sku_unavailable", False):
                unavailable_by_recipe.setdefault(ri.recipe_id, []).append(
                    ing.canonical_name or ing.name
                )
        exclude_set = set()
        if exclude_allergens:
            exclude_set = {a.strip().lower() for a in exclude_allergens.split(",") if a.strip()}
        result = []
        for r in recipes:
            allergens = (r.allergens or []) if hasattr(r, "allergens") else []
            if exclude_set and set(allergens) & exclude_set:
                continue
            unavailable_names = list(dict.fromkeys(unavailable_by_recipe.get(r.id, [])))
            result.append({
                "id": r.id,
                "name": r.name,
                "servings": r.servings,
                "instructions": r.instructions,
                "source_file": r.source_file,
                "meal_type": getattr(r, "meal_type", "entree"),
                "allergens": allergens,
                "has_unavailable_ingredients": len(unavailable_names) > 0,
                "unavailable_ingredient_names": unavailable_names,
            })
        return result


@router.get("/ingredients-with-skus")
def ingredients_with_skus():
    """Return all ingredients with their attached SKUs for display."""
    with get_session() as session:
        ingredients = list(session.exec(select(Ingredient)))
        skus = list(session.exec(select(SKU)))
        now = datetime.utcnow()
        valid_skus = [s for s in skus if s.expires_at > now]
        skus_by_ingredient: dict[int, list] = {}
        for s in valid_skus:
            skus_by_ingredient.setdefault(s.ingredient_id, []).append(s)
        def _sku_row(s) -> dict:
            size = getattr(s, "size_display", None) or s.size
            qty = getattr(s, "quantity_in_base_unit", None)
            price = s.price
            ppu = None
            if price is not None and qty and qty > 0:
                ppu = round(price / qty, 6)
            out = {
                "id": s.id,
                "name": s.name,
                "brand": s.brand,
                "size": size,
                "price": price,
                "retailer_slug": s.retailer_slug,
            }
            if ppu is not None:
                out["price_per_base_unit"] = ppu
            return out
        return [
            {
                "id": i.id,
                "name": i.canonical_name,
                "base_unit": i.base_unit,
                "skus": [_sku_row(sk) for sk in skus_by_ingredient.get(i.id, [])],
                "sku_unavailable": getattr(i, "sku_unavailable", False),
            }
            for i in ingredients
        ]


@router.post("/sku/refresh")
def refresh_skus(body: dict | None = Body(default=None)) -> dict:
    """
    Manually trigger SKU refresh for ingredients with no valid (non-expired) prices.
    Body: { "ingredient_ids": [1,2,3], "postal_code": "10001" } — both optional.
    Omit ingredient_ids to refresh all needing it. Enqueues fetch_skus_for_ingredient tasks.
    """
    from app.storage.repositories import get_ingredients_needing_sku_refresh
    from app.workers.tasks import refresh_expired_skus

    body = body or {}
    ingredient_ids = body.get("ingredient_ids")
    postal_code = body.get("postal_code")
    refresh_expired_skus.delay(ingredient_ids=ingredient_ids, postal_code=postal_code)
    with get_session() as session:
        ingredients = get_ingredients_needing_sku_refresh(session, ingredient_ids)
    return {
        "queued": len(ingredients),
        "ingredient_ids": [i.id for i in ingredients],
        "message": f"Enqueued SKU refresh for {len(ingredients)} ingredient(s)",
    }


@router.post("/sku/reset")
def reset_skus(body: dict | None = Body(default=None)) -> dict:
    """
    Delete all SKU rows for given ingredient_ids, then enqueue refresh.
    Body: { "ingredient_ids": [1,2,3], "postal_code": "10001" }. ingredient_ids required.
    Use to force full re-fetch of prices. Parsed data (Recipe/Ingredient) is unchanged.
    """
    from app.storage.repositories import delete_skus_for_ingredients, get_ingredients_needing_sku_refresh
    from app.workers.tasks import refresh_expired_skus

    body = body or {}
    ingredient_ids = body.get("ingredient_ids")
    if not ingredient_ids:
        return {"deleted": 0, "queued": 0, "message": "ingredient_ids required"}
    postal_code = body.get("postal_code")
    with get_session() as session:
        deleted = delete_skus_for_ingredients(session, ingredient_ids)
    refresh_expired_skus.delay(ingredient_ids=ingredient_ids, postal_code=postal_code)
    with get_session() as session:
        ingredients = get_ingredients_needing_sku_refresh(session, ingredient_ids)
    return {
        "deleted": deleted,
        "queued": len(ingredients),
        "ingredient_ids": ingredient_ids,
        "message": f"Deleted {deleted} SKU(s), enqueued refresh for {len(ingredients)} ingredient(s)",
    }


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
            if request.exclude_allergens:
                exclude_set = {a.strip().lower() for a in request.exclude_allergens if a.strip()}
                recipes = [
                    r for r in recipes
                    if not (set(r.allergens or []) & exclude_set)
                ]
            recipe_ingredients = list(session.exec(select(RecipeIngredient)))
            ingredients = {i.id: i for i in session.exec(select(Ingredient))}
            # Exclude recipes that contain any ingredient with sku_unavailable
            recipe_ids_with_unavailable = {
                ri.recipe_id
                for ri in recipe_ingredients
                if ingredients.get(ri.ingredient_id) and getattr(ingredients[ri.ingredient_id], "sku_unavailable", False)
            }
            recipes = [r for r in recipes if r.id not in recipe_ids_with_unavailable]
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

            store_slugs = None
            if request.store_slugs:
                store_slugs = [s.lower().strip().replace(" ", "-") for s in request.store_slugs if s]

            ingredients_by_id = {i.id: i for i in session.exec(select(Ingredient))}
            sku_options = []
            ingredient_ids_with_options = set()
            for sku in valid_skus:
                if store_slugs:
                    slug = (sku.retailer_slug or "").lower()
                    if slug not in store_slugs:
                        continue
                ing = ingredients_by_id.get(sku.ingredient_id)
                base_unit = ing.base_unit if ing else "count"
                qty = sku.quantity_in_base_unit
                if qty is None or qty <= 0:
                    qty, _ = convert_sku_size(sku.size, base_unit)
                sku_options.append(
                    IngredientOption(
                        ingredient_id=sku.ingredient_id,
                        sku_id=sku.id,
                        quantity=qty,
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

            recipe_meal_types = {r.id: getattr(r, "meal_type", "entree") for r in recipes}
            meal_config = request.meal_config or {}

            # Check feasibility: all required ingredients must have at least one SKU from selected stores
            missing_with_store = all_required_ingredient_ids - ingredient_ids_with_options
            if store_slugs and missing_with_store:
                return PlanResponse(
                    status="Infeasible",
                    objective=None,
                    plan_payload={},
                    sku_details={},
                    recipe_details=[],
                    consolidated_shopping_list=[],
                    menu_card=[],
                    infeasible_reason="Some ingredients have no SKUs from selected stores. Relax the store filter.",
                )
            if store_slugs and not sku_options and all_required_ingredient_ids:
                return PlanResponse(
                    status="Infeasible",
                    objective=None,
                    plan_payload={},
                    sku_details={},
                    recipe_details=[],
                    consolidated_shopping_list=[],
                    menu_card=[],
                    infeasible_reason="No SKUs from selected stores. Try relaxing the store filter.",
                )

            solver_opts = None
            if request.time_limit_seconds is not None or request.batch_penalty is not None:
                solver_opts = ILPSolverOptions(
                    time_limit_seconds=request.time_limit_seconds if request.time_limit_seconds is not None else 10,
                    batch_penalty=request.batch_penalty if request.batch_penalty is not None else 0.0001,
                )
            result = solve_ilp(
                request.target_servings,
                recipe_options,
                sku_options,
                solver_opts,
                recipe_meal_types=recipe_meal_types,
                meal_config=meal_config,
                include_every_recipe_ids=request.include_every_recipe_ids,
                required_recipe_ids=request.required_recipe_ids,
            )
            plan_payload = {
                "recipes": {str(k): int(v) if v is not None else 0 for k, v in (result["recipes"] or {}).items()},
                "skus": {str(k): int(v) if v is not None else 0 for k, v in (result["skus"] or {}).items()},
            }
            if result.get("status") != "Infeasible":
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
                        "size": getattr(s, "size_display", None) or s.size,
                        "quantity": int(qty),
                    }

            # Build recipe_details, consolidated_shopping_list, menu_card
            recipe_by_id = {r.id: r for r in recipes}
            recipe_details_list: list[dict] = []
            ingredient_totals: dict[int, float] = {}
            menu_card_list: list[dict] = []

            for rid, batches in (result.get("recipes") or {}).items():
                bid = int(rid)
                if not batches:
                    continue
                recipe = recipe_by_id.get(bid)
                if not recipe:
                    continue
                recipe_details_list.append({
                    "recipe_id": bid,
                    "name": recipe.name,
                    "batches": int(batches),
                    "servings_per_batch": recipe.servings,
                    "total_servings": int(batches) * recipe.servings,
                })
                scale = int(batches)
                for ri in recipe_ingredients:
                    if ri.recipe_id != bid:
                        continue
                    ingredient_totals[ri.ingredient_id] = ingredient_totals.get(ri.ingredient_id, 0) + ri.quantity * scale
                first_line = (recipe.instructions or "").split(".")[0].strip()
                if first_line:
                    first_line += "."
                menu_card_list.append({
                    "name": recipe.name,
                    "recipe_id": bid,
                    "meal_type": recipe.meal_type or "entree",
                    "allergens": recipe.allergens or [],
                    "ingredients": [
                        ri.original_text for ri in recipe_ingredients
                        if ri.recipe_id == bid
                    ],
                    "description": first_line or f"A delicious {recipe.name}.",
                    "instructions": recipe.instructions or "",
                })

            consolidated_shopping_list: list[dict] = []
            for ing_id, total_qty in ingredient_totals.items():
                ing = ingredients_by_id.get(ing_id)  # already loaded above
                if not ing:
                    continue
                consolidated_shopping_list.append({
                    "ingredient": ing.canonical_name,
                    "quantity": round(total_qty, 2),
                    "unit": ing.base_unit or "units",
                })

        status = result.get("status", "Unknown")
        objective_val = result.get("objective")
        if objective_val is None:
            objective_val = 0.0
        infeasible_reason = None
        if status == "Infeasible":
            infeasible_reason = "Optimization not possible. Relax meal-type or store constraints."
        logger.info("plan.end status=%s objective=%s", status, objective_val)
        return PlanResponse(
            status=status,
            objective=float(objective_val),
            infeasible_reason=infeasible_reason,
            plan_payload=plan_payload,
            sku_details=sku_details if status != "Infeasible" else {},
            recipe_details=recipe_details_list if status != "Infeasible" else [],
            consolidated_shopping_list=consolidated_shopping_list if status != "Infeasible" else [],
            menu_card=menu_card_list if status != "Infeasible" else [],
        )


def _parse_size(size: str | None) -> float:
    if not size:
        return 1.0
    match = re.search(r"([\d\.]+)", size)
    if not match:
        return 1.0
    return float(match.group(1))
