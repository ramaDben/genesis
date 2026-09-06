#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Hook SessionStart — inyecta el estado real del proyecto al arrancar.

POR QUÉ EXISTE

``CLAUDE.md`` ordena listar y leer las memorias de Serena al inicio de cada
sesión, antes de tocar código o responder.  Eso es una **instrucción**: depende
de que el agente se acuerde de obedecerla, y ya se sabe cómo terminan las
instrucciones que sustituyen a un control (ver ``mem:reserva-de-gobernanza-2026-09``).
Este hook la convierte en un **hecho**: el índice de memorias y el estado del
repositorio llegan al contexto inicial sin que nadie tenga que pedirlo.

Todo lo que lee sale del disco del repo salvo la lista de issues, que es
opcional y degrada en silencio si no hay red o no hay ``gh``.

Contrato: stdin = payload JSON, stdout = JSON de respuesta, stderr = diagnóstico.
NUNCA bloquea — siempre termina con código 0.
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
from pathlib import Path

# Bootstrap _lib en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "_lib"))

from pulse_hooks_lib.runtime import emit_response, log, project_root, read_payload
from pulse_hooks_lib.state import read_active_change, read_phase

# Segundos que se le conceden a un subproceso antes de abandonarlo.  El arranque
# de la sesión no puede quedar colgado esperando a la red.
_GIT_TIMEOUT_S = 5
_GH_TIMEOUT_S = 8

# Cuántas memorias listar antes de truncar.  Hoy hay 23; el tope evita que el
# contexto inicial se degrade solo cuando la carpeta crezca.
_MAX_MEMORIAS = 40


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> str:
    """Ejecuta un comando y devuelve stdout, o "" ante cualquier problema."""
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log(f"session-context: {cmd[0]} falló ({exc.__class__.__name__}), se omite")
        return ""
    return proc.stdout.strip()


def _titulo_de_memoria(path: Path) -> str:
    """Primera línea con contenido real de una memoria de Serena.

    Las memorias empiezan con un paréntesis de fecha —``*(2026-09-05 — ...)*``—
    y recién después va el ``# Título``.  Se prefiere el título; si no hay, la
    primera línea no vacía sirve igual.
    """
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    primera = ""
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        if limpia.startswith("# "):
            return limpia[2:].strip()
        if not primera:
            primera = limpia.lstrip("*(").rstrip(")*")
    return primera


def _bloque_memorias(root: Path) -> str:
    carpeta = root / ".serena" / "memories"
    if not carpeta.is_dir():
        return ""
    # rglob, no glob: hay memorias anidadas en subcarpetas
    # (p. ej. `pulse-gate2-review/issue-18-ftmo-spec`).
    archivos = sorted(carpeta.rglob("*.md"))
    if not archivos:
        return ""
    lineas = [
        f"### Memorias de Serena ({len(archivos)} disponibles)",
        "",
        "Léelas con `read_memory` ANTES de tocar código o responder sobre un área."
        " No hace falta llamar a `list_memories`: el índice está acá.",
        "",
    ]
    for path in archivos[:_MAX_MEMORIAS]:
        titulo = _titulo_de_memoria(path)
        sufijo = f" — {titulo}" if titulo else ""
        # El nombre que espera `read_memory` es la ruta relativa sin extensión.
        nombre = path.relative_to(carpeta).with_suffix("").as_posix()
        lineas.append(f"- `{nombre}`{sufijo}")
    if len(archivos) > _MAX_MEMORIAS:
        lineas.append(f"- … y {len(archivos) - _MAX_MEMORIAS} más")
    lineas.append("")
    lineas.append(
        "Recordatorio: son **observaciones fechadas, no estado vivo**. Si una cita"
        " un archivo, una función o una cifra, verifícalo contra el código actual"
        " antes de afirmarlo."
    )
    return "\n".join(lineas)


def _bloque_git(root: Path) -> str:
    rama = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, timeout=_GIT_TIMEOUT_S)
    ultimo = _run(["git", "log", "-1", "--oneline"], cwd=root, timeout=_GIT_TIMEOUT_S)
    sucio = _run(["git", "status", "--porcelain"], cwd=root, timeout=_GIT_TIMEOUT_S)
    if not rama and not ultimo:
        return ""
    n_sucios = len([ln for ln in sucio.splitlines() if ln.strip()])
    estado = "limpio" if n_sucios == 0 else f"{n_sucios} archivo(s) sin commitear"
    return "\n".join(
        [
            "### Repositorio",
            "",
            f"- Rama: `{rama or '?'}` · working tree {estado}",
            f"- Último commit: {ultimo or '?'}",
        ]
    )


def _bloque_ciclo() -> str:
    fase = read_phase()
    slug = ""
    with contextlib.suppress(Exception):
        activo = read_active_change()
        slug = (activo or {}).get("slug", "") if isinstance(activo, dict) else ""
    lineas = ["### Ciclo SDD (pulse)", "", f"- Fase del engine: **{fase}**"]
    if slug:
        lineas.append(f"- Change activo: `{slug}`")
    else:
        lineas.append("- Change activo: ninguno")
    if fase == "unknown":
        lineas.append(
            "- ⚠️ No se pudo leer `.pulse/state.sqlite`. Si esta sesión corre en"
            " Windows sobre UNC, el guardián de escritura está en modo fail-closed"
            " y sólo permitirá la vía rápida."
        )
    return "\n".join(lineas)


def _bloque_issues(root: Path) -> str:
    """Issues abiertos que NO están reservados. Degrada en silencio sin red."""
    salida = _run(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            "30",
            "--json",
            "number,title,labels",
            "--template",
            "{{range .}}#{{.number}} {{.title}}|{{range .labels}}{{.name}},{{end}}\n{{end}}",
        ],
        cwd=root,
        timeout=_GH_TIMEOUT_S,
    )
    if not salida:
        return ""
    activos: list[str] = []
    diferidos = 0
    for linea in salida.splitlines():
        if not linea.strip():
            continue
        titulo, _, etiquetas = linea.partition("|")
        if "state:diferido" in etiquetas:
            diferidos += 1
            continue
        activos.append(f"- {titulo.strip()}")
    if not activos and not diferidos:
        return ""
    lineas = ["### Issues abiertos y NO reservados", ""]
    lineas.extend(activos or ["- (ninguno)"])
    if diferidos:
        lineas.append("")
        lineas.append(
            f"Además hay {diferidos} issue(s) con `state:diferido` — trabajo"
            " reservado a propósito. No los retomes sin decisión explícita:"
            " el porqué está en `mem:reserva-de-gobernanza-2026-09`."
        )
    return "\n".join(lineas)


def _bloque_omega() -> str:
    return "\n".join(
        [
            "### OMEGA",
            "",
            "Si arriba no llegó un briefing de OMEGA, su server MCP todavía no"
            " estaba conectado cuando disparó este hook. En ese caso llama a"
            " `omega_welcome()` y `omega_protocol()` tú mismo antes de trabajar,"
            " y `omega_store()` al cerrar decisiones.",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Hook SessionStart de genesis")
    ap.add_argument("--client", default="claude", choices=["claude", "gemini", "codex"])
    ap.parse_args()

    # El payload se consume aunque no se use: dejar stdin sin leer puede
    # provocar un EPIPE del lado del cliente.
    with contextlib.suppress(Exception):
        read_payload()

    root = project_root()
    bloques = [
        b
        for b in (
            _bloque_git(root),
            _bloque_ciclo(),
            _bloque_issues(root),
            _bloque_memorias(root),
            _bloque_omega(),
        )
        if b
    ]

    if not bloques:
        log("session-context: nada que inyectar")
        emit_response({})
        return 0

    contexto = "[genesis · contexto de sesión inyectado automáticamente]\n\n" + "\n\n".join(bloques)
    log(f"session-context: {len(bloques)} bloque(s), {len(contexto)} caracteres")
    emit_response(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": contexto,
            }
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
