"""
vector_store.py
===============
ChromaDB-backed vector store for document chunks.
Provides add / query / delete operations with metadata filtering.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings

from .chunker import TextChunk
from .embedder import embed_texts, embed_single

logger = logging.getLogger(__name__)

COLLECTION_NAME = "legal_documents"


class VectorStore:
    """Thin wrapper around a ChromaDB collection."""

    def __init__(self, persist_dir: Optional[str] = None):
        persist_dir = persist_dir or os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("VectorStore ready  collection=%s  count=%d",
                     COLLECTION_NAME, self.collection.count())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[TextChunk]) -> int:
        """
        Embed and upsert a batch of TextChunk objects.
        Returns the number of chunks added.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        ids = [c.chunk_id for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "page": c.page or 0,
                "section": c.section or "",
                "start_char": c.start_char,
                "end_char": c.end_char,
            }
            for c in chunks
        ]

        embeddings = embed_texts(texts)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Upserted %d chunks (total collection count: %d)",
                     len(chunks), self.collection.count())
        return len(chunks)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        doc_id_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search over the collection.

        Returns a list of dicts:
          {chunk_id, text, doc_id, page, section, similarity}
        sorted by relevance (best first).
        """
        query_embedding = embed_single(query_text)

        where_filter = None
        if doc_id_filter:
            where_filter = {"doc_id": doc_id_filter}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for i in range(len(results["ids"][0])):
            dist = results["distances"][0][i]
            similarity = 1.0 - dist  # cosine distance → similarity
            hits.append({
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "doc_id": results["metadatas"][0][i].get("doc_id", ""),
                "page": results["metadatas"][0][i].get("page", 0),
                "section": results["metadatas"][0][i].get("section", ""),
                "similarity": round(similarity, 4),
            })

        return hits

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(self, doc_id: str) -> int:
        """Remove all chunks for a given doc_id."""
        existing = self.collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])
            logger.info("Deleted %d chunks for doc_id=%s", len(existing["ids"]), doc_id)
            return len(existing["ids"])
        return 0

    def count(self) -> int:
        return self.collection.count()

    def list_documents(self) -> list[str]:
        """Return unique doc_ids in the store."""
        all_meta = self.collection.get(include=["metadatas"])
        doc_ids = set()
        for m in all_meta["metadatas"]:
            doc_ids.add(m.get("doc_id", ""))
        return sorted(doc_ids)
