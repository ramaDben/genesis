from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from pulse_hooks_lib.runtime import project_root, read_payload, tool_args, tool_name


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


# ---------------------------------------------------------------------------
# Regresión: el dialecto real de Claude Code (2026-09-05)
#
# Claude Code envía `tool_name` / `tool_input` en snake_case, no las formas
# camelCase que asumía la rama "claude".  Con el nombre vacío el guardián de
# escritura registraba "no tool name found, allowing" y **permitía todo** — un
# fail-open silencioso en el único control mecánico del ciclo SDD.
# ---------------------------------------------------------------------------


def test_tool_name_claude_snake_case():
    """Es la forma que Claude Code envía de verdad."""
    payload = {"tool_name": "Write", "tool_input": {"file_path": "src/x.py"}}
    assert tool_name(payload, "claude") == "Write"


def test_tool_args_claude_snake_case():
    payload = {"tool_name": "Write", "tool_input": {"file_path": "src/x.py"}}
    assert tool_args(payload, "claude") == {"file_path": "src/x.py"}


def test_tool_args_claude_camel_case_sigue_funcionando():
    """No se rompe a quien ya emitía camelCase."""
    payload = {"toolName": "Write", "toolInput": {"file_path": "src/x.py"}}
    assert tool_name(payload, "claude") == "Write"
    assert tool_args(payload, "claude") == {"file_path": "src/x.py"}


def test_tool_args_codex_command_string():
    payload = {"tool_name": "shell", "tool_input": "ls -la"}
    assert tool_args(payload, "codex") == {"command": "ls -la"}


def test_tool_args_gemini_no_se_ve_afectado():
    assert tool_args({"toolArgs": {"path": "a"}}, "gemini") == {"path": "a"}
    assert tool_args({"call": {"args": {"path": "b"}}}, "gemini") == {"path": "b"}


def test_project_root_env_var(monkeypatch):
    monkeypatch.setattr("os.environ", {"GEMINI_PROJECT_DIR": "/custom/path"})
    assert project_root() == Path("/custom/path").resolve()
