"""Embedding and vector retrieval service. Single instance, serialized access."""

from app.services.embedding.service import embedding_service

__all__ = ["embedding_service"]
