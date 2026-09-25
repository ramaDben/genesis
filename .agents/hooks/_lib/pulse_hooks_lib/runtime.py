"""I/O helpers shared across all genesis hooks.

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
      1. ``GEMINI_PROJECT_DIR`` env var (Antigravity CLI)
      2. ``git rev-parse --show-toplevel``
      3. Walk-up from this file looking for ``.git/``
    """
    val = os.environ.get("GEMINI_PROJECT_DIR")
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
    - **antigravity**: ``toolCall.name`` (camelCase)

    Hasta el 2026-09-05 la rama de Claude leía únicamente ``toolName``.  Claude
    Code envía ``tool_name``, así que el nombre salía vacío y el guardián
    permitía la operación sin siquiera mirarla.  Se aceptan ambas formas para no
    volver a depender de qué dialecto usa cada superficie.

    MISMO FALLO, OTRA SUPERFICIE (medido el 2026-09-12): Antigravity CLI envía
    ``toolCall: {name, args}``.  Ninguna de las formas anteriores lo cubría, así
    que el nombre salía vacío y el guardián de escritura de entonces respondía "no tool name
    found, allowing": **agy escribía en `src/genesis/**` sin gate y sin ruido**.
    Por eso ``toolCall`` se inspecciona para TODOS los clientes y no detrás de un
    ``if client == ...``: hacer depender un control de seguridad de que el flag
    ``--client`` esté bien puesto ya falló dos veces.
    """
    for key in ("tool_name", "toolName"):
        name = payload.get(key)
        if name:
            return str(name)

    # antigravity — https://antigravity.google/docs/hooks/
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict) and tool_call.get("name"):
        return str(tool_call["name"])

    # gemini alternative representation
    call = payload.get("call")
    if isinstance(call, dict) and call.get("name"):
        return str(call["name"])

    return ""


def tool_args(payload: dict[str, Any], client: str) -> dict[str, Any]:
    """Extract tool arguments respecting client dialect.

    - **claude** / **codex**: ``tool_input`` (dict, o str en codex)
    - **gemini**: ``toolArgs`` o ``call.args``
    - **antigravity**: ``toolCall.args``

    Misma corrección que en :func:`tool_name` (2026-09-05): Claude Code envía
    ``tool_input``, no ``toolInput``.  Y misma razón que allí para mirar
    ``toolCall`` sin condicionar al cliente (2026-09-12).
    """
    # antigravity — se mira primero y para todos los clientes: ningún otro
    # dialecto usa esta clave, así que no hay ambigüedad posible.
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        args = tool_call.get("args")
        if isinstance(args, dict):
            return args

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
