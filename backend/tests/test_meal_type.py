"""Tests for meal type inference."""

from app.services.parsing.recipe_parser import infer_meal_type


def test_infer_meal_type_entree_default():
    assert infer_meal_type("Chicken Stir Fry", "Cook the chicken") == "entree"
    assert infer_meal_type("Beef Stew", "") == "entree"


def test_infer_meal_type_dessert():
    assert infer_meal_type("Chocolate Cake", "Bake for 30 minutes") == "dessert"
    assert infer_meal_type("Apple Pie", "") == "dessert"
    assert infer_meal_type("Ice cream sundae", "") == "dessert"
    assert infer_meal_type("Pudding", "Chill before serving") == "dessert"


def test_infer_meal_type_appetizer():
    assert infer_meal_type("Greek Salad", "Toss ingredients") == "appetizer"
    assert infer_meal_type("Tomato Soup", "Simmer for 20 min") == "appetizer"
    assert infer_meal_type("Bruschetta", "Toast the bread") == "appetizer"
    assert infer_meal_type("Spinach dip", "Mix and serve") == "appetizer"


def test_infer_meal_type_side():
    assert infer_meal_type("Mashed Potato", "Boil and mash") == "side"
    assert infer_meal_type("Steamed Asparagus", "Steam for 5 min") == "side"
    assert infer_meal_type("Garlic bread", "Toast with garlic butter") == "side"


def test_infer_meal_type_priority_dessert_over_side():
    # "potato" could match side, but "pie" matches dessert first - order in code matters
    assert infer_meal_type("Sweet Potato Pie", "") == "dessert"


def test_infer_meal_type_from_instructions():
    assert infer_meal_type("Mystery Dish", "Serve as appetizer with crackers") == "appetizer"
    assert infer_meal_type("Dish", "A dessert to finish the meal") == "dessert"
