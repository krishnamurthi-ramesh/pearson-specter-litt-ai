"""
pattern_extractor.py
====================
Analyses accumulated operator edits to discover reusable patterns.
Patterns are categorised into:
  - tone       : formality, verbosity preferences
  - structure   : section ordering, required sections
  - terminology : preferred legal terms
  - additions   : content that is consistently added
  - deletions   : content that is consistently removed
"""

from __future__ import annotations

import json
import re
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from .edit_tracker import get_edits, _get_db

logger = logging.getLogger(__name__)


def _analyse_additions(edits: list[dict]) -> list[dict]:
    """Find consistently added phrases across edits."""
    all_additions = []
    for edit in edits:
        diff = json.loads(edit["diff_json"])
        all_additions.extend(diff.get("additions", []))

    # Find recurring additions (appear in ≥2 edits)
    counter = Counter(all_additions)
    patterns = []
    for phrase, count in counter.most_common(10):
        if count >= 2 and len(phrase) > 10:
            patterns.append({
                "pattern_type": "addition",
                "description": f"Operators frequently add: '{phrase[:100]}'",
                "example_before": "",
                "example_after": phrase,
                "frequency": count,
            })
    return patterns


def _analyse_deletions(edits: list[dict]) -> list[dict]:
    """Find consistently removed phrases."""
    all_deletions = []
    for edit in edits:
        diff = json.loads(edit["diff_json"])
        all_deletions.extend(diff.get("deletions", []))

    counter = Counter(all_deletions)
    patterns = []
    for phrase, count in counter.most_common(10):
        if count >= 2 and len(phrase) > 10:
            patterns.append({
                "pattern_type": "deletion",
                "description": f"Operators frequently remove: '{phrase[:100]}'",
                "example_before": phrase,
                "example_after": "",
                "frequency": count,
            })
    return patterns


def _analyse_modifications(edits: list[dict]) -> list[dict]:
    """Find consistent replacements (terminology preferences)."""
    all_mods = []
    for edit in edits:
        diff = json.loads(edit["diff_json"])
        all_mods.extend(diff.get("modifications", []))

    # Group by original text
    replacement_map: dict[str, list[str]] = {}
    for mod in all_mods:
        orig = mod["original"].strip().lower()
        repl = mod["replacement"].strip()
        replacement_map.setdefault(orig, []).append(repl)

    patterns = []
    for orig, replacements in replacement_map.items():
        if len(replacements) >= 2:
            # Take the most common replacement
            most_common = Counter(replacements).most_common(1)[0]
            patterns.append({
                "pattern_type": "terminology",
                "description": f"Replace '{orig}' with '{most_common[0][:100]}'",
                "example_before": orig,
                "example_after": most_common[0],
                "frequency": most_common[1],
            })
    return patterns


def _analyse_tone(edits: list[dict]) -> list[dict]:
    """Detect tone preferences: formal vs. concise, passive vs. active."""
    patterns = []
    length_changes = []

    for edit in edits:
        orig_len = len(edit["original_text"])
        edit_len = len(edit["edited_text"])
        if orig_len > 0:
            length_changes.append(edit_len / orig_len)

    if length_changes:
        avg_ratio = sum(length_changes) / len(length_changes)
        if avg_ratio < 0.85:
            patterns.append({
                "pattern_type": "tone",
                "description": "Operators prefer more CONCISE drafts (avg reduction to "
                               f"{avg_ratio:.0%} of original length)",
                "example_before": "",
                "example_after": "",
                "frequency": len(length_changes),
            })
        elif avg_ratio > 1.15:
            patterns.append({
                "pattern_type": "tone",
                "description": "Operators prefer more DETAILED drafts (avg expansion to "
                               f"{avg_ratio:.0%} of original length)",
                "example_before": "",
                "example_after": "",
                "frequency": len(length_changes),
            })

    return patterns


def _analyse_structure(edits: list[dict]) -> list[dict]:
    """Detect structural preferences (added sections, reordering)."""
    patterns = []
    added_headings = []

    for edit in edits:
        diff = json.loads(edit["diff_json"])
        for addition in diff.get("additions", []):
            # Check if it looks like a section heading
            if re.match(r"^(?:\d+\.|#{1,3}|[A-Z][A-Z ]{3,})", addition.strip()):
                added_headings.append(addition.strip())

    counter = Counter(added_headings)
    for heading, count in counter.most_common(5):
        if count >= 2:
            patterns.append({
                "pattern_type": "structure",
                "description": f"Operators frequently add section: '{heading}'",
                "example_before": "",
                "example_after": heading,
                "frequency": count,
            })

    return patterns


def extract_patterns(
    draft_type: Optional[str] = None,
    db_path: str | None = None,
) -> list[dict]:
    """
    Analyse all stored edits and extract reusable patterns.

    Returns a list of pattern dicts and also saves them to the DB.
    """
    edits = get_edits(draft_type=draft_type, limit=200, db_path=db_path)

    if not edits:
        logger.info("No edits found — no patterns to extract")
        return []

    logger.info("Analysing %d edits for patterns", len(edits))

    all_patterns = []
    all_patterns.extend(_analyse_additions(edits))
    all_patterns.extend(_analyse_deletions(edits))
    all_patterns.extend(_analyse_modifications(edits))
    all_patterns.extend(_analyse_tone(edits))
    all_patterns.extend(_analyse_structure(edits))

    # Persist patterns
    if all_patterns:
        _save_patterns(all_patterns, db_path)

    logger.info("Extracted %d patterns from %d edits", len(all_patterns), len(edits))
    return all_patterns


def _save_patterns(patterns: list[dict], db_path: str | None = None):
    """Upsert patterns into the learned_patterns table."""
    conn = _get_db(db_path)
    now = datetime.now(timezone.utc).isoformat()

    for p in patterns:
        # Check if a similar pattern already exists
        existing = conn.execute(
            "SELECT id, frequency FROM learned_patterns WHERE description = ?",
            (p["description"],),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE learned_patterns SET frequency = ?, updated_at = ? WHERE id = ?",
                (p["frequency"], now, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO learned_patterns
                   (pattern_type, description, example_before, example_after,
                    frequency, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["pattern_type"],
                    p["description"],
                    p.get("example_before", ""),
                    p.get("example_after", ""),
                    p["frequency"],
                    now, now,
                ),
            )

    conn.commit()
    conn.close()


def get_learned_patterns(db_path: str | None = None) -> list[dict]:
    """Retrieve all learned patterns from the database."""
    conn = _get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM learned_patterns ORDER BY frequency DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
