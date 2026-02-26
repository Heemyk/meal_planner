from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlmodel import Session, select

from app.config import settings
from app.logging import get_logger
from app.storage.models import Ingredient, LLMCallLog, MenuPlan, Recipe, RecipeIngredient, SKU

logger = get_logger(__name__)


def create_recipe(session: Session, recipe: Recipe) -> Recipe:
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    logger.info("recipe.created id=%s name=%s servings=%s", recipe.id, recipe.name, recipe.servings)
    return recipe


def create_recipe_ingredients(
    session: Session, recipe_ingredients: Iterable[RecipeIngredient]
) -> None:
    items = list(recipe_ingredients)
    session.add_all(items)
    session.commit()
    logger.info("recipe_ingredients.created count=%s", len(items))


def get_ingredients(session: Session) -> list[Ingredient]:
    return list(session.exec(select(Ingredient)))


def get_ingredient_by_id(session: Session, ingredient_id: int) -> Ingredient | None:
    return session.exec(select(Ingredient).where(Ingredient.id == ingredient_id)).first()


def get_or_create_ingredient(
    session: Session, name: str, canonical_name: str, base_unit: str, base_unit_qty: float
) -> Ingredient:
    ingredient = session.exec(
        select(Ingredient).where(Ingredient.canonical_name == canonical_name)
    ).first()
    if ingredient:
        return ingredient
    ingredient = Ingredient(
        name=name,
        canonical_name=canonical_name,
        base_unit=base_unit,
        base_unit_qty=base_unit_qty,
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient


def upsert_skus(
    session: Session, ingredient_id: int, skus: list[dict], retailer_slug: str, postal_code: str
) -> list[SKU]:
    """Upsert SKUs. Per-SKU retailer_slug preferred; fallback to top-level retailer_slug."""
    expires_at = datetime.utcnow() + timedelta(hours=settings.sku_cache_ttl_hours)
    created: list[SKU] = []
    for sku in skus:
        slug = sku.get("retailer_slug") or retailer_slug
        model = SKU(
            ingredient_id=ingredient_id,
            name=sku.get("name", ""),
            brand=sku.get("brand"),
            size=sku.get("size"),
            price=sku.get("price"),
            price_per_unit=sku.get("price_per_unit"),
            retailer_slug=slug,
            postal_code=postal_code,
            expires_at=expires_at,
        )
        session.add(model)
        created.append(model)
    session.commit()
    for sku in created:
        session.refresh(sku)
        logger.info(
            "sku.created id=%s ingredient_id=%s name=%s price=%s retailer=%s brand=%s",
            sku.id,
            sku.ingredient_id,
            sku.name,
            sku.price,
            sku.retailer_slug,
            sku.brand,
        )
    return created


def get_active_skus(session: Session, ingredient_id: int) -> list[SKU]:
    now = datetime.utcnow()
    return list(
        session.exec(
            select(SKU).where(SKU.ingredient_id == ingredient_id, SKU.expires_at > now)
        )
    )


def create_menu_plan(session: Session, target_servings: int, plan_payload: str) -> MenuPlan:
    plan = MenuPlan(target_servings=target_servings, plan_payload=plan_payload)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def log_llm_call(
    session: Session,
    prompt_name: str,
    prompt_version: str,
    model: str,
    input_payload: str,
    output_payload: str,
    latency_ms: int,
) -> None:
    session.add(
        LLMCallLog(
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            model=model,
            input_payload=input_payload,
            output_payload=output_payload,
            latency_ms=latency_ms,
        )
    )
    session.commit()
