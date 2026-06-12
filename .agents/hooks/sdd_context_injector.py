#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["pydantic>=2"]
# ///
"""Pulse SDD context injector hook — fast-path (no Docker).

Reads the current SDD phase and active change directly from the
filesystem and emits ``additionalContext`` so the LLM turno stays
phase-aware.  Loads domain heuristics from ``.pulse/heuristics/``
when available.

Contract: stdin = JSON payload, stdout = JSON response, stderr = debug.
NEVER blocks — always exits 0.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

# Bootstrap _lib on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "_lib"))

from pulse_hooks_lib.runtime import emit_response, log, project_root, read_payload
from pulse_hooks_lib.state import read_active_change, read_phase

# ---------------------------------------------------------------------------
# Domain heuristics loader
# ---------------------------------------------------------------------------


def _load_domain_heuristics(domain: str) -> str:
    """Read the versioned heuristics file; degrade silently on error."""
    try:
        root = project_root()
        path = root / ".pulse" / "heuristics" / f"{domain}.md"
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        # Take the N most recent entries (delimited by '### Heurística:')
        blocks = text.split("### Heurística:")
        recent = [b for b in blocks[-3:] if b.strip()]
        if recent:
            return ("### Heurística:" + "### Heurística:".join(recent)).strip()
        return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_context(phase: str, active_change: dict | None) -> str:
    """Build the additionalContext string injected into the LLM turn."""
    base = (
        f"[Pulse SDD · contexto inyectado] Fase actual del engine: **{phase}**. "
        "Respeta el ciclo explore→specify→design→apply→review→close y el gate "
        "humano DESIGN→APPLY. Usa request_sdd_transition con evidencia real para "
        "avanzar de fase."
    )

    if active_change:
        slug = active_change.get("slug", "?")
        domain = active_change.get("domain", "?")
        change_phase = active_change.get("current_phase", "?")
        awaiting = active_change.get("awaiting_approval", False)
        base += (
            f" Cambio activo: {slug} (dominio={domain}, fase={change_phase}, "
            f"awaiting_approval={awaiting})."
        )

        if domain and domain != "?":
            heuristics = _load_domain_heuristics(domain)
            if heuristics:
                base += f"\n[Heurísticas dominio {domain}]\n{heuristics[:800]}"

    return base


# ---------------------------------------------------------------------------
# Emit (client-dialect wrappers)
# ---------------------------------------------------------------------------


def _emit(client: str, ctx: str | None) -> None:
    """Emit the hook response in the client's expected format."""
    if ctx is None:
        emit_response({})
        return

    if client == "claude":
        out = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ctx,
            }
        }
    else:
        # gemini (BeforeAgent) and codex — same shape
        out = {"hookSpecificOutput": {"additionalContext": ctx}}

    emit_response(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Pulse SDD context injector hook")
    ap.add_argument("--client", default="gemini", choices=["gemini", "claude", "codex"])
    args = ap.parse_args()

    # Consume stdin by contract; we don't need the content.
    with contextlib.suppress(Exception):
        read_payload()

    ctx: str | None = None
    try:
        phase = read_phase()
        if phase == "unknown":
            log("sdd-context: phase unknown, emitting empty context")
        else:
            active = read_active_change()
            ctx = _build_context(phase, active)
    except Exception as exc:
        log(f"sdd-context: error {exc!r}")

    _emit(args.client, ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
