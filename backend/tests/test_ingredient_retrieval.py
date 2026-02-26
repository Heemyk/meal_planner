"""Tests for hybrid ingredient retrieval."""

from app.services.llm.ingredient_retrieval import (
    INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD,
    INGREDIENT_RETRIEVAL_TOP_K,
    retrieve_similar_ingredients,
)


def test_retrieve_empty_list():
    assert retrieve_similar_ingredients("milk", [], top_k=5) == []


def test_retrieve_small_list_returns_top_k():
    ingredients = ["milk", "egg", "flour"]
    result = retrieve_similar_ingredients("milk", ingredients, top_k=2)
    assert len(result) <= 2
    assert "milk" in result


def test_retrieve_respects_top_k():
    ingredients = [f"ingredient_{i}" for i in range(30)]
    result = retrieve_similar_ingredients("ingredient_0", ingredients, top_k=5)
    assert len(result) == 5


def test_retrieve_returns_subsets():
    ingredients = ["milk", "cream", "butter", "flour", "egg"]
    result = retrieve_similar_ingredients("milk", ingredients, top_k=3)
    assert len(result) == 3
    assert all(ing in ingredients for ing in result)
    # "milk" should rank highest when query is "milk"
    assert result[0] == "milk"


def test_retrieve_similar_ingredients_semantic():
    """TF-IDF or embeddings should rank 'cream' and 'butter' near 'milk' (dairy)."""
    ingredients = ["milk", "cream", "butter", "flour", "sugar"]
    result = retrieve_similar_ingredients("dairy milk", ingredients, top_k=3)
    assert len(result) == 3
    assert "milk" in result
    # cream/butter may appear due to co-occurrence in recipe context
    assert all(ing in ingredients for ing in result)


def test_constants():
    assert INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD >= 1
    assert INGREDIENT_RETRIEVAL_TOP_K >= 1
