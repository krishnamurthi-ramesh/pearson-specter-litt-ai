"""
grounding.py
============
Post-generation grounding verification.
Checks how well the generated draft is supported by the retrieved evidence.
Produces a grounding report that maps draft statements to source evidence.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

from ..retrieval.embedder import embed_texts

logger = logging.getLogger(__name__)


def _extract_sentences(text: str) -> list[str]:
    """Split text into sentences (simple rule-based)."""
    # Split on period followed by space/newline, question mark, exclamation
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def _has_citation(sentence: str) -> bool:
    """Check if a sentence already contains a source citation."""
    return bool(re.search(r"\[Source:.*?\]", sentence))


def verify_grounding(
    draft_text: str,
    evidence: list[dict],
    threshold: float = 0.45,
) -> dict:
    """
    Verify how well a draft is grounded in the provided evidence.

    For each sentence in the draft, compute its semantic similarity
    to each evidence chunk. Flag sentences that aren't well-supported.

    Parameters
    ----------
    draft_text : str
        The generated draft text.
    evidence : list[dict]
        The evidence chunks used for generation.
    threshold : float
        Minimum similarity score to consider a sentence "grounded".

    Returns
    -------
    dict with keys:
        - grounding_score: float (0-1, overall)
        - total_sentences: int
        - grounded_sentences: int
        - ungrounded_sentences: list[str]
        - sentence_details: list[{sentence, best_match, similarity, grounded}]
    """
    sentences = _extract_sentences(draft_text)
    if not sentences or not evidence:
        return {
            "grounding_score": 0.0,
            "total_sentences": len(sentences),
            "grounded_sentences": 0,
            "ungrounded_sentences": sentences,
            "sentence_details": [],
        }

    evidence_texts = [e["text"] for e in evidence]

    # Embed all sentences and evidence chunks
    all_texts = sentences + evidence_texts
    all_embeddings = embed_texts(all_texts)

    sent_embeddings = all_embeddings[:len(sentences)]
    evi_embeddings = all_embeddings[len(sentences):]

    # Compute cosine similarity
    import numpy as np
    sent_arr = np.array(sent_embeddings)
    evi_arr = np.array(evi_embeddings)

    # Normalise
    sent_norm = sent_arr / (np.linalg.norm(sent_arr, axis=1, keepdims=True) + 1e-9)
    evi_norm = evi_arr / (np.linalg.norm(evi_arr, axis=1, keepdims=True) + 1e-9)

    # Similarity matrix: [n_sentences x n_evidence]
    sim_matrix = sent_norm @ evi_norm.T

    details = []
    grounded_count = 0
    ungrounded = []

    for i, sent in enumerate(sentences):
        best_idx = int(np.argmax(sim_matrix[i]))
        best_sim = float(sim_matrix[i, best_idx])
        is_grounded = best_sim >= threshold or _has_citation(sent)

        if is_grounded:
            grounded_count += 1
        else:
            ungrounded.append(sent)

        details.append({
            "sentence": sent,
            "best_match_chunk": evidence[best_idx].get("chunk_id", ""),
            "best_match_doc": evidence[best_idx].get("doc_id", ""),
            "similarity": round(best_sim, 4),
            "grounded": is_grounded,
        })

    score = grounded_count / max(len(sentences), 1)

    return {
        "grounding_score": round(score, 4),
        "total_sentences": len(sentences),
        "grounded_sentences": grounded_count,
        "ungrounded_sentences": ungrounded,
        "sentence_details": details,
    }
