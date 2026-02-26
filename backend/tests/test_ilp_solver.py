from app.services.optimization.ilp_solver import (
    ILPSolverOptions,
    IngredientOption,
    RecipeOption,
    solve_ilp,
)


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


def test_ilp_solver_with_meal_config():
    recipes = [
        RecipeOption(recipe_id=1, servings=2, ingredient_requirements={1: 1}),
        RecipeOption(recipe_id=2, servings=2, ingredient_requirements={1: 1}),
    ]
    options = [
        IngredientOption(ingredient_id=1, sku_id=10, quantity=4, cost=2.0),
    ]
    recipe_meal_types = {1: "entree", 2: "entree"}
    meal_config = {"entree": 1}
    result = solve_ilp(
        target_servings=2,
        recipes=recipes,
        options=options,
        recipe_meal_types=recipe_meal_types,
        meal_config=meal_config,
    )
    assert result["status"] in {"Optimal", "Not Solved"}
    assert result["recipes"] is not None
    # At least one recipe should have batches >= 1
    total_batches = sum(v or 0 for v in result["recipes"].values())
    assert total_batches >= 1


def test_ilp_solver_with_options():
    recipes = [
        RecipeOption(recipe_id=1, servings=2, ingredient_requirements={1: 1}),
    ]
    options = [
        IngredientOption(ingredient_id=1, sku_id=10, quantity=2, cost=1.0),
    ]
    opts = ILPSolverOptions(time_limit_seconds=5, batch_penalty=0.001)
    result = solve_ilp(
        target_servings=2,
        recipes=recipes,
        options=options,
        solver_options=opts,
    )
    assert result["status"] in {"Optimal", "Not Solved"}
    assert result["objective"] is not None
