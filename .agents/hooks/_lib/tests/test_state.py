from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from pulse_hooks_lib.state import read_active_change, read_phase


def test_read_phase_no_db(monkeypatch):
    def mock_project_root():
        return Path("/non/existent/path")

    monkeypatch.setattr("pulse_hooks_lib.state.project_root", mock_project_root)
    assert read_phase() == "unknown"


def test_read_phase_with_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / ".pulse" / "state.sqlite"
        db_path.parent.mkdir(parents=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE project_state (id TEXT PRIMARY KEY, json TEXT)")
            state_json = json.dumps({"current_phase": "design"})
            conn.execute(
                "INSERT INTO project_state (id, json) VALUES (?, ?)", ("singleton", state_json)
            )

        def mock_project_root():
            return Path(tmpdir)

        monkeypatch.setattr("pulse_hooks_lib.state.project_root", mock_project_root)
        assert read_phase() == "design"


def test_read_active_change_no_db(monkeypatch):
    def mock_project_root():
        return Path("/non/existent/path")

    monkeypatch.setattr("pulse_hooks_lib.state.project_root", mock_project_root)
    assert read_active_change() is None


def test_read_active_change_with_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        pulse_dir = Path(tmpdir) / ".pulse"
        db_path = pulse_dir / "state.sqlite"
        db_path.parent.mkdir(parents=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE project_state (id TEXT PRIMARY KEY, json TEXT)")
            state_json = json.dumps({"active_change_slug": "test-slug"})
            conn.execute(
                "INSERT INTO project_state (id, json) VALUES (?, ?)", ("singleton", state_json)
            )

        change_dir = pulse_dir / "changes" / "test-slug"
        change_dir.mkdir(parents=True)
        state_yaml = change_dir / "state.yaml"
        # state.py uses json.loads, so we write JSON here
        state_yaml.write_text(json.dumps({"current_phase": "apply", "domain": "core"}))

        def mock_project_root():
            return Path(tmpdir)

        monkeypatch.setattr("pulse_hooks_lib.state.project_root", mock_project_root)

        change = read_active_change()
        assert change is not None
        assert change["slug"] == "test-slug"
        assert change["current_phase"] == "apply"
        assert change["domain"] == "core"
