"""
edit_tracker.py
===============
Captures operator edits on drafts and stores them in SQLite.
Computes structured diffs to feed into the pattern extractor.
"""

from __future__ import annotations

import os
import json
import sqlite3
import difflib
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("FEEDBACK_DB_PATH", "./data/feedback.db")


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get a connection to the feedback SQLite database."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS edits (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id        TEXT NOT NULL,
            draft_type    TEXT NOT NULL,
            original_text TEXT NOT NULL,
            edited_text   TEXT NOT NULL,
            diff_json     TEXT NOT NULL,
            edit_stats    TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learned_patterns (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type  TEXT NOT NULL,
            description   TEXT NOT NULL,
            example_before TEXT,
            example_after  TEXT,
            frequency     INTEGER DEFAULT 1,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_edits_doc ON edits(doc_id);
        CREATE INDEX IF NOT EXISTS idx_patterns_type ON learned_patterns(pattern_type);
    """)
    conn.commit()


def compute_diff(original: str, edited: str) -> dict:
    """
    Compute a structured diff between original and edited text.

    Returns:
        {
            additions: [str],
            deletions: [str],
            modifications: [{original: str, replacement: str}],
            edit_distance: float,   # normalised 0-1
            change_ratio: float,    # % of text changed
        }
    """
    orig_lines = original.splitlines(keepends=True)
    edit_lines = edited.splitlines(keepends=True)

    differ = difflib.unified_diff(orig_lines, edit_lines, lineterm="")
    additions = []
    deletions = []
    modifications = []

    prev_del = None
    for line in differ:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            content = line[1:].strip()
            if content:
                if prev_del is not None:
                    modifications.append({"original": prev_del, "replacement": content})
                    prev_del = None
                else:
                    additions.append(content)
        elif line.startswith("-"):
            if prev_del is not None:
                deletions.append(prev_del)
            prev_del = line[1:].strip()
        else:
            if prev_del is not None:
                deletions.append(prev_del)
                prev_del = None

    if prev_del is not None:
        deletions.append(prev_del)

    # Compute Levenshtein-like ratio
    seq = difflib.SequenceMatcher(None, original, edited)
    change_ratio = 1.0 - seq.ratio()

    return {
        "additions": additions,
        "deletions": deletions,
        "modifications": modifications,
        "edit_distance": round(change_ratio, 4),
        "change_ratio": round(change_ratio * 100, 2),
    }


def save_edit(
    doc_id: str,
    draft_type: str,
    original_text: str,
    edited_text: str,
    db_path: str | None = None,
) -> int:
    """
    Save an operator edit to the database.

    Returns the edit ID.
    """
    diff = compute_diff(original_text, edited_text)
    stats = {
        "additions_count": len(diff["additions"]),
        "deletions_count": len(diff["deletions"]),
        "modifications_count": len(diff["modifications"]),
        "change_ratio": diff["change_ratio"],
    }

    conn = _get_db(db_path)
    cursor = conn.execute(
        """INSERT INTO edits (doc_id, draft_type, original_text, edited_text,
           diff_json, edit_stats, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id,
            draft_type,
            original_text,
            edited_text,
            json.dumps(diff),
            json.dumps(stats),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    edit_id = cursor.lastrowid
    conn.close()

    logger.info("Saved edit #%d for doc=%s (change_ratio=%.1f%%)",
                edit_id, doc_id, diff["change_ratio"])
    return edit_id


def get_edits(
    doc_id: Optional[str] = None,
    draft_type: Optional[str] = None,
    limit: int = 50,
    db_path: str | None = None,
) -> list[dict]:
    """Retrieve edits, optionally filtered by doc_id or draft_type."""
    conn = _get_db(db_path)
    query = "SELECT * FROM edits WHERE 1=1"
    params: list = []
    if doc_id:
        query += " AND doc_id = ?"
        params.append(doc_id)
    if draft_type:
        query += " AND draft_type = ?"
        params.append(draft_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
