"""
chunker.py
==========
Smart text chunking for the retrieval layer.
Splits documents into overlapping chunks while preserving
paragraph/section boundaries and source metadata.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500       # target tokens (approx chars / 4)
CHUNK_OVERLAP = 100    # overlap tokens
CHAR_PER_TOKEN = 4     # rough approximation


@dataclass
class TextChunk:
    """A single chunk of text with provenance metadata."""
    chunk_id: str
    text: str
    doc_id: str
    page: Optional[int] = None
    section: Optional[str] = None
    start_char: int = 0
    end_char: int = 0
    metadata: dict = None  # type: ignore

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text on double-newlines, filtering empties."""
    paras = re.split(r"\n{2,}", text)
    return [p.strip() for p in paras if p.strip()]


def chunk_text(
    text: str,
    doc_id: str,
    page: Optional[int] = None,
    section: Optional[str] = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """
    Chunk a text block into overlapping segments.

    Strategy:
      1. Split by paragraphs first.
      2. Greedily accumulate paragraphs until chunk_size is reached.
      3. Overlap by including the last `chunk_overlap` tokens from the
         previous chunk at the start of the next.
    """
    if not text.strip():
        return []

    target_chars = chunk_size * CHAR_PER_TOKEN
    overlap_chars = chunk_overlap * CHAR_PER_TOKEN

    paragraphs = _split_into_paragraphs(text)
    chunks: list[TextChunk] = []

    buffer = ""
    buf_start = 0
    char_cursor = 0

    for para in paragraphs:
        if len(buffer) + len(para) + 2 > target_chars and buffer:
            # Flush current buffer as a chunk
            cid = f"{doc_id}_chunk_{len(chunks):04d}"
            chunks.append(TextChunk(
                chunk_id=cid,
                text=buffer.strip(),
                doc_id=doc_id,
                page=page,
                section=section,
                start_char=buf_start,
                end_char=buf_start + len(buffer),
            ))
            # Overlap: keep tail of previous buffer
            if overlap_chars > 0 and len(buffer) > overlap_chars:
                buffer = buffer[-overlap_chars:] + "\n\n" + para
            else:
                buffer = para
            buf_start = char_cursor
        else:
            if buffer:
                buffer += "\n\n" + para
            else:
                buffer = para
                buf_start = char_cursor

        char_cursor += len(para) + 2  # +2 for the double newline

    # Last buffer
    if buffer.strip():
        cid = f"{doc_id}_chunk_{len(chunks):04d}"
        chunks.append(TextChunk(
            chunk_id=cid,
            text=buffer.strip(),
            doc_id=doc_id,
            page=page,
            section=section,
            start_char=buf_start,
            end_char=buf_start + len(buffer),
        ))

    logger.info("Chunked doc_id=%s into %d chunks (target=%d chars)", doc_id, len(chunks), target_chars)
    return chunks


def chunk_document_pages(
    pages: list[dict],
    doc_id: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """
    Chunk a multi-page document (list of {page, text} dicts).
    Each page is chunked independently with its page number preserved.
    """
    all_chunks: list[TextChunk] = []
    for page_data in pages:
        page_num = page_data.get("page", 1)
        text = page_data.get("text", "")
        page_chunks = chunk_text(
            text, doc_id=doc_id, page=page_num,
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(page_chunks)

    # Re-index chunk IDs globally
    for i, chunk in enumerate(all_chunks):
        chunk.chunk_id = f"{doc_id}_chunk_{i:04d}"

    return all_chunks
