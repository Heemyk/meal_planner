from typing import Any

from pydantic import BaseModel


class PlanRequest(BaseModel):
    target_servings: int


class PlanResponse(BaseModel):
    status: str
    objective: float | None
    plan_payload: dict
    sku_details: dict[str, dict[str, Any]] = {}
