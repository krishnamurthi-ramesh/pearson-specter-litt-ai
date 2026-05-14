"""
embedder.py
===========
Embedding wrapper around sentence-transformers.
Encodes text chunks into dense vectors for semantic search.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_model = None  # lazy-loaded singleton


def _get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Lazy-load the sentence-transformer model (singleton)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
        logger.info("Embedding model loaded (dim=%d)", _model.get_sentence_embedding_dimension())
    return _model


def embed_texts(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> list[list[float]]:
    """
    Embed a batch of texts.

    Returns a list of float vectors, one per input text.
    """
    if not texts:
        return []

    model = _get_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [vec.tolist() for vec in embeddings]


def embed_single(text: str, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """Embed a single text string."""
    return embed_texts([text], model_name)[0]
