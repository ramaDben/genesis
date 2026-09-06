"""I/O helpers shared across all Pulse SDD hooks.

Handles stdin/stdout contract, project-root resolution, and client-dialect
extraction of tool names / arguments so each hook script stays minimal.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------


def project_root() -> Path:
    """Resolve the workspace root using several fallbacks.

    Priority:
      1. ``PULSE_WORKSPACE_ROOT`` env var (Docker / mise)
      2. ``GEMINI_PROJECT_DIR`` env var (Antigravity CLI)
      3. ``git rev-parse --show-toplevel``
      4. Walk-up from this file looking for ``.git/``
    """
    for env_key in ("PULSE_WORKSPACE_ROOT", "GEMINI_PROJECT_DIR"):
        val = os.environ.get(env_key)
        if val:
            return Path(val).resolve()

    git = shutil.which("git")
    if git is not None:
        try:
            proc = subprocess.run(  # noqa: S603
                [git, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(proc.stdout.strip()).resolve()
        except subprocess.CalledProcessError, OSError:
            pass

    # Walk up from _lib/ looking for .git
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / ".git").is_dir():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    return Path.cwd()


# ---------------------------------------------------------------------------
# stdin / stdout contract
# ---------------------------------------------------------------------------


def read_payload() -> dict[str, Any]:
    """Read the JSON payload from stdin.

    Returns an empty dict when stdin is a TTY, empty, or unparseable.
    """
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError, OSError:
        return {}


def emit_response(data: dict[str, Any]) -> None:
    """Write a JSON dict to stdout — the ONLY thing printed to stdout."""
    print(json.dumps(data, default=str))


def log(*args: object) -> None:
    """Print debug info to stderr (never stdout)."""
    print(*args, file=sys.stderr)


# ---------------------------------------------------------------------------
# Client-dialect extraction
# ---------------------------------------------------------------------------


def tool_name(payload: dict[str, Any], client: str) -> str:
    """Extract the tool name respecting client dialect.

    - **claude** / **codex**: ``tool_name`` (snake_case)
    - **gemini**: ``toolName`` o ``call.name``

    Hasta el 2026-09-05 la rama de Claude leía únicamente ``toolName``.  Claude
    Code envía ``tool_name``, así que el nombre salía vacío y el guardián
    permitía la operación sin siquiera mirarla.  Se aceptan ambas formas para no
    volver a depender de qué dialecto usa cada superficie.
    """
    for key in ("tool_name", "toolName"):
        name = payload.get(key)
        if name:
            return str(name)

    # gemini alternative representation
    if client == "gemini":
        call = payload.get("call")
        if isinstance(call, dict):
            return str(call.get("name", ""))

    return ""


def tool_args(payload: dict[str, Any], client: str) -> dict[str, Any]:
    """Extract tool arguments respecting client dialect.

    - **claude** / **codex**: ``tool_input`` (dict, o str en codex)
    - **gemini**: ``toolArgs`` o ``call.args``

    Misma corrección que en :func:`tool_name` (2026-09-05): Claude Code envía
    ``tool_input``, no ``toolInput``.
    """
    if client in ("claude", "codex"):
        for key in ("tool_input", "toolInput"):
            raw = payload.get(key)
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                return {"command": raw}
        return {}

    # gemini
    args = payload.get("toolArgs")
    if isinstance(args, dict):
        return args
    call = payload.get("call")
    if isinstance(call, dict):
        return dict(call.get("args") or {})
    return {}
