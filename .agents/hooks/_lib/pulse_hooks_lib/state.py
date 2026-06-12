"""Direct filesystem readers for Pulse SDD state.

Reads ``.pulse/state.sqlite`` (project state) and ``.pulse/changes/``
(active changes) without Docker or MCP — pure stdlib ``sqlite3`` +
``json`` so the hook stays sub-50 ms.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pulse_hooks_lib.runtime import log, project_root

# The SQLite row is always stored under id = 'singleton'
_ROW_ID = "singleton"


# ---------------------------------------------------------------------------
# Project state (from state.sqlite)
# ---------------------------------------------------------------------------


def _db_path() -> Path:
    """Resolve the SQLite database path."""
    return project_root() / ".pulse" / "state.sqlite"


def _load_state_json() -> dict[str, Any]:
    """Load the raw ProjectState JSON from SQLite.

    Returns empty dict on any failure (missing DB, missing row, etc.).
    """
    db = _db_path()
    if not db.exists():
        return {}
    try:
        conn = sqlite3.connect(str(db), timeout=2)
        try:
            row = conn.execute(
                "SELECT json FROM project_state WHERE id = ?",
                (_ROW_ID,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return {}
        return json.loads(row[0])  # type: ignore[no-any-return]
    except (sqlite3.Error, json.JSONDecodeError, OSError) as exc:
        log(f"pulse-hooks: state.sqlite read error: {exc}")
        return {}


def read_phase() -> str:
    """Return the current SDD phase string.

    Reads from ``.pulse/state.sqlite`` → ``project_state.json`` →
    ``current_phase``.  Falls back to ``"unknown"`` when unavailable.
    """
    state = _load_state_json()
    return str(state.get("current_phase", "unknown"))


def read_active_change_slug() -> str | None:
    """Return the active change slug from project state, or None."""
    state = _load_state_json()
    return state.get("active_change_slug")


# ---------------------------------------------------------------------------
# Active change (from filesystem: .pulse/changes/<slug>/state.yaml)
# ---------------------------------------------------------------------------


def read_active_change() -> dict[str, Any] | None:
    """Read active change info from ``.pulse/changes/<slug>/state.yaml``.

    Returns a dict with ``slug``, ``domain``, ``current_phase``, and
    ``awaiting_approval`` keys, or *None* when no active change exists.
    """
    slug = read_active_change_slug()
    if not slug:
        return None

    state_yaml = project_root() / ".pulse" / "changes" / slug / "state.yaml"
    if not state_yaml.exists():
        return None

    try:
        raw = json.loads(state_yaml.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log(f"pulse-hooks: change state.yaml read error: {exc}")
        return None

    current_phase = raw.get("current_phase", "unknown")
    design_approved_at = raw.get("design_approved_at")
    awaiting = current_phase == "design" and design_approved_at is None

    return {
        "slug": slug,
        "domain": raw.get("domain", ""),
        "current_phase": current_phase,
        "awaiting_approval": awaiting,
    }
