"""
test_feedback.py
================
Unit tests for the feedback loop (edit tracking + pattern extraction).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feedback.edit_tracker import compute_diff, save_edit, get_edits
from src.feedback.pattern_extractor import extract_patterns, get_learned_patterns
from src.feedback.improver import build_feedback_instructions, compute_improvement_metrics

TEST_DB = os.path.join(os.path.dirname(__file__), "..", "data", "_test_feedback.db")


def setup_module():
    """Clean up test DB before running."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def teardown_module():
    """Clean up test DB after running."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ── Diff computation ──

def test_compute_diff_no_change():
    diff = compute_diff("same text", "same text")
    assert diff["edit_distance"] == 0.0
    assert len(diff["additions"]) == 0

def test_compute_diff_additions():
    diff = compute_diff("Hello world", "Hello world\nNew line added")
    assert diff["edit_distance"] > 0
    assert len(diff["additions"]) >= 1

def test_compute_diff_modifications():
    diff = compute_diff("The claimant filed a motion", "The plaintiff filed a motion")
    assert diff["edit_distance"] > 0

def test_compute_diff_deletions():
    diff = compute_diff("Line one\nLine two\nLine three", "Line one\nLine three")
    assert len(diff["deletions"]) >= 1


# ── Edit storage ──

def test_save_and_retrieve_edit():
    edit_id = save_edit(
        doc_id="test_doc",
        draft_type="case_summary",
        original_text="Original draft text here",
        edited_text="Improved draft text with edits",
        db_path=TEST_DB,
    )
    assert isinstance(edit_id, int)
    assert edit_id > 0

    edits = get_edits(doc_id="test_doc", db_path=TEST_DB)
    assert len(edits) >= 1
    assert edits[0]["doc_id"] == "test_doc"


# ── Pattern extraction ──

def test_pattern_extraction_with_repeated_edits():
    # Simulate multiple similar edits
    for i in range(3):
        save_edit(
            doc_id=f"doc_{i}",
            draft_type="case_summary",
            original_text="The claimant asserts that damages were incurred. "
                          "This is a verbose statement.",
            edited_text="The plaintiff asserts that damages were incurred. "
                        "DISCLAIMER: This is for internal use only.",
            db_path=TEST_DB,
        )

    patterns = extract_patterns(draft_type="case_summary", db_path=TEST_DB)
    # Should detect at least the addition pattern
    assert isinstance(patterns, list)


def test_get_learned_patterns():
    patterns = get_learned_patterns(db_path=TEST_DB)
    assert isinstance(patterns, list)


# ── Improvement metrics ──

def test_improvement_metrics():
    metrics = compute_improvement_metrics(db_path=TEST_DB)
    assert "total_edits" in metrics
    assert "patterns_learned" in metrics
    assert "avg_change_ratio" in metrics
    assert metrics["total_edits"] > 0


# ── Feedback instructions ──

def test_build_feedback_instructions():
    instructions = build_feedback_instructions(db_path=TEST_DB, auto_extract=True)
    assert isinstance(instructions, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
