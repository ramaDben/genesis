*(2026-08-29)*

> **OBSOLETA desde 2026-09-25:** pulse se retiró del repo (`scripts/pulse_engine.py` ya no
> existe). Ver `mem:pulse-retirado-2026-09-25`.

# Operar el engine de pulse sin el plugin: JSON-RPC directo al contenedor

## Cuándo hace falta

El plugin `pulse@genesis` **no se instala** en sesiones de Claude Code lanzadas desde Windows,
aunque el repo tenga su `.claude-plugin/marketplace.json` y su `.claude/plugins/pulse/` intactos:

```
✘ Failed to install plugin "pulse@genesis": Cannot install pulse@genesis: its marketplace
  entry path does not stay inside the marketplace directory (an absolute, climbing,
  network-shaped or link-traversing entry, ...)
```

La entrada del marketplace es relativa y correcta (`./.claude/plugins/pulse`), pero resuelta
contra un marketplace en `\\wsl.localhost\Ubuntu\...` queda **network-shaped**, y Claude Code se
niega a instalar desde una ubicación de red. Registrar el marketplace en `extraKnownMarketplaces`
de `~/.claude/settings.json` (scope USER, obligatorio para rutas de red) **sí** lo hace aparecer
en `claude plugin marketplace list`, pero no habilita la instalación.

Solución de raíz: correr Claude Code **dentro** de Ubuntu (`cd ~/genesis && claude`). Al
2026-08-29 `claude` no estaba instalado en WSL; el `npm` que responde ahí es el de Windows
filtrado por `/mnt/c/nvm4w/nodejs`. El instalador nativo (`curl -fsSL https://claude.ai/install.sh
| bash`, verificado: 200, redirige a `downloads.claude.ai`) no necesita node.

## Cómo operar el engine igual

El bloqueo es de **comodidad, no de capacidad**. El engine es un server MCP por stdio en el
contenedor `mcp-pulse:0.13.6`; se le habla con JSON-RPC directo. Así se cerró el change #55.

**Trampa:** redirigir un archivo a `docker run -i` **no funciona** — el server ve EOF y termina
antes de atender la llamada. Solo responde al `initialize`. Hay que mantener el pipe abierto hasta
recibir cada respuesta, o sea usar un cliente de verdad (`subprocess.Popen`, escribir, leer,
recién después cerrar stdin).

Secuencia: `initialize` → `notifications/initialized` → `tools/call`. El banner de FastMCP sale
por stderr y las respuestas JSON por stdout, así que filtrar por líneas que empiecen con `{`.

Invocación (mismos flags que el `.mcp.json` del plugin):

```
docker run -i --rm --user "$(id -u):$(id -g)" \
  -v "$(git rev-parse --show-toplevel):/work" \
  -v pulse-venv:/work/.venv -v uv_warm_cache:/tmp/uv-cache -w /work \
  -e PULSE_WORKSPACE_ROOT=/work -e PULSE_SQLITE_PATH=/work/.pulse/state.sqlite \
  -e UV_HTTP_TIMEOUT=1800 mcp-pulse:0.13.6
```

## Las 10 tools del engine

`request_sdd_transition`, `create_change_from_issue`, `approve_design`, `mark_tests_passed`,
`close_change`, `list_active_changes`, `view_project_dashboard`, y las tres de hooks
(`mcp__pulse__get_current_phase`, `mcp__pulse__log_audit_event`, `mcp__pulse__validate_tool_use`).

## Leer el código del engine

Para verificar una precondición en vez de adivinarla:

```
docker run --rm --entrypoint sh mcp-pulse:0.13.6 -c \
  "grep -rn '<texto del error>' /app --include=*.py"
```

La lógica del ciclo de vida está en `/app/src/pulse/application/change_lifecycle.py`.

## Estado del sqlite

`.pulse/state.sqlite` tiene **una sola tabla** `project_state` con **una fila** (`id='singleton'`)
cuyo campo `json` guarda `{project_id, current_phase, active_mini_specs, active_change_slug,
updated_at}`. El estado **por change** no vive ahí: vive en
`.pulse/changes/<slug>/state.yaml` (que pese al nombre es JSON). `close_change` lee la fase del
change desde el yaml, no del sqlite.

Ver `mem:entorno-de-desarrollo` y `mem:change-55-tick-size-apply`.
