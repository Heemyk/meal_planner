"""
Hybrid ingredient matching: when existing_ingredients > k, use embedding retrieval
to fetch top-k candidates for LLM context instead of passing everything.
"""

from typing import List

from app.config import settings
from app.services.embedding import embedding_service

INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD = settings.ingredient_match_full_context_threshold
INGREDIENT_RETRIEVAL_TOP_K = settings.ingredient_retrieval_top_k


def retrieve_similar_ingredients(
    ingredient_text: str,
    existing_ingredients: List[str],
    top_k: int = INGREDIENT_RETRIEVAL_TOP_K,
) -> List[str]:
    """
    Return top-k most similar existing ingredients to ingredient_text.
    Used when len(existing_ingredients) > threshold to reduce LLM context.
    Raises on retrieval failure; no fallback.
    """
    if not existing_ingredients:
        return []
    return embedding_service.retrieve_similar(ingredient_text, existing_ingredients, top_k)
