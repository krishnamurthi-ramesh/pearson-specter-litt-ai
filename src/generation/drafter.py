"""
drafter.py
==========
Draft generation using a local Ollama LLM (Mistral 7B by default).
Combines retrieved evidence + structured data into a grounded legal draft.
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from .prompts import (
    SYSTEM_PROMPT,
    get_template,
    format_evidence_blocks,
    format_structured_data,
)


def _call_ollama(prompt: str, system: str = SYSTEM_PROMPT, model: str | None = None) -> str:
    """
    Call the local Ollama instance.
    Falls back to a template-based response if Ollama is unreachable.
    """
    model = model or os.getenv("OLLAMA_MODEL", "mistral:7b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    try:
        import ollama as ollama_lib
        client = ollama_lib.Client(host=host)
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3, "top_p": 0.9, "num_predict": 2048},
        )
        return response["message"]["content"]
    except Exception as exc:
        logger.error("Ollama call failed: %s — using fallback template", exc)
        return _fallback_draft(prompt)


def query_llm(prompt: str, model: str | None = None) -> str:
    """Expose a public query function for the local LLM."""
    return _call_ollama(prompt, model=model)


def _fallback_draft(prompt: str) -> str:
    """
    Simple template-based fallback if LLM is unavailable.
    Extracts key information from the prompt and structures it.
    """
    return (
        "# Draft Output (Template Fallback)\n\n"
        "*Note: The LLM service was unreachable. This is a structured template "
        "populated from extracted data.*\n\n"
        "## Summary\n"
        "Based on the provided documents, the following information was extracted.\n"
        "Please review and edit as needed.\n\n"
        "## Evidence Referenced\n"
        "See the evidence blocks provided in the processing pipeline.\n\n"
        "## Next Steps\n"
        "- Review extracted structured data\n"
        "- Verify key dates and parties\n"
        "- Complete the draft with additional analysis\n"
    )


def generate_draft(
    evidence: list[dict],
    structured_data: dict,
    draft_type: str = "case_summary",
    feedback_instructions: str = "",
    model: Optional[str] = None,
) -> dict:
    """
    Generate a grounded draft from evidence and structured data.

    Parameters
    ----------
    evidence : list[dict]
        Retrieved evidence chunks from the vector store.
    structured_data : dict
        Structured fields extracted from the document.
    draft_type : str
        One of: case_summary, internal_memo, document_checklist.
    feedback_instructions : str
        Additional instructions learned from operator feedback.
    model : str, optional
        Override the Ollama model name.

    Returns
    -------
    dict
        {draft_text, draft_type, evidence_used, generated_at, model}
    """
    template = get_template(draft_type)
    evidence_text = format_evidence_blocks(evidence)
    structured_text = format_structured_data(structured_data)

    prompt = template.format(
        structured_data=structured_text,
        evidence_blocks=evidence_text,
        feedback_instructions=feedback_instructions or "No additional style instructions.",
    )

    logger.info("Generating draft type=%s with %d evidence chunks", draft_type, len(evidence))
    draft_text = _call_ollama(prompt, model=model)

    return {
        "draft_text": draft_text,
        "draft_type": draft_type,
        "evidence_used": [
            {
                "chunk_id": e.get("chunk_id", ""),
                "doc_id": e.get("doc_id", ""),
                "page": e.get("page", 0),
                "similarity": e.get("similarity", 0),
            }
            for e in evidence
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model or os.getenv("OLLAMA_MODEL", "mistral:7b"),
    }
