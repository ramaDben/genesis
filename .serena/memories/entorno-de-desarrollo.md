# Entorno de desarrollo (desde 2026-08-01)

**WSL2 / Ubuntu 26.04, no Windows nativo.** El repo de trabajo es `~/genesis`
(usuario Linux `bbenja11`). **Nunca trabajar en `/mnt/c/Users/bbrav/genesis`**: es la copia
vieja de Windows y el I/O cruza la frontera de filesystems.

Motivo de la migración: el engine de pulse en modo nativo Windows **se cuelga al ejecutar el
gate determinista** (`close_change` sin respuesta a los 1827 s, procesos con CPU 0 y sin logs;
sospecha de interacción de asyncio/FastMCP con `subprocess`, reportado en `Bajmein/pulse#127`).

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

Estado al 2026-08-01: **639 tests** en verde, `main` en `a6429bb`.

Ver también `mem:datos-ftmo-y-respaldos` y `mem:perf-diagnose-detect-ct-events`.
