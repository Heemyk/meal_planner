from pathlib import Path

from app.services.parsing.recipe_parser import parse_recipe_text


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
