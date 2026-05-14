"""
improver.py
===========
Applies learned patterns to improve future draft generation.
Builds a "style guide" prompt from accumulated feedback that is
injected into the LLM prompt before generating a new draft.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from .pattern_extractor import get_learned_patterns, extract_patterns
from .edit_tracker import get_edits

logger = logging.getLogger(__name__)


def build_feedback_instructions(
    draft_type: Optional[str] = None,
    db_path: str | None = None,
    auto_extract: bool = True,
) -> str:
    """
    Build a natural-language "style guide" from learned patterns.

    This string is injected into the LLM prompt to steer future drafts
    toward operator preferences.

    Parameters
    ----------
    draft_type : str, optional
        Filter patterns by draft type.
    db_path : str, optional
        Override the database path.
    auto_extract : bool
        If True, re-extract patterns from edits before building instructions.

    Returns
    -------
    str
        Human-readable instructions for the LLM.
    """
    if auto_extract:
        extract_patterns(draft_type=draft_type, db_path=db_path)

    patterns = get_learned_patterns(db_path=db_path)

    if not patterns:
        return ""

    lines = [
        "IMPORTANT — OPERATOR PREFERENCES (learned from previous edits):",
        "Apply the following style guidelines when generating this draft:\n",
    ]

    for i, p in enumerate(patterns, 1):
        ptype = p.get("pattern_type", "general")
        desc = p.get("description", "")
        freq = p.get("frequency", 1)
        before = p.get("example_before", "")
        after = p.get("example_after", "")

        line = f"{i}. [{ptype.upper()}] {desc} (observed {freq}x)"
        if before and after:
            line += f"\n   Example: '{before}' → '{after}'"
        lines.append(line)

    return "\n".join(lines)


def compute_improvement_metrics(
    db_path: str | None = None,
) -> dict:
    """
    Compute metrics showing how drafts have improved over time.

    Returns:
        {
            total_edits: int,
            avg_change_ratio: float,
            trend: [float],       # change_ratio over time (should decrease)
            patterns_learned: int,
            improvement_detected: bool,
        }
    """
    edits = get_edits(limit=200, db_path=db_path)
    patterns = get_learned_patterns(db_path=db_path)

    if not edits:
        return {
            "total_edits": 0,
            "avg_change_ratio": 0.0,
            "trend": [],
            "patterns_learned": 0,
            "improvement_detected": False,
        }

    # Extract change ratios in chronological order
    ratios = []
    for edit in reversed(edits):  # oldest first
        stats = json.loads(edit["edit_stats"])
        ratios.append(stats.get("change_ratio", 0.0))

    avg = sum(ratios) / len(ratios)

    # Check if the trend is downward (improvement)
    # Compare first half vs. second half average
    mid = len(ratios) // 2
    improvement = False
    if mid > 0:
        first_half_avg = sum(ratios[:mid]) / mid
        second_half_avg = sum(ratios[mid:]) / (len(ratios) - mid)
        improvement = second_half_avg < first_half_avg

    return {
        "total_edits": len(edits),
        "avg_change_ratio": round(avg, 2),
        "trend": ratios,
        "patterns_learned": len(patterns),
        "improvement_detected": improvement,
    }
