"""Tests for allergen ontology and inference."""

from app.services.allergens import (
    ALLERGEN_ONTOLOGY,
    _infer_allergens_keywords,
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
    assert infer_allergens_from_ingredients([], use_llm=False) == []


def test_infer_allergens_single():
    assert infer_allergens_from_ingredients(["milk"], use_llm=False) == ["milk"]
    assert infer_allergens_from_ingredients(["butter"], use_llm=False) == ["milk"]
    assert infer_allergens_from_ingredients(["egg"], use_llm=False) == ["eggs"]


def test_infer_allergens_multiple():
    result = infer_allergens_from_ingredients(["milk", "flour", "butter"], use_llm=False)
    assert set(result) == {"milk", "wheat"}
    assert result == sorted(result)


def test_infer_allergens_all_keywords():
    ingredients = ["milk", "eggs", "flour", "soy", "mustard"]
    result = infer_allergens_from_ingredients(ingredients, use_llm=False)
    assert "milk" in result
    assert "eggs" in result
    assert "wheat" in result
    assert "soy" in result
    assert "mustard" in result


def test_infer_allergens_case_insensitive():
    assert infer_allergens_from_ingredients(["MILK", "Egg"], use_llm=False) == ["eggs", "milk"]
    assert infer_allergens_from_ingredients(["Butter", "CREAM"], use_llm=False) == ["milk"]


def test_infer_allergens_substring_in_combined():
    assert "wheat" in infer_allergens_from_ingredients(["all-purpose flour"], use_llm=False)
    assert "milk" in infer_allergens_from_ingredients(["whole milk"], use_llm=False)


def test_keyword_fallback_unchanged():
    """Keyword logic (used as fallback) remains correct."""
    assert _infer_allergens_keywords(["milk", "flour"]) == ["milk", "wheat"]


def test_ontology_has_expected_structure():
    for code, keywords in ALLERGEN_ONTOLOGY.items():
        assert isinstance(code, str)
        assert isinstance(keywords, list)
        assert len(keywords) >= 1
        for kw in keywords:
            assert isinstance(kw, str)


def test_infer_allergens_llm_mocked(monkeypatch):
    """LLM path returns parsed allergens when LLM succeeds."""
    from app.services.llm.allergen_infer import infer_allergens_llm

    def fake_run(*args, **kwargs):
        class P:
            allergens = "milk, wheat, eggs"
        return P()

    monkeypatch.setattr(
        "app.services.llm.allergen_infer.run_with_logging",
        fake_run,
    )
    result = infer_allergens_llm(["milk", "flour", "egg"])
    assert set(result) == {"eggs", "milk", "wheat"}


def test_parse_allergen_output():
    from app.services.llm.allergen_infer import _parse_allergen_output

    assert _parse_allergen_output("milk, wheat") == ["milk", "wheat"]
    assert _parse_allergen_output("none") == []
    assert _parse_allergen_output("tree_nuts") == ["tree_nuts"]
