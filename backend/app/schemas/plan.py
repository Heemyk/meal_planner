from typing import Any

from pydantic import BaseModel


class PlanRequest(BaseModel):
    target_servings: int
    postal_code: str | None = None
    time_limit_seconds: int | None = None
    batch_penalty: float | None = None
    meal_config: dict[str, int] | None = None  # e.g. {"appetizer": 1, "entree": 1, "dessert": 1, "side": 1}
    store_slugs: list[str] | None = None  # e.g. ["costco", "market-basket"] - only use SKUs from these stores
    exclude_allergens: list[str] | None = None  # e.g. ["nuts", "milk"] - exclude recipes containing these


class PlanResponse(BaseModel):
    status: str
    objective: float | None
    plan_payload: dict
    sku_details: dict[str, dict[str, Any]] = {}
    recipe_details: list[dict[str, Any]] = []
    consolidated_shopping_list: list[dict[str, Any]] = []
    menu_card: list[dict[str, Any]] = []
    infeasible_reason: str | None = None  # e.g. "Relax store filter or meal-type constraints."
