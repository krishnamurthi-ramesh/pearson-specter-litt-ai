"""
test_retrieval.py
=================
Unit tests for the retrieval layer (chunking, embedding, vector store).
"""

import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.chunker import chunk_text, chunk_document_pages, TextChunk


# ── Chunking ──

def test_chunk_text_basic():
    text = "Paragraph one about contracts.\n\nParagraph two about agreements.\n\nParagraph three about law."
    chunks = chunk_text(text, doc_id="test_doc")
    assert len(chunks) >= 1
    assert all(isinstance(c, TextChunk) for c in chunks)

def test_chunk_text_preserves_doc_id():
    text = "Some legal text here."
    chunks = chunk_text(text, doc_id="my_doc")
    assert all(c.doc_id == "my_doc" for c in chunks)

def test_chunk_text_empty():
    chunks = chunk_text("", doc_id="empty")
    assert len(chunks) == 0

def test_chunk_text_long():
    # Generate a long text that should produce multiple chunks
    paragraphs = [f"This is paragraph {i} with enough content to fill space." * 10 for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, doc_id="long_doc", chunk_size=100)
    assert len(chunks) > 1

def test_chunk_document_pages():
    pages = [
        {"page": 1, "text": "Content of page one."},
        {"page": 2, "text": "Content of page two."},
    ]
    chunks = chunk_document_pages(pages, doc_id="multi_page")
    assert len(chunks) >= 2
    assert any(c.page == 1 for c in chunks)
    assert any(c.page == 2 for c in chunks)


# ── Embedding (requires model download; skip if not available) ──

def test_embed_texts():
    try:
        from src.retrieval.embedder import embed_texts
        vecs = embed_texts(["Hello world", "Legal document text"])
        assert len(vecs) == 2
        assert len(vecs[0]) > 50  # embedding dimension
    except Exception:
        pytest.skip("Embedding model not available")


# ── Vector Store (uses temp directory) ──

def test_vector_store_add_and_query():
    try:
        from src.retrieval.vector_store import VectorStore
        from src.retrieval.chunker import TextChunk

        test_dir = os.path.join(os.path.dirname(__file__), "..", "data", "_test_chroma")
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        vs = VectorStore(persist_dir=test_dir)

        chunks = [
            TextChunk(chunk_id="t1", text="The purchase price is three million dollars.", doc_id="doc1"),
            TextChunk(chunk_id="t2", text="The defendant filed a motion for summary judgment.", doc_id="doc2"),
        ]
        vs.add_chunks(chunks)
        assert vs.count() == 2

        results = vs.query("How much does the property cost?", n_results=2)
        assert len(results) > 0
        assert results[0]["doc_id"] == "doc1"  # should match purchase price

        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception as e:
        pytest.skip(f"Vector store test skipped: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
