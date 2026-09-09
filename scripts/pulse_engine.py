"""Cliente JSON-RPC directo contra el engine de pulse, sin pasar por el plugin.

El ciclo SDD se opera normalmente con las skills `/pulse:*` del plugin `pulse@genesis`.
Este script existe para cuando ese plugin **no carga**, que es el caso de toda sesión de
Claude Code lanzada desde Windows: la entrada del marketplace resuelve a una ruta UNC
(`\\\\wsl.localhost\\...`) y Claude Code se niega a instalar desde una ubicación de red.

    Cannot install pulse@genesis: its marketplace entry path does not stay inside the
    marketplace directory (an absolute, climbing, network-shaped or link-traversing entry...)

El bloqueo es de comodidad, no de capacidad: el engine es un server MCP por stdio dentro
del contenedor, y se le puede hablar directamente. Con esto se cerró el change #55 el
2026-08-29, después de 18 días atascado.

**Por qué un cliente y no un redirect.** Redirigir un archivo de mensajes a `docker run -i`
no funciona: el server ve EOF y termina antes de atender la llamada, así que responde el
`initialize` y nada más. Hay que sostener el pipe abierto hasta leer cada respuesta.

Uso:

    uv run python scripts/pulse_engine.py tools
    uv run python scripts/pulse_engine.py call list_active_changes
    uv run python scripts/pulse_engine.py call close_change \\
        --args '{"input_data":{"slug":"55-..."}}'

Advertencia sobre el cierre: `close_change` exige el Change en fase `review` y **es** quien
lo mueve a `close`. Nunca adelantar la fase con `request_sdd_transition(target_phase="close")`
— deja el Change inservible y la guarda G2 bloquea entonces la creación de cualquier otro.
Ver `.claude/plugins/pulse/skills/review/SKILL.md`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

IMAGE: str = "mcp-pulse:0.13.6"
"""Imagen del engine. La `:latest` publicada en ghcr es la v0.13.0 y falla en `promote_delta`;
hay que construir desde `main` y etiquetar (ver CLAUDE.md)."""

PROTOCOL_VERSION: str = "2024-11-05"


def _binario(nombre: str) -> str:
    """Ruta absoluta de un ejecutable; fail-fast nombrándolo si no está en el `PATH`."""
    ruta = shutil.which(nombre)
    if ruta is None:
        raise SystemExit(f"No se encontró {nombre!r} en el PATH.")
    return ruta


def _repo_root() -> Path:
    """Raíz del repo montada en `/work`; fail-fast si no estamos dentro de uno."""
    try:
        salida = subprocess.run(  # noqa: S603 — argv fijo, sin entrada del usuario
            [_binario("git"), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit("No se pudo resolver la raíz del repo con git.") from exc
    return Path(salida.stdout.strip())


def _docker_argv(root: Path) -> list[str]:
    """Mismos flags que el `.mcp.json` del plugin: el engine espera exactamente este entorno."""
    return [
        _binario("docker"),
        "run",
        "-i",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{root}:/work",
        "-v",
        "pulse-venv:/work/.venv",
        "-v",
        "uv_warm_cache:/tmp/uv-cache",
        "-w",
        "/work",
        "-e",
        "PULSE_WORKSPACE_ROOT=/work",
        "-e",
        "PULSE_SQLITE_PATH=/work/.pulse/state.sqlite",
        "-e",
        "UV_HTTP_TIMEOUT=1800",
        IMAGE,
    ]


class _EngineSession:
    """Sesión MCP por stdio: mantiene el pipe abierto hasta recibir cada respuesta."""

    def __init__(self, root: Path) -> None:
        self._proc = subprocess.Popen(  # noqa: S603 — argv fijo, sin entrada del usuario
            _docker_argv(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # El banner de FastMCP sale por stderr y solo estorba.
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise SystemExit("No se pudieron abrir los pipes del contenedor del engine.")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout

    def __enter__(self) -> _EngineSession:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "genesis/pulse_engine.py", "version": "1.0"},
                },
            }
        )
        self._await(1)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def __exit__(self, *_: object) -> None:
        self._stdin.close()
        self._proc.wait(timeout=120)

    def _send(self, mensaje: Mapping[str, object]) -> None:
        self._stdin.write(json.dumps(mensaje) + "\n")
        self._stdin.flush()

    def _await(self, target: int) -> dict[str, object]:
        while True:
            linea = self._stdout.readline()
            if not linea:
                raise SystemExit(
                    f"El engine cerró stdout sin responder al id={target}. "
                    f"Verificá que la imagen {IMAGE} exista: docker image inspect {IMAGE}"
                )
            linea = linea.strip()
            if not linea.startswith("{"):
                continue
            mensaje = json.loads(linea)
            if mensaje.get("id") == target:
                return mensaje

    def request(self, method: str, params: Mapping[str, object]) -> dict[str, object]:
        self._send({"jsonrpc": "2.0", "id": 2, "method": method, "params": params})
        return self._await(2)


def _resultado(respuesta: Mapping[str, object]) -> dict[str, object]:
    """Extrae el `result` de una respuesta JSON-RPC, fail-fast si no vino."""
    resultado = respuesta.get("result")
    if not isinstance(resultado, dict):
        raise SystemExit(f"El engine respondió sin `result`: {respuesta}")
    return resultado


def _lista(contenedor: Mapping[str, object], clave: str) -> list[object]:
    """Extrae una lista del payload; vacía si la clave no vino, fail-fast si no es lista."""
    valor = contenedor.get(clave, [])
    if not isinstance(valor, list):
        raise SystemExit(f"El engine devolvió `{clave}` con tipo {type(valor).__name__}.")
    return valor


def _campo(elemento: object, clave: str) -> str:
    """Lee un campo de texto de un elemento del payload, tolerando ausencia."""
    if not isinstance(elemento, dict):
        return ""
    return str(elemento.get(clave, ""))


def _print_tools(respuesta: Mapping[str, object]) -> None:
    for tool in _lista(_resultado(respuesta), "tools"):
        descripcion = _campo(tool, "description").strip().splitlines()
        print(f"{_campo(tool, 'name'):<32} {descripcion[0] if descripcion else ''}")


def _print_result(respuesta: Mapping[str, object]) -> int:
    if "error" in respuesta:
        print(json.dumps(respuesta["error"], indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    resultado = _resultado(respuesta)

    # El engine devuelve el payload duplicado: texto plano en `content` y objeto en
    # `structuredContent`. Se prefiere el segundo, que no exige re-parsear.
    if "structuredContent" in resultado:
        print(json.dumps(resultado["structuredContent"], indent=2, ensure_ascii=False))
    else:
        for bloque in _lista(resultado, "content"):
            print(_campo(bloque, "text"))

    # `isError` viaja dentro del resultado, no como error JSON-RPC: una guarda rechazada
    # (SpecGate, G2, precondición de fase) llega por acá y debe propagarse al exit code.
    return 1 if resultado.get("isError") else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Habla con el engine de pulse por JSON-RPC, sin el plugin.",
        epilog="El engine corre en Docker: requiere POSIX (no Windows nativo).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("tools", help="Lista las tools que expone el engine.")

    llamar = sub.add_parser("call", help="Invoca una tool del engine.")
    llamar.add_argument("tool", help="Nombre de la tool (ver `tools`).")
    llamar.add_argument(
        "--args",
        default="{}",
        help='Argumentos como JSON. Ej: \'{"input_data":{"slug":"55-..."}}\'',
    )

    args = parser.parse_args()
    root = _repo_root()

    with _EngineSession(root) as sesion:
        if args.comando == "tools":
            _print_tools(sesion.request("tools/list", {}))
            return 0

        try:
            argumentos = json.loads(args.args)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--args no es JSON válido: {exc}") from exc

        return _print_result(
            sesion.request("tools/call", {"name": args.tool, "arguments": argumentos})
        )


if __name__ == "__main__":
    raise SystemExit(main())
