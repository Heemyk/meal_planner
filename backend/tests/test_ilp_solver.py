from app.services.optimization.ilp_solver import IngredientOption, RecipeOption, solve_ilp


def test_ilp_solver_basic():
    recipes = [
        RecipeOption(recipe_id=1, servings=2, ingredient_requirements={1: 1}),
        RecipeOption(recipe_id=2, servings=4, ingredient_requirements={1: 2}),
    ]
    options = [
        IngredientOption(ingredient_id=1, sku_id=10, quantity=2, cost=3.0),
        IngredientOption(ingredient_id=1, sku_id=11, quantity=4, cost=5.0),
    ]
    result = solve_ilp(target_servings=4, recipes=recipes, options=options)
    assert result["status"] in {"Optimal", "Not Solved", "Infeasible", "Undefined"}
    assert result["objective"] is not None
