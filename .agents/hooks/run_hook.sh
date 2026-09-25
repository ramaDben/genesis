#!/usr/bin/env bash
# Despachador de hooks: ejecuta el hook en el entorno donde de verdad funciona.
#
# POR QUÉ EXISTE (medido el 2026-09-05, no supuesto)
#
# Desde una sesión de Claude Code lanzada en Windows, el repo se alcanza por UNC
# (//wsl.localhost/Ubuntu/home/<usuario>/genesis). Ejecutar los hooks ahí es
# frágil: el I/O por UNC puede fallar sin ruido y el hook emitir contexto vacío
# como si hubiera funcionado. Despacharlos dentro de WSL lo evita.
#
#   Ruta A (Git Bash de Windows sobre UNC): 3.81 s
#   Ruta B (despachado por `wsl -d Ubuntu`): 1.45 s
#
# Además la ruta B es MÁS rápida: el I/O por UNC cuesta más que arrancar WSL.
#
# El mismo settings.json versionado sirve en los dos escenarios: cuando la sesión
# corra dentro de WSL (la solución de raíz de mem:entorno-de-desarrollo), este
# script ejecuta directo y el rodeo desaparece solo.
#
# Uso:  run_hook.sh <script.py> [args...]     (el payload JSON viaja por stdin)

set -euo pipefail

script="${1:?run_hook.sh: falta el nombre del script de hook}"
shift

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    # Sesión en Windows: hay que re-ejecutar dentro de WSL.
    root="${CLAUDE_PROJECT_DIR:-$(pwd)}"

    # //wsl.localhost/Ubuntu/home/u/genesis  ->  /home/u/genesis
    # (también acepta la forma antigua //wsl$/Ubuntu/...)
    linux_root=$(printf '%s' "$root" \
      | tr '\\' '/' \
      | sed -E 's#^/{2}wsl(\.localhost|\$)/[^/]+##')

    if [ -z "$linux_root" ] || [ "$linux_root" = "$root" ]; then
      # No se pudo traducir la ruta. Fallar de forma VISIBLE en vez de adivinar
      # una ubicación: un hook que corre sobre el repo equivocado es peor que un
      # hook que no corre (es la trampa de mem:entorno-de-desarrollo, donde los
      # MCP apuntaban a la copia obsoleta de Windows sin que nadie lo notara).
      echo "run_hook.sh: no se pudo traducir '$root' a una ruta de WSL." >&2
      echo "run_hook.sh: el hook '$script' NO se ejecutó." >&2
      exit 1
    fi

    # El login shell (-l) es obligatorio: sin él no hay uv ni mise en el PATH.
    quoted=""
    for arg in "$@"; do
      quoted="$quoted '$arg'"
    done
    exec wsl -d Ubuntu -- bash -lc \
      "cd '$linux_root' && exec uv run '.agents/hooks/$script'$quoted"
    ;;

  *)
    # Sesión nativa en Linux/WSL: ejecutar directo.
    cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
    exec uv run ".agents/hooks/$script" "$@"
    ;;
esac
