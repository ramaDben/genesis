# Pulse retirado del repo (2026-09-25)

Decisión del usuario: **el MCP de pulse no se usa en este entorno**. Se retiró todo lo que
dependía del engine, porque sin él `.pulse/state.sqlite` no existe y el guardián de escritura
quedaba en fail-closed permanente (bloqueaba `src/**`, `tests/**` y hasta `.serena/ty-lsp.sh`).

Qué se quitó:

- Plugin `.claude/plugins/pulse/` y `.claude-plugin/marketplace.json`; `enabledPlugins` y el
  permiso `mcp__plugin_pulse_pulse-engine__*` de `.claude/settings.json`.
- Hooks `PreToolUse` (`sdd_validate_tool.py`) y `UserPromptSubmit` (`sdd_context_injector.py`),
  `smoke_test_guard.sh`, y `pulse_hooks_lib/state.py` con sus tests. Queda sólo `SessionStart`
  (`session_context.py`, sin el bloque de fase, + `omega_welcome`).
- `scripts/pulse_engine.py`, `mise-tasks/docker.toml`, las tareas `mcp:add`/`mcp:inspect-image`,
  las variables `PULSE_*` de `.env.example` y `mise.toml`.

Qué se **conservó**: el directorio `.pulse/` (specs en `.pulse/specs/`, grafo del MCP `memory`
en `.pulse/memory/`, historial de changes archivados) y el nombre del paquete `pulse_hooks_lib`
(sólo helpers genéricos de hooks; renombrarlo tocaría `pyproject.toml`, `uv.lock` y `mise.toml`).

Política que reemplaza al ciclo SDD: cambios de comportamiento o contrato bajo `src/genesis/**`
van por rama → PR → revisión humana. **No hay control mecánico**: la debilidad de
`mem:reserva-de-gobernanza-2026-09` pesa más ahora que antes.

Entorno a esta fecha: usuario Linux `kenno`, repo en `/home/kenno/BenjaLabs/genesis` (Fedora,
Linux nativo, no WSL). `.serena/ty-lsp.sh` resuelve la raíz relativa al script, sin ruta fija.

Desactualiza a: `mem:hooks-controles-mecanicos`, las secciones de pulse de
`mem:entorno-de-desarrollo`, `mem:pulse-engine-sin-plugin`,
`mem:pulse-engine-prefijo-de-tools-en-subagentes`.
