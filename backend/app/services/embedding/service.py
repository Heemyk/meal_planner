"""
Embedding and vector retrieval service.
Single resource/instance reused across concurrent calls; access serialized via a lock.
Loads the model once; no per-retrieval instantiation.
"""

import threading
from typing import List

from app.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Single-instance embedding/retrieval service. Model loaded once; all retrievals
    serialized via lock so concurrent callers are queued naturally.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._backend: str | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._backend = "st"
                logger.info("embedding_service.loaded backend=sentence_transformers")
            except ImportError:
                pass
            if self._model is None:
                try:
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.metrics.pairwise import cosine_similarity

                    class _TFIDFRetriever:
                        def retrieve(self, query: str, docs: List[str], k: int) -> List[str]:
                            if not docs:
                                return []
                            vec = TfidfVectorizer(
                                ngram_range=(1, 2), max_features=256, lowercase=True
                            )
                            all_texts = [query] + docs
                            X = vec.fit_transform(all_texts)
                            q = X[0:1]
                            d = X[1:]
                            sim = cosine_similarity(q, d)[0]
                            idx = sim.argsort()[::-1][:k]
                            return [docs[i] for i in idx]

                    self._model = _TFIDFRetriever()
                    self._backend = "tfidf"
                    logger.info("embedding_service.loaded backend=tfidf")
                except ImportError:
                    raise RuntimeError(
                        "No embedding backend available. Install sentence-transformers or scikit-learn."
                    ) from None

    def retrieve_similar(
        self,
        query: str,
        docs: List[str],
        k: int,
    ) -> List[str]:
        """
        Return top-k most similar docs to query. Thread-safe; serialized via lock.
        """
        if not docs:
            return []
        self._ensure_loaded()

        with self._lock:
            if self._backend == "st":
                import numpy as np

                query_vec = self._model.encode([query])
                doc_vecs = self._model.encode(docs)
                scores = [
                    float(
                        np.dot(query_vec[0], v)
                        / (np.linalg.norm(query_vec[0]) * np.linalg.norm(v) + 1e-9)
                    )
                    for v in doc_vecs
                ]
                indexed = sorted(
                    range(len(scores)), key=lambda i: scores[i], reverse=True
                )
                return [docs[i] for i in indexed[:k]]
            else:
                return self._model.retrieve(query, docs, k)


# Single shared instance
embedding_service = EmbeddingService()
