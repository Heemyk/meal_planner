"""Tests for allergen ontology and inference."""

import pytest

from app.services.allergens import (
    ALLERGEN_ONTOLOGY,
    get_all_allergen_codes,
    infer_allergens_from_ingredients,
)


def test_get_all_allergen_codes():
    codes = get_all_allergen_codes()
    assert len(codes) == 10
    assert "milk" in codes
    assert "eggs" in codes
    assert "peanuts" in codes
    assert "wheat" in codes


def test_infer_allergens_empty():
    assert infer_allergens_from_ingredients([]) == []


def test_infer_allergens_single():
    assert infer_allergens_from_ingredients(["milk"]) == ["milk"]
    assert infer_allergens_from_ingredients(["butter"]) == ["milk"]
    assert infer_allergens_from_ingredients(["egg"]) == ["eggs"]


def test_infer_allergens_multiple():
    result = infer_allergens_from_ingredients(["milk", "flour", "butter"])
    assert set(result) == {"milk", "wheat"}
    assert result == sorted(result)


def test_infer_allergens_all_keywords():
    ingredients = ["milk", "eggs", "flour", "soy", "mustard"]
    result = infer_allergens_from_ingredients(ingredients)
    assert "milk" in result
    assert "eggs" in result
    assert "wheat" in result
    assert "soy" in result
    assert "mustard" in result


def test_infer_allergens_case_insensitive():
    assert infer_allergens_from_ingredients(["MILK", "Egg"]) == ["eggs", "milk"]
    assert infer_allergens_from_ingredients(["Butter", "CREAM"]) == ["milk"]


def test_infer_allergens_substring_in_combined():
    # "flour" contains/match in combined string
    assert "wheat" in infer_allergens_from_ingredients(["all-purpose flour"])
    assert "milk" in infer_allergens_from_ingredients(["whole milk"])


def test_ontology_has_expected_structure():
    for code, keywords in ALLERGEN_ONTOLOGY.items():
        assert isinstance(code, str)
        assert isinstance(keywords, list)
        assert len(keywords) >= 1
        for kw in keywords:
            assert isinstance(kw, str)
