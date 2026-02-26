from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


MEAL_TYPES = ("appetizer", "entree", "dessert", "side")


class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    servings: int
    instructions: str
    source_file: str
    meal_type: str = "entree"  # appetizer | entree | dessert | side
    allergens: Optional[list] = Field(default=None, sa_column=Column(JSON, default=None))  # set on upload
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Ingredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    canonical_name: str
    base_unit: str
    base_unit_qty: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RecipeIngredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    ingredient_id: int = Field(foreign_key="ingredient.id")
    quantity: float
    unit: str
    original_text: str


class SKU(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredient.id")
    name: str
    brand: Optional[str] = None
    size: Optional[str] = None
    price: Optional[float] = None
    price_per_unit: Optional[str] = None
    retailer_slug: Optional[str] = None
    postal_code: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class MenuPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    target_servings: int
    plan_payload: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMCallLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_name: str
    prompt_version: str
    model: str
    input_payload: str
    output_payload: str
    latency_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
