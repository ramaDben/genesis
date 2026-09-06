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

## TRAMPA: un subagente que reporta "MCP no disponible" puede estar equivocado (2026-08-09)

Los subagentes de las fases propose, specify y design del change #51 reportaron los tres, de
forma consecutiva, que `pulse-engine` (y en design también `serena` y `memory`) **no estaba
disponible**, y por eso ninguno ejecutó su `request_sdd_transition`. Verificado desde la sesión
principal inmediatamente después: `view_project_dashboard` y `request_sdd_transition`
respondieron normalmente al primer intento. El síntoma real es del arranque de los servers MCP
(quedan en estado *connecting* mientras el subagente ya está corriendo), no del engine.

Regla operativa: **no dar por buena la afirmación "el MCP no está disponible" de un subagente**.
Verificarlo desde la sesión principal cargando la tool con `ToolSearch` y llamándola; si
responde, ejecutar ahí la transición pendiente. Vale la pena confirmar que los servers están
conectados (`/mcp`) **antes** de lanzar un subagente de fase.

## TRAMPA: `close_change` exige `current_phase="review"`, pero la skill review pide transicionar a `close` primero (2026-08-10)

La skill `pulse:review` instruye textualmente, cuando ambos gates son ✅, llamar
`request_sdd_transition(target_phase="close", evidence_artifacts=[...])`. Eso deja
`state.yaml` con `current_phase: "close"` (fase terminal del FSM). Pero `close_change(slug)` —
la tool que hace el trabajo real de cierre (version bump, promoción de dominio, archivado,
`closed_at`) — **rechaza el Change si no está en fase `"review"`**: `"close_change requiere un
Change en fase review"`. Como `close` es terminal, `request_sdd_transition(target_phase=
"review")` para revertir también falla (`"close solo puede avanzar a la fase siguiente"`) → no
hay tool de pulse-engine para deshacer la transición.

Ocurrió en Issue #53 (2026-08-10): seguí la skill al pie de la letra, quedó
`current_phase=close` con `closed_at=null` (estado huérfano, ni terminal de verdad ni
reabrible). Única salida encontrada: editar a mano **solo** el campo `current_phase` en
`.pulse/changes/<slug>/state.yaml` de vuelta a `"review"` (excepción puntual a la regla de
"nunca editar `state.yaml` a mano", autorizada explícitamente por el humano; no se tocó ningún
otro campo) y recién ahí llamar `close_change(slug)`, que sí completó el cierre real
(`closed_at`, `version_bumped_to`, archivado).

Regla operativa: en la fase review, **no** llamar `request_sdd_transition(target_phase=
"close")` cuando ambos gates son ✅ — llamar directamente `close_change(slug)` desde fase
`review` (sin pasar por `request_sdd_transition`).

**Corregido en el origen el 2026-08-29 (PR #75).** El plugin vive en este repo, así que el
texto culpable se arregló en `.claude/plugins/pulse/skills/review/SKILL.md` y en
`agents/review-agent.md`: ahora instruyen `close_change(slug)` directo y prohíben
explícitamente la transición manual a `close`. Volvió a pasar en el change #55 (2026-08-11),
y esa vez la guarda G2 dejó el flujo SDD entero detenido 18 días — ver
`mem:change-55-tick-size-apply`. Señal de cierre real: `HeuristicsExtracted` en el audit log,
el change movido a `archive/`, y `list_active_changes` en `[]`.

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

## Los hooks se encendieron el 2026-09-05

Ya no hay que acordarse de leer las memorias ni de respetar la fase: `SessionStart` inyecta el
índice de memorias y el estado del repo, y `PreToolUse` deniega escrituras fuera de fase. **Los
hooks NO pueden ejecutarse directamente sobre la ruta UNC** —`.pulse/state.sqlite` responde
`database is locked` y el hook emite contexto vacío sin fallar—; van todos por
`.agents/hooks/run_hook.sh`, que re-ejecuta dentro de WSL. Detalle completo y los cinco defectos
que hubo que corregir antes de encenderlos: `mem:hooks-controles-mecanicos`.

`rg` 15.1.0 y `fd` 10.3.0 ya están instalados en el WSL (antes no estaban, y eso obligaba a caer a
`grep`/`sed`). `fd` es un symlink a `fdfind` en `~/.local/bin`.

Ver también `mem:datos-ftmo-y-respaldos`, `mem:perf-diagnose-detect-ct-events` y
`mem:change-51-scope-decision`.
