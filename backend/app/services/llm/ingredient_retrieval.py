"""
Hybrid ingredient matching: when existing_ingredients > k, use embedding retrieval
to fetch top-k candidates for LLM context instead of passing everything.
"""

from functools import lru_cache
from typing import List

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD = settings.ingredient_match_full_context_threshold
INGREDIENT_RETRIEVAL_TOP_K = settings.ingredient_retrieval_top_k


def _get_embedding_model():
    """Lazy-load a small embedding model. Falls back to TF-IDF if sentence-transformers unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2"), "st"
    except ImportError:
        pass
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        class TFIDFRetriever:
            def __init__(self):
                self.vec = TfidfVectorizer(ngram_range=(1, 2), max_features=256)

            def retrieve(self, query: str, docs: List[str], k: int) -> List[str]:
                if not docs:
                    return []
                all_texts = [query] + docs
                X = self.vec.fit_transform(all_texts)
                q = X[0:1]
                d = X[1:]
                sim = cosine_similarity(q, d)[0]
                idx = sim.argsort()[::-1][:k]
                return [docs[i] for i in idx]

        return TFIDFRetriever(), "tfidf"
    except ImportError:
        return None, None


@lru_cache(maxsize=1)
def _cached_model():
    model, backend = _get_embedding_model()
    if model:
        logger.info("ingredient_retrieval.backend=%s", backend)
    return model, backend


def retrieve_similar_ingredients(
    ingredient_text: str,
    existing_ingredients: List[str],
    top_k: int = INGREDIENT_RETRIEVAL_TOP_K,
) -> List[str]:
    """
    Return top-k most similar existing ingredients to ingredient_text.
    Used when len(existing_ingredients) > threshold to reduce LLM context.
    """
    model, backend = _cached_model()
    if not model or not existing_ingredients:
        return existing_ingredients[:top_k]

    try:
        if backend == "st":
            query_vec = model.encode([ingredient_text])
            doc_vecs = model.encode(existing_ingredients)
            from numpy import dot
            from numpy.linalg import norm
            scores = [float(dot(query_vec[0], v) / (norm(query_vec[0]) * norm(v) + 1e-9)) for v in doc_vecs]
            indexed = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            return [existing_ingredients[i] for i in indexed[:top_k]]
        else:
            return model.retrieve(ingredient_text, existing_ingredients, top_k)
    except Exception as e:
        logger.warning("ingredient_retrieval.fallback error=%s", e)
        return existing_ingredients[:top_k]
