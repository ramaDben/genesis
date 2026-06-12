#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["pydantic>=2"]
# ///
"""Pulse SDD gate hook — fast-path validation (no Docker).

Reads the current phase directly from ``.pulse/state.sqlite`` and applies
simplified write-guard rules.  Complex multi-path cases still go through
the MCP engine; this hook covers the common single-tool fast-path in
< 50 ms instead of the 2-5 s Docker+MCP overhead.

Contract: stdin = JSON payload, stdout = JSON response, stderr = debug.
Exit 0 always (blocking is via ``reject`` in the response body).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path, PurePath

# Bootstrap _lib on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "_lib"))

from pulse_hooks_lib.runtime import emit_response, log, read_payload, tool_args, tool_name
from pulse_hooks_lib.state import read_active_change_slug, read_phase

# ---------------------------------------------------------------------------
# Phase → allowed write globs (mirrors _PHASE_WRITE_GLOBS in skills_blueprint.py)
# ---------------------------------------------------------------------------

_PHASE_WRITE_GLOBS: dict[str, list[str]] = {
    "explore": [".pulse/changes/*/idea.md"],
    "specify": [
        ".pulse/changes/*/proposal.md",
        ".pulse/changes/*/delta_spec.md",
    ],
    "design": [".pulse/changes/*/design.md", ".pulse/changes/*/tasks.md"],
    "apply": ["src/**", "tests/**", ".pulse/changes/*/tasks.md"],
    "review": [
        ".pulse/changes/*/delta_spec.md",
        ".pulse/changes/*/spec_compliance_report.md",
        ".pulse/changes/*/code_quality_report.md",
    ],
    "close": [],
}

# Canonical write-tool names (normalized)
_WRITE_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit", "ApplyPatch"})

# Maps surface tool names to canonical forms
_TOOL_NAME_MAP: dict[str, str] = {
    "write_file": "Write",
    "replace": "Edit",
    "mcp_filesystem_write_file": "Write",
    "mcp_filesystem_edit_file": "Edit",
    "apply_patch": "ApplyPatch",
    # Gemini / Antigravity surface names
    "write_to_file": "Write",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "MultiEdit",
    "create_text_file": "Write",
    "replace_content": "Edit",
    "replace_symbol_body": "Edit",
    "insert_after_symbol": "Edit",
    "insert_before_symbol": "Edit",
}


# ---------------------------------------------------------------------------
# Path matching (mirrors skills_blueprint._path_permitida)
# ---------------------------------------------------------------------------


def _concrete_globs(phase: str, active_slug: str | None) -> list[str]:
    """Resolve write globs, substituting the active change slug."""
    raw = list(_PHASE_WRITE_GLOBS.get(phase, []))
    if active_slug is None:
        return raw
    concrete: list[str] = []
    for glob in raw:
        if glob.startswith(".pulse/changes/*/"):
            concrete.append(glob.replace(".pulse/changes/*/", f".pulse/changes/{active_slug}/"))
        else:
            concrete.append(glob)
    return concrete


def _path_allowed(path: PurePath, allowed_globs: list[str]) -> bool:
    """Return True if *path* matches at least one of the allowed globs."""
    if path.is_absolute():
        return False
    for glob in allowed_globs:
        if glob.endswith("/**"):
            prefix = glob[:-3]
            if path.is_relative_to(prefix):
                return True
        elif path.match(glob):
            return True
    return False


def _extract_paths(args: dict) -> list[str]:
    """Extract target paths from tool arguments (simplified)."""
    # Single-file tools
    for key in ("TargetFile", "file_path", "path", "AbsolutePath"):
        val = args.get(key)
        if val and isinstance(val, str):
            return [val]
    # apply_patch / command-based tools
    command = args.get("command") or args.get("tool_input")
    if isinstance(command, dict):
        command = command.get("command", "")
    if isinstance(command, str) and command:
        # Quick heuristic: find lines like "*** path/to/file" or "+++ path"
        paths: list[str] = []
        for line in command.splitlines():
            stripped = line.strip()
            if stripped.startswith("*** ") and not stripped.startswith("*** Begin"):
                candidate = stripped[4:].strip()
                if candidate and candidate not in paths:
                    paths.append(candidate)
        if paths:
            return paths
    return []


def _normalize_path(raw: str, workspace_root: str | None) -> PurePath:
    """Normalize an absolute path to workspace-relative if possible."""
    path = PurePath(raw)
    if path.is_absolute() and workspace_root:
        with contextlib.suppress(ValueError):
            path = path.relative_to(workspace_root)
    return path


# ---------------------------------------------------------------------------
# Response builders (client-dialect)
# ---------------------------------------------------------------------------


def _allow() -> dict:
    return {}


def _block(client: str, reason: str) -> dict:
    if client == "codex":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    # gemini / claude
    out: dict = {"reject": True, "rejectReason": reason}
    if client == "claude":
        out["hookEventName"] = "PreToolUse"
    return {"hookSpecificOutput": out}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Pulse SDD write-guard hook")
    ap.add_argument("--client", default="gemini", choices=["gemini", "claude", "codex"])
    args = ap.parse_args()

    payload = read_payload()
    name = tool_name(payload, args.client)
    t_args = tool_args(payload, args.client)

    if not name:
        log("sdd-validate: no tool name found, allowing")
        emit_response(_allow())
        return 0

    # Normalize to canonical write-tool name
    canonical = _TOOL_NAME_MAP.get(name, name)
    if canonical not in _WRITE_TOOLS:
        log(f"sdd-validate: {name!r} is not a write tool, allowing")
        emit_response(_allow())
        return 0

    # Read current SDD phase
    phase = read_phase()
    if phase == "unknown":
        log("sdd-validate: phase unknown, allowing (degraded)")
        emit_response(_allow())
        return 0

    # Extract paths from tool arguments
    paths = _extract_paths(t_args)
    if not paths:
        # Fail-closed: write tool without parseable paths → block
        reason = (
            f"BLOQUEADO: {name} sin rutas parseables "
            f"(fail-closed: no se pudo determinar el alcance de la operación)."
        )
        log(f"sdd-validate: {reason}")
        emit_response(_block(args.client, reason))
        return 0

    # Resolve allowed globs for the current phase
    active_slug = read_active_change_slug()
    allowed = _concrete_globs(phase, active_slug)

    # Import project_root for path normalization
    from pulse_hooks_lib.runtime import project_root

    ws_root = str(project_root())

    # Check every path against allowed globs
    for raw_path in paths:
        norm = _normalize_path(raw_path, ws_root)
        if not _path_allowed(norm, allowed):
            reason = (
                f"BLOQUEADO: {name} en '{raw_path}' no está permitido "
                f"durante la fase '{phase}'. "
                f"Rutas permitidas: {allowed or ['ninguna']}."
            )
            log(f"sdd-validate: {reason}")
            emit_response(_block(args.client, reason))
            return 0

    paths_str = ", ".join(paths) if len(paths) > 1 else paths[0]
    log(f"sdd-validate: PERMITIDO {name} en {paths_str} (fase {phase})")
    emit_response(_allow())
    return 0


if __name__ == "__main__":
    sys.exit(main())
