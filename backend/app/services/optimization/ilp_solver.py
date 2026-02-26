from dataclasses import dataclass
from typing import Dict, List

import pulp


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
    target_servings: int, recipes: List[RecipeOption], options: List[IngredientOption]
) -> dict:
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
    BATCH_PENALTY = 0.0001
    model += pulp.lpSum([sku_vars[o.sku_id] * o.cost for o in options]) + BATCH_PENALTY * pulp.lpSum(recipe_vars.values())

    model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10))

    return {
        "status": pulp.LpStatus[model.status],
        "recipes": {rid: var.value() for rid, var in recipe_vars.items()},
        "skus": {sid: var.value() for sid, var in sku_vars.items()},
        "objective": pulp.value(model.objective),
    }
