from dataclasses import dataclass
from typing import Dict, List, Optional

import pulp


@dataclass
class ILPSolverOptions:
    time_limit_seconds: int = 10
    batch_penalty: float = 0.0001


@dataclass
class IngredientOption:
    ingredient_id: int
    sku_id: int
    quantity: float
    cost: float


@dataclass
class RecipeOption:
    recipe_id: int
    servings: int
    ingredient_requirements: Dict[int, float]


def solve_ilp(
    target_servings: int,
    recipes: List[RecipeOption],
    options: List[IngredientOption],
    solver_options: Optional[ILPSolverOptions] = None,
    recipe_meal_types: Optional[Dict[int, str]] = None,
    meal_config: Optional[Dict[str, int]] = None,
) -> dict:
    opts = solver_options or ILPSolverOptions()
    model = pulp.LpProblem("meal_plan", pulp.LpMinimize)

    recipe_vars = {
        recipe.recipe_id: pulp.LpVariable(f"x_{recipe.recipe_id}", lowBound=0, cat="Integer")
        for recipe in recipes
    }
    sku_vars = {
        option.sku_id: pulp.LpVariable(f"y_{option.sku_id}", lowBound=0, cat="Integer")
        for option in options
    }

    model += pulp.lpSum([recipe_vars[r.recipe_id] * r.servings for r in recipes]) >= target_servings

    # Meal-type constraints: at least N recipes of each specified type must have batches >= 1
    if recipe_meal_types and meal_config:
        for meal_type, min_count in meal_config.items():
            if min_count and min_count > 0:
                type_recipe_ids = [rid for rid, mt in recipe_meal_types.items() if mt == meal_type]
                if type_recipe_ids:
                    # At least min_count total batches across recipes of this type
                    model += (
                        pulp.lpSum([recipe_vars[rid] for rid in type_recipe_ids if rid in recipe_vars])
                        >= min_count
                    )

    ingredients = {option.ingredient_id for option in options}
    for ingredient_id in ingredients:
        demand = []
        for recipe in recipes:
            if ingredient_id in recipe.ingredient_requirements:
                demand.append(recipe_vars[recipe.recipe_id] * recipe.ingredient_requirements[ingredient_id])
        supply = [
            sku_vars[opt.sku_id] * opt.quantity
            for opt in options
            if opt.ingredient_id == ingredient_id
        ]
        model += pulp.lpSum(demand) <= pulp.lpSum(supply)

    # Primary: minimize cost. Secondary: minimize recipe batches (avoids absurdly large x_r when costs tie).
    model += pulp.lpSum([sku_vars[o.sku_id] * o.cost for o in options]) + opts.batch_penalty * pulp.lpSum(recipe_vars.values())

    model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=opts.time_limit_seconds))

    return {
        "status": pulp.LpStatus[model.status],
        "recipes": {rid: var.value() for rid, var in recipe_vars.items()},
        "skus": {sid: var.value() for sid, var in sku_vars.items()},
        "objective": pulp.value(model.objective),
    }
