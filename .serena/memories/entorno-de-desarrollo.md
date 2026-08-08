# Entorno de desarrollo (desde 2026-08-01)

**WSL2 / Ubuntu 26.04, no Windows nativo.** El repo de trabajo es `~/genesis`
(usuario Linux `bbenja11`). **Nunca trabajar en `/mnt/c/Users/bbrav/genesis`**: es la copia
vieja de Windows y el I/O cruza la frontera de filesystems.

Motivo de la migración: el engine de pulse en modo nativo Windows **se cuelga al ejecutar el
gate determinista** (`close_change` sin respuesta a los 1827 s, procesos con CPU 0 y sin logs;
sospecha de interacción de asyncio/FastMCP con `subprocess`, reportado en `Bajmein/pulse#127`).

## TRAMPA: los MCP heredan el workspace del CWD de la sesión (2026-08-02)

Si la sesión de Claude Code se lanza **en Windows** (CWD `C:\Users\bbrav\genesis`), todo el
toolchain MCP que deriva su raíz del CWD apunta a la **copia obsoleta**, no al repo de trabajo:

- `pulse-engine` montaba `-v "$(git rev-parse --show-toplevel):/work"` → `/mnt/c/...`.
- `serena` (`--project-from-cwd`), `filesystem` y `memory` (ambos con `git rev-parse`) → ídem.

Síntoma que lo delató: `list_active_changes` reportaba el change #24 **activo en review**,
cuando el estado real (`~/genesis/.pulse/state.sqlite`, 2026-08-01) tiene
`current_phase=explore` y `active_change_slug=null`. El engine estaba leyendo el SQLite de
Windows, congelado el 2026-07-24. Además `create_change_from_issue` fallaba con
`[Errno 13] Permission denied` sobre `/work/.pulse/changes`: ese directorio quedó
`root:root` en la copia de Windows (lo creó una imagen antigua que corría como root) y el
contenedor actual corre con `--user 1000:1000`.

**Fix aplicado** en `.claude/plugins/pulse/.mcp.json` (versionado): resolver el workspace y
redirigir a `$HOME/genesis` cuando el toplevel cae en `/mnt/c`:

```sh
WS=$(git rev-parse --show-toplevel 2>/dev/null)
case "$WS" in /mnt/c/*|"") WS="$HOME/genesis";; esac
exec docker run -i --rm --user "$(id -u):$(id -g)" -v "$WS:/work" ...
```

Verificado: monta `/home/bbenja11/genesis`, todo `1000:1000`, `mkdir`/`touch` permitidos.
**Requiere reiniciar la sesión** para que el MCP se relance. El parche arregla pulse; serena,
filesystem y memory siguen viendo la copia de Windows.

**Solución de raíz**: lanzar Claude Code **dentro de WSL** (`cd ~/genesis && claude`). Está
instalado vía mise (`~/.local/share/mise/installs/node/lts/bin/`) pero el login quedó pendiente
por credenciales de Claude for Work — ese es el único bloqueo.

**Diagnóstico rápido** de si el workspace es el correcto:
`docker inspect <contenedor> --format '{{json .Mounts}}'` — si aparece `/mnt/c/...`, está mal.

## Desde una sesión de Claude Code que corre en Windows

- Leer/editar archivos del repo de WSL por UNC: `\\wsl$\Ubuntu\home\bbenja11\genesis\...`
  (Read/Write/Edit funcionan bien; `rg` y `ls` de Git Bash **no** manejan esa ruta).
- Ejecutar comandos: `wsl -d Ubuntu -- bash -lc "cd ~/genesis && <cmd>"`. El **login shell
  (`-l`) es obligatorio**: sin él no hay `uv`, `mise` ni `node` en el `PATH`.
- Para comandos largos o con comillas, pipes o `$()`: escribir un `.sh` en el scratchpad y
  lanzarlo con `wsl -d Ubuntu -- bash -l /mnt/c/.../script.sh`. El escaping inline de
  PowerShell hacia bash falla de forma sistemática.
- Los scripts `.ps1` deben ser **ASCII puro** (los acentos se corrompen).

## Comandos del proyecto

`mise run setup` (uv sync --all-groups) · `mise run ci` (lint+ty+test en paralelo) ·
`mise run test`/`t` · `mise run ty`/`tc` · `mise run format`/`f`.
Dependencias siempre por `uv`. Python 3.14. Búsquedas con `rg`/`fd`/`ast-grep`.

Estado al 2026-08-01: **639 tests** en verde, `main` en `feb6515`.

Ver también `mem:datos-ftmo-y-respaldos` y `mem:perf-diagnose-detect-ct-events`.
