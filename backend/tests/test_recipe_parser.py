from pathlib import Path

from app.services.parsing.recipe_parser import infer_meal_type, parse_recipe_text


def test_parse_recipe_text_from_dataset():
    repo_root = Path(__file__).resolve().parents[2]
    file_path = repo_root / "intern-dataset-main" / "1.txt"
    with file_path.open("r", encoding="utf-8") as handle:
        text = handle.read()
    recipes = parse_recipe_text(text)
    assert len(recipes) == 3
    assert recipes[0].name == "Lemon Herb Roasted Chicken"
    assert recipes[0].servings == 4
    assert "whole chicken" in recipes[0].ingredients[0]


def test_infer_meal_type_in_parsed_recipes():
    repo_root = Path(__file__).resolve().parents[2]
    file_path = repo_root / "intern-dataset-main" / "1.txt"
    with file_path.open("r", encoding="utf-8") as handle:
        text = handle.read()
    recipes = parse_recipe_text(text)
    # Lemon Herb Roasted Chicken -> entree
    assert infer_meal_type(recipes[0].name, recipes[0].instructions) == "entree"
    # Garlic Mashed Potatoes -> side (potato)
    assert infer_meal_type(recipes[1].name, recipes[1].instructions) == "side"
    # Steamed Asparagus -> side
    assert infer_meal_type(recipes[2].name, recipes[2].instructions) == "side"
