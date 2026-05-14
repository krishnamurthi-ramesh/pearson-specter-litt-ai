"""
preprocessor.py
===============
Text cleaning and normalisation applied after raw extraction.
Fixes common OCR artefacts, normalises whitespace, and segments
the text into sections for downstream processing.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Apply a battery of cleaning rules to raw extracted text.

    - Fix common OCR substitutions (e.g. 'l' ↔ '1', '0' ↔ 'O')
    - Normalise whitespace
    - Remove control characters
    - Fix broken hyphenation from line wraps
    """
    if not text:
        return ""

    # Remove control characters (keep newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Fix broken hyphenation:  "docu-\nment" → "document"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Collapse runs of 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Normalise horizontal whitespace (but keep newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # Strip leading/trailing whitespace on each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def detect_sections(text: str) -> list[dict]:
    """
    Attempt to split text into labelled sections.

    Looks for patterns like:
        SECTION 1: ...
        Article II - ...
        1. TITLE
        ALL-CAPS HEADER

    Returns a list of {title, body, start_char, end_char}.
    """
    # Pattern: numbered or titled section headers
    header_pattern = re.compile(
        r"^(?:"
        r"(?:SECTION|ARTICLE|PART|CLAUSE)\s+[\dIVXivx]+[.:)\-]?\s*"  # SECTION 1:
        r"|(?:\d+\.?\s+[A-Z][A-Z ]{3,})"                              # 1. TITLE
        r"|(?:[A-Z][A-Z ]{5,})"                                        # ALL CAPS HEADER (6+ chars)
        r")",
        re.MULTILINE,
    )

    matches = list(header_pattern.finditer(text))

    if not matches:
        # No sections detected — return whole text as one section
        return [{"title": "Full Document", "body": text, "start_char": 0, "end_char": len(text)}]

    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group().strip().rstrip(":").rstrip("-").strip()
        body = text[m.end():end].strip()
        sections.append({
            "title": title,
            "body": body,
            "start_char": start,
            "end_char": end,
        })

    return sections


def compute_quality_score(text: str) -> float:
    """
    Heuristic quality score (0-1) for extracted text.
    A score < 0.5 usually means OCR quality was poor.
    """
    if not text:
        return 0.0

    total = len(text)

    # Ratio of printable ASCII + common Unicode
    printable = sum(1 for c in text if c.isprintable() or c in "\n\t")
    printable_ratio = printable / total

    # Ratio of dictionary-like words (simple heuristic: 3+ alpha chars)
    words = text.split()
    word_like = sum(1 for w in words if len(w) >= 3 and w.isalpha()) / max(len(words), 1)

    score = 0.5 * printable_ratio + 0.5 * word_like
    return round(min(1.0, score), 3)
