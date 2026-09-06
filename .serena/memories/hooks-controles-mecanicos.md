*(2026-09-05 — hooks encendidos por primera vez. Cinco defectos encontrados y corregidos, todos
verificados con payloads reales, no razonados.)*

# Los hooks: de instrucción a control mecánico

`mem:reserva-de-gobernanza-2026-09` fijó la restricción de diseño: *el enforcement tiene que ser
mecánico, porque una instrucción la puede violar el mismo agente que debería obedecerla.* Los hooks
de Claude Code **son** ese mecanismo, y el proyecto ya tenía la mitad escrita sin usar.

## Lo que estaba apagado

- `.claude/settings.json.example` traía un bloque `hooks` completo. Nunca se renombró; el
  `settings.json` real tenía **cero hooks**.
- `.agents/hooks/sdd_validate_tool.py` (guardián de escritura por fase) y
  `sdd_context_injector.py` existían desde el 2026-08-22, sin cablear.
- El plugin `pulse@genesis`, que traía los hooks vía MCP, **no está instalado**
  (`installed_plugins.json` de Windows: 0 ocurrencias de "pulse"). Ver `mem:pulse-engine-sin-plugin`.

**Consecuencia que reencuadra el precedente de los PR #68/#69**: no había ningún control activo. Con
el guardián encendido, modificar `src/` fuera de la fase `apply` es mecánicamente imposible.

## LA MEDICIÓN QUE ORDENA TODO: los hooks NO pueden correr sobre UNC

Desde una sesión de Claude Code lanzada en Windows, el repo se alcanza por
`//wsl.localhost/Ubuntu/home/bbenja11/genesis`. Ejecutar un hook ahí:

| Ruta | Tiempo | Resultado |
|---|---|---|
| Git Bash de Windows, directo sobre UNC | 3.81 s | ❌ `state.sqlite read error: database is locked` → fase `unknown` → contexto `{}` |
| Despachado por `wsl -d Ubuntu` | **1.45 s** | ✅ fase `explore`, `additionalContext` correcto |

**No falla ruidosamente: emite `{}` y parece que funcionó.** Para un control de seguridad es el peor
modo de falla que existe. Y el rodeo por WSL además es **más rápido**, porque el I/O por UNC cuesta
más que arrancar WSL.

Por eso existe **`.agents/hooks/run_hook.sh`**: detecta `uname -s`, y en `MINGW*/MSYS*/CYGWIN*`
traduce la ruta UNC a ruta Linux y re-ejecuta por `wsl -d Ubuntu -- bash -lc`. Si no puede traducir
la ruta, **falla visible** (exit 1) en vez de adivinar — es la trampa de `mem:entorno-de-desarrollo`
donde los MCP apuntaban a la copia obsoleta sin que nadie lo notara. Cuando la sesión corra dentro
de WSL, el mismo script ejecuta directo y el rodeo desaparece solo.

## Los cinco defectos del guardián — todos fail-open menos uno

El guardián se escribió para Gemini/Antigravity (`_TOOL_NAME_MAP` mapea `write_file`, `replace`).
**La rama de Claude nunca se había ejercitado**, y estaba rota en tres lugares distintos:

1. **`runtime.tool_name` / `tool_args` leían camelCase.** Claude Code envía `tool_name` y
   `tool_input` en snake_case. El nombre salía vacío ⇒ `main()` registraba *"no tool name found,
   allowing"* ⇒ **permitía todo**. Corregido aceptando ambas formas; con tests de regresión en
   `_lib/tests/test_runtime.py`.
2. **`_block` emitía el dialecto de Gemini** (`reject`/`rejectReason`) para el cliente `claude`.
   Claude Code espera `permissionDecision: "deny"` + `permissionDecisionReason` — la forma que
   irónicamente ya tenía la rama `codex`. El bloqueo **se ignoraba en silencio**.
3. **Fail-OPEN con fase desconocida.** Combinado con el lock de SQLite por UNC, la fase era
   *siempre* `unknown` desde Windows ⇒ permitía todo, siempre. Ahora es **fail-closed**: sólo pasa
   la vía rápida.
4. **Serena era un bypass completo.** `tool_name` devuelve `mcp__serena__replace_symbol_body` y el
   mapa tenía la clave desnuda. Corregido quitando el prefijo `mcp__<server>__` con regex, más las
   entradas que faltaban (`replace_lines`, `delete_lines`, `insert_at_line`, `replace_in_files`,
   `rename_symbol`, `safe_delete_symbol`) y la clave `relative_path` en `_extract_paths`.
5. **Sin escape para la vía rápida ⇒ inutilizable.** La allowlist por fase es estricta y en
   `explore` sólo pasa `.pulse/changes/*/idea.md`: encenderlo bloqueaba `docs/`, `scripts/` y
   `.serena/memories/`, o sea toda la vía rápida de `CLAUDE.md`. Se añadió
   `_ALWAYS_ALLOWED_GLOBS`.

**Los defectos 1 y 5 se anulaban mutuamente**: el 1 permitía todo antes de que el 5 pudiera bloquear
todo. Encender el hook arreglando sólo uno habría dado un desastre en cualquiera de las dos
direcciones. Por eso la batería de humo va antes que el encendido.

Además: `_normalize_path` no traducía UNC ni rutas de Windows. Ahora devuelve `None` para lo que cae
fuera del workspace (scratchpad de la sesión, `/tmp`, otro repo) y el llamador **permite** — el ciclo
SDD gobierna este repositorio, no el resto del disco.

## Qué quedó activo

| Evento | Qué hace |
|---|---|
| `SessionStart` → `session_context.py` | Índice de memorias de Serena, rama y commit, fase del engine, issues abiertos no reservados. Convierte «lee las memorias al inicio» de instrucción en hecho. |
| `SessionStart` → `omega_welcome` (`mcp_tool`) | Briefing de OMEGA |
| `UserPromptSubmit` → `sdd_context_injector.py` | Fase del ciclo en cada turno |
| `PreToolUse` → `sdd_validate_tool.py` | Deniega escrituras fuera de fase |

Verificación: `bash .agents/hooks/smoke_test_guard.sh` (20 casos, todos en verde) y
`cd .agents/hooks/_lib && uv run pytest` (15).

## Lo que se descubrió de la doc (context7) y conviene no re-investigar

- Los eventos ya no son nueve: hay `Setup`, `SubagentStart`, `TaskCreated`, `TaskCompleted`,
  `PermissionRequest`, `PermissionDenied`, `PostToolUseFailure`, `PostCompact`, `FileChanged`,
  `InstructionsLoaded`, `Elicitation` y más.
- Tipos de hook: `command`, `http`, `mcp_tool`, `prompt`, `agent`.
- **`mcp_tool` exige que el server MCP ya esté conectado.** Por eso OMEGA en `SessionStart` es
  best-effort y el bloque OMEGA de `session_context.py` avisa si no llegó.
- `once` sólo aplica a hooks declarados en frontmatter de skills — **no** sirve en `settings.json`.
- `Stop`/`SubagentStop` aceptan `{"decision": "block", "reason": ...}` con tope de 8 continuaciones
  consecutivas.
- `PreToolUse` prioriza `deny > defer > ask > allow`.
- El campo `if` permite condicionar un hook con sintaxis de permisos, p. ej. `"Bash(git commit *)"`.

## Debilidad aceptada a sabiendas

`.agents/**` y `.claude/**` están en la vía rápida ⇒ **un agente puede editar los hooks que lo
restringen**: un control capaz de desactivarse a sí mismo. Se acepta porque bloquearlos haría
imposible mantenerlos y porque git deja el rastro. Es la primera excepción que debería escalar al
adjudicador externo del #87.

## Lo que sigue, no hecho

- Deny de `request_sdd_transition(target_phase="close")` — cierra la trampa que costó 18 días
  (`mem:change-55-tick-size-apply`). Hoy no hay tool que interceptar porque el plugin no está
  instalado; la vía real sería un matcher sobre `Bash` contra `scripts/pulse_engine.py`.
- Hooks del #88: denegar `run_pipeline.py` sin un `H-<n>` pre-registrado, y hacer
  `docs/PRE_REGISTRO_HIPOTESIS.md` append-only por construcción.
- `rg` 15.1.0 y `fd` 10.3.0 se instalaron en el WSL el 2026-09-05 (`fd` es un symlink a `fdfind` en
  `~/.local/bin`). Con eso los matchers que prohíben `grep`/`find`/`sed`/`awk` ya son viables, pero
  siguen apagados.

Ver `mem:entorno-de-desarrollo`, `mem:pulse-engine-sin-plugin`,
`mem:reserva-de-gobernanza-2026-09`, `mem:preferencias-de-herramientas`.
