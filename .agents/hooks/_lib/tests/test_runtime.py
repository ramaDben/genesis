from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from pulse_hooks_lib.runtime import project_root, read_payload, tool_name


def test_read_payload_empty_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    payload = read_payload()
    assert payload == {}


def test_read_payload_valid_json(monkeypatch):
    data = {"key": "value"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(data)))
    payload = read_payload()
    assert payload == data


def test_tool_name_gemini():
    # Format 1: toolName
    payload1 = {"toolName": "my_tool"}
    assert tool_name(payload1, "gemini") == "my_tool"

    # Format 2: call.name
    payload2 = {"call": {"name": "my_tool"}}
    assert tool_name(payload2, "gemini") == "my_tool"


def test_tool_name_claude():
    payload = {"toolName": "my_tool"}
    assert tool_name(payload, "claude") == "my_tool"


def test_tool_name_codex():
    payload = {"tool_name": "my_tool"}
    assert tool_name(payload, "codex") == "my_tool"


def test_project_root_env_var(monkeypatch):
    monkeypatch.setattr("os.environ", {"PULSE_WORKSPACE_ROOT": "/custom/path"})
    assert project_root() == Path("/custom/path").resolve()
