"""
structured_extractor.py
=======================
Extract structured fields from raw legal text using regex patterns
and (optionally) spaCy NER.

Extracted fields:
  - parties (names of people / organisations)
  - dates
  - case / reference numbers
  - monetary amounts
  - addresses (basic)
  - document type classification
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex pattern library
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # "January 15, 2024" / "Jan 15, 2024"
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
    # "15/01/2024" or "01-15-2024"
    r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
    # "2024-01-15"
    r"\b\d{4}-\d{2}-\d{2}\b",
]

_CASE_NUMBER_PATTERNS = [
    r"\b(?:Case|Cause|Docket|File|Ref(?:erence)?)\s*(?:No\.?|Number|#)\s*[:.]?\s*([\w\-/]+)",
    r"\b(\d{2,4}[\-/](?:CV|CR|CIV|AP|BR)[\-/]\d{3,})\b",
]

_MONEY_PATTERN = r"\$[\d,]+(?:\.\d{2})?"

_PARTY_KEYWORDS = [
    r"(?:Plaintiff|Defendant|Petitioner|Respondent|Appellant|Appellee|Claimant)\s*[:.]?\s*(.+)",
    r"(?:Between|BETWEEN)\s+(.+?)\s+(?:and|AND)\s+(.+?)(?:\n|$)",
    r"(?:IN THE MATTER OF|In the Matter of|RE:|Re:)\s+(.+)",
]


def _find_all(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> list[str]:
    """Run multiple regex patterns and return all unique matches."""
    results = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags):
            val = m.group(0).strip()
            if val and val not in results:
                results.append(val)
    return results


def _classify_document_type(text: str) -> str:
    """Simple keyword-based classification of document type."""
    text_lower = text[:3000].lower()  # Only scan the first 3 KB
    scoreboard: dict[str, int] = {
        "contract": 0,
        "complaint": 0,
        "motion": 0,
        "order": 0,
        "notice": 0,
        "memorandum": 0,
        "deed": 0,
        "affidavit": 0,
        "subpoena": 0,
        "settlement": 0,
    }
    keywords = {
        "contract":    ["agreement", "contract", "terms and conditions", "parties agree", "hereby"],
        "complaint":   ["complaint", "plaintiff", "defendant", "cause of action", "prayer for relief"],
        "motion":      ["motion", "movant", "hereby moves", "relief sought"],
        "order":       ["court order", "it is ordered", "the court finds", "judgment"],
        "notice":      ["notice", "hereby notified", "take notice"],
        "memorandum":  ["memorandum", "memo", "internal memo", "to:", "from:", "subject:"],
        "deed":        ["deed", "property", "grantor", "grantee", "convey"],
        "affidavit":   ["affidavit", "sworn", "deponent", "notary"],
        "subpoena":    ["subpoena", "commanded to appear", "duces tecum"],
        "settlement":  ["settlement", "release", "mutual agreement", "consideration"],
    }
    for doc_type, words in keywords.items():
        for w in words:
            if w in text_lower:
                scoreboard[doc_type] += 1

    best = max(scoreboard, key=scoreboard.get)  # type: ignore[arg-type]
    return best if scoreboard[best] > 0 else "unknown"


def extract_structured_data(text: str) -> dict[str, Any]:
    """
    Extract structured fields from legal text.

    Returns a dict with keys: dates, case_numbers, parties, amounts,
    document_type, key_phrases.
    """
    if not text:
        return {
            "dates": [],
            "case_numbers": [],
            "parties": [],
            "amounts": [],
            "document_type": "unknown",
            "key_phrases": [],
        }

    dates = _find_all(_DATE_PATTERNS, text)

    # Case numbers — extract the captured group if present
    case_numbers = []
    for pat in _CASE_NUMBER_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = (m.group(1) if m.lastindex else m.group(0)).strip()
            if val and val not in case_numbers:
                case_numbers.append(val)

    # Parties
    parties = []
    for pat in _PARTY_KEYWORDS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            for g in m.groups():
                if g:
                    name = g.strip().rstrip(".,;:")
                    if name and name not in parties and len(name) < 200:
                        parties.append(name)

    # Monetary amounts
    amounts = re.findall(_MONEY_PATTERN, text)
    amounts = list(dict.fromkeys(amounts))  # deduplicate preserving order

    # Document type
    doc_type = _classify_document_type(text)

    # Key phrases — extract short bold/capitalised phrases
    key_phrases = re.findall(r"\b[A-Z][A-Z ]{4,30}\b", text[:5000])
    key_phrases = list(dict.fromkeys(key_phrases))[:15]  # top 15 unique

    return {
        "dates": dates,
        "case_numbers": case_numbers,
        "parties": parties,
        "amounts": amounts,
        "document_type": doc_type,
        "key_phrases": key_phrases,
    }
