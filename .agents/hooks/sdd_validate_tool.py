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
import re
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

# Rutas escribibles en CUALQUIER fase — la "vía rápida" de CLAUDE.md.
#
# Sin esto el guardián es inutilizable: la allowlist por fase es estricta, y en
# `explore` sólo pasa `.pulse/changes/*/idea.md`.  Encenderlo tal cual bloquearía
# escribir documentación, runners y memorias, que CLAUDE.md declara
# explícitamente fuera del ciclo SDD porque no alteran comportamiento ni
# contrato bajo `src/genesis/**`.
#
# DEBILIDAD ACEPTADA A SABIENDAS (2026-09-05): `.agents/**` y `.claude/**` están
# acá dentro, así que el agente puede editar los hooks que lo restringen — un
# control capaz de desactivarse a sí mismo.  Se acepta porque la alternativa
# (bloquearlos siempre) haría imposible mantenerlos, y porque el historial de git
# deja el rastro.  Cuando exista el adjudicador externo del #87, esta es la
# primera excepción que debería escalar.
_ALWAYS_ALLOWED_GLOBS: list[str] = [
    "docs/**",
    "scripts/**",
    ".serena/memories/**",
    ".agents/**",
    ".claude/**",
    "*.md",
]

# Canonical write-tool names (normalized)
_WRITE_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit", "ApplyPatch"})

# Herramientas que ejecutan un comando de shell.
#
# Eran un bypass completo: `run_command` con `sed -i src/genesis/...` escribía
# sin pasar por ninguna allowlist (medido el 2026-09-12).  El agujero existía
# también para el `Bash` de Claude Code; se tapan los dos de una vez.
_COMMAND_TOOLS: frozenset[str] = frozenset({"RunCommand"})

_COMMAND_TOOL_MAP: dict[str, str] = {
    "run_command": "RunCommand",      # antigravity
    "run_terminal_cmd": "RunCommand",
    "Bash": "RunCommand",             # claude code
    "shell": "RunCommand",            # codex
    "execute_shell_command": "RunCommand",  # serena
}

# Rutas que ningún comando puede tocar fuera de la fase `apply`.
_COMMAND_PROTECTED = re.compile(r"(?:^|[\s'\"=(/])(?:\./)?(src|tests)/")

# Construcciones de shell que escriben.  Heurística deliberada: reconocer
# "esto muta un archivo" en shell arbitrario es indecidible, así que esto NO es
# una garantía, es una red.  La garantía dura vive en `permissions.deny` de
# Antigravity (`write_file(src/)`, `command(regex:...)`), que se evalúa con
# precedencia `Deny > Ask > Allow` y no depende de este parser.
#
# Limitaciones conocidas y aceptadas: variables (`$D/x.py`), heredocs, base64,
# `python -c "open(...,'w')"`, y cualquier indirección pasan.  Se cubre el caso
# accidental y el perezoso, no al adversario decidido.
_COMMAND_WRITERS = re.compile(
    r"(?:>>?\s|\btee\b|\bsed\b[^|;]*\s-[a-zA-Z]*i|\bcp\b|\bmv\b|\brm\b|\btruncate\b"
    r"|\bdd\b|\bpatch\b|\btouch\b|\bchmod\b|\bmkdir\b|\bln\b"
    r"|\bgit\s+(?:apply|checkout|restore|clean|stash)\b)"
)

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
    # Serena — el resto de sus herramientas de escritura.  Sin estas entradas
    # serena era un bypass completo del guardián: `replace_symbol_body` sobre
    # `src/genesis/**` pasaba sin bloqueo (verificado el 2026-09-05).
    "replace_lines": "Edit",
    "delete_lines": "Edit",
    "insert_at_line": "Edit",
    "replace_in_files": "MultiEdit",
    "rename_symbol": "MultiEdit",
    "safe_delete_symbol": "MultiEdit",
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
    """Extract target paths from tool arguments (simplified).

    ``relative_path`` es la clave que usan las herramientas de escritura de
    serena (``replace_symbol_body``, ``insert_after_symbol``, …).  Sin ella el
    guardián no encuentra ruta y cae en la rama fail-closed, que bloquea por el
    motivo equivocado.
    """
    # Single-file tools
    for key in ("TargetFile", "file_path", "path", "relative_path", "AbsolutePath"):
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


def _normalize_path(raw: str, workspace_root: str | None) -> PurePath | None:
    """Devuelve la ruta relativa al workspace, o ``None`` si cae fuera de él.

    Traduce las rutas que envía una sesión de Claude Code corriendo en Windows
    contra el repo de WSL: llegan en forma UNC
    (``\\\\wsl.localhost\\Ubuntu\\home\\u\\genesis\\docs\\x.md``) mientras que el
    hook se ejecuta *dentro* de WSL, donde la raíz es ``/home/u/genesis``.  Sin
    la traducción, ``relative_to`` falla, la ruta queda absoluta y
    ``_path_allowed`` la rechaza: el guardián bloquearía **toda** escritura
    (verificado el 2026-09-05).

    ``None`` significa "fuera del repositorio" y el llamador debe **permitir**:
    el ciclo SDD gobierna este workspace, no el resto del disco.  Es el caso del
    directorio de scratchpad de la sesión, que vive bajo ``C:\\Users\\...`` y es
    justamente donde se deben escribir los archivos temporales.
    """
    texto = raw.replace("\\", "/")
    # //wsl.localhost/Ubuntu/home/u/genesis/...  ->  /home/u/genesis/...
    texto = re.sub(r"^/{2}wsl(?:\.localhost|\$)/[^/]+", "", texto)

    # Ruta de Windows con letra de unidad (C:/Users/...): fuera del repo de WSL
    # por construcción.  PurePosixPath no la reconoce como absoluta, así que si
    # no se detecta acá se colaría como si fuera relativa.
    if re.match(r"^[A-Za-z]:/", texto):
        return None

    path = PurePath(texto)
    if not path.is_absolute():
        return path
    if workspace_root and path.is_relative_to(workspace_root):
        return path.relative_to(workspace_root)
    return None


# ---------------------------------------------------------------------------
# Response builders (client-dialect)
# ---------------------------------------------------------------------------


def _allow() -> dict:
    return {}


def _block(client: str, reason: str) -> dict:
    """Construye la respuesta de bloqueo en el dialecto del cliente.

    Claude Code y Codex comparten forma: ``permissionDecision: "deny"`` dentro de
    ``hookSpecificOutput``.  Gemini usa ``reject``/``rejectReason``.
    Antigravity CLI usa ``decision``/``reason`` **en la raíz**.

    Hasta el 2026-09-05 la rama de Claude emitía el dialecto de Gemini, así que
    **el bloqueo se ignoraba en silencio** y la escritura procedía igual.  Era el
    único cliente cuya rama nunca se había ejercitado.

    El 2026-09-12 se encontró el mismo fallo en la rama de Antigravity, que
    emitía el dialecto de Gemini: agy habría ignorado todo bloqueo.  La forma
    correcta está en https://antigravity.google/docs/hooks/ — el vocabulario es
    ``allow | deny | ask | force_ask | deny_unless_prior_grant``.
    """
    if client in ("claude", "codex"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    if client == "antigravity":
        return {"decision": "deny", "reason": reason}
    # gemini
    return {"hookSpecificOutput": {"reject": True, "rejectReason": reason}}


# ---------------------------------------------------------------------------
# Command tools
# ---------------------------------------------------------------------------


def _command_text(args: dict) -> str:
    """Devuelve el comando a ejecutar, mirando las claves de cada superficie."""
    for key in ("CommandLine", "command", "Command", "cmd", "shell_command"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _check_command(client: str, name: str, t_args: dict, phase: str) -> dict:
    """Decide sobre una ejecución de shell.

    Durante `apply` los comandos sobre `src/`/`tests/` son legítimos (es la fase
    que los habilita).  Fuera de `apply`, un comando que además de nombrar esas
    rutas trae una construcción de escritura se bloquea.

    Un comando ilegible se PERMITE, a diferencia de una herramienta de escritura
    sin rutas.  No es incoherencia: una herramienta de escritura escribe por
    definición, un comando no.  Denegar todo comando que no se pueda parsear
    equivale a denegar `ls`, y un guardián que inutiliza la sesión se apaga al
    día siguiente.  La capa dura para este caso es `permissions.deny` de
    Antigravity, que no depende de este parser.
    """
    command = _command_text(t_args)
    if not command:
        log(
            f"sdd-validate: {name!r} sin comando legible en {sorted(t_args)}, "
            "PERMITIDO (ver docstring)"
        )
        return _allow()

    if phase == "apply":
        log(f"sdd-validate: PERMITIDO {name} (fase apply habilita src/ y tests/)")
        return _allow()

    toca = _COMMAND_PROTECTED.search(command)
    escribe = _COMMAND_WRITERS.search(command)
    if toca and escribe:
        reason = (
            f"BLOQUEADO: {name} parece escribir en '{toca.group(1)}/' durante la fase "
            f"'{phase}'. Comando: {command[:200]!r}. "
            "Un cambio bajo `src/genesis/**` o `tests/**` exige un change activo en "
            "fase `apply` — pasa por el ciclo SDD (ver CLAUDE.md). Si el comando no "
            "escribe, reformulalo para que no dispare la heurística, o hacelo en la fase correcta."
        )
        log(f"sdd-validate: {reason}")
        return _block(client, reason)

    log(f"sdd-validate: PERMITIDO {name} (no escribe en rutas protegidas, fase {phase})")
    return _allow()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Pulse SDD write-guard hook")
    ap.add_argument(
        "--client",
        default="gemini",
        choices=["gemini", "claude", "codex", "antigravity"],
    )
    args = ap.parse_args()

    payload = read_payload()
    name = tool_name(payload, args.client)
    t_args = tool_args(payload, args.client)

    if not name:
        log("sdd-validate: no tool name found, allowing")
        emit_response(_allow())
        return 0

    # Normalize to canonical write-tool name.
    #
    # Las herramientas de un server MCP llegan como `mcp__<server>__<tool>`
    # (p. ej. `mcp__serena__replace_symbol_body`), así que hay que quitar el
    # prefijo antes de consultar el mapa o toda escritura vía MCP se cuela.
    bare = re.sub(r"^mcp__[^_]+(?:_[^_]+)*__", "", name)

    # Herramientas de shell: camino propio.  No traen "ruta" en los argumentos,
    # así que el chequeo por globs no las alcanza — hay que leer el comando.
    if _COMMAND_TOOL_MAP.get(bare, _COMMAND_TOOL_MAP.get(name)) in _COMMAND_TOOLS:
        emit_response(_check_command(args.client, name, t_args, read_phase()))
        return 0

    canonical = _TOOL_NAME_MAP.get(bare, _TOOL_NAME_MAP.get(name, name))
    if canonical not in _WRITE_TOOLS:
        log(f"sdd-validate: {name!r} is not a write tool, allowing")
        emit_response(_allow())
        return 0

    # Read current SDD phase.
    #
    # Fase desconocida ⇒ fail-CLOSED (cambiado el 2026-09-05; antes permitía).
    # Motivo medido: desde una sesión en Windows sobre UNC, leer
    # `.pulse/state.sqlite` devuelve "database is locked" y la fase es SIEMPRE
    # "unknown".  Con la rama vieja el guardián permitía todo, siempre, sin
    # avisar — un control que se apaga solo justo donde más falta hace.
    # `_ALWAYS_ALLOWED_GLOBS` sigue pasando, así que la vía rápida nunca se
    # bloquea por este camino y la sesión no queda inutilizable.
    phase = read_phase()

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

    # Resolve allowed globs: la vía rápida siempre, más lo que abra la fase.
    active_slug = read_active_change_slug()
    phase_globs = _concrete_globs(phase, active_slug)
    allowed = [*_ALWAYS_ALLOWED_GLOBS, *phase_globs]

    # Import project_root for path normalization
    from pulse_hooks_lib.runtime import project_root

    ws_root = str(project_root())

    # Check every path against allowed globs
    for raw_path in paths:
        norm = _normalize_path(raw_path, ws_root)
        if norm is None:
            # Fuera del repositorio (scratchpad de la sesión, /tmp, etc.).
            # El ciclo SDD gobierna este workspace, no el resto del disco.
            log(f"sdd-validate: '{raw_path}' cae fuera del workspace, PERMITIDO")
            continue
        if not _path_allowed(norm, allowed):
            if phase == "unknown":
                detalle = (
                    "no se pudo determinar la fase del ciclo SDD "
                    "(¿`.pulse/state.sqlite` ilegible?), así que sólo se permite "
                    "la vía rápida"
                )
            else:
                detalle = f"no está permitido durante la fase '{phase}'"
            reason = (
                f"BLOQUEADO: {name} en '{raw_path}' {detalle}. "
                f"Rutas permitidas: {allowed}. "
                "Un cambio bajo `src/genesis/**` exige un change activo en fase "
                "`apply` — pasa por el ciclo SDD (ver CLAUDE.md)."
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
