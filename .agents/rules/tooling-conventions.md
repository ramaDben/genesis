<!--
  NOTAS DE MANTENIMIENTO (bloque HTML — no consume contexto).

  Propósito: fuente única de verdad para el tooling del orquestador SDD y los 8 subagentes
  de fase (shell moderno + enrutamiento MCP por intención + matriz fase→MCP). Referenciada
  por las 4 superficies de definición de agentes (canónica, .claude, .gemini, .codex).
  Dueño: equipo Pulse. Origen: issue #85.
  Mantener ≤200 líneas. Si crece, dividir por tema.
-->

# Tooling — orquestador y subagentes SDD

## Contexto del proyecto

El orquestador SDD (hilo principal `/orchestrate`) y los 8 subagentes de fase
(`explore`, `specify`, `design`, `apply`, `spec-compliance`, `code-quality`, `review`,
`close`) se definen en **4 superficies**: la fuente canónica `src/pulse_plugin/agents/`,
y las wirings por cliente `.claude/agents/`, `.gemini/agents/`, `.codex/agents/`.

Esta regla es la **única fuente de verdad** del tooling. Cada superficie la referencia y
declara su allowlist concreta en su formato nativo (no se puede "incluir" entre clientes,
así que se replica de forma disciplinada y se verifica con `rg`). El objetivo: búsquedas
rápidas y precisas, menor privilegio por fase, y paridad multi-cliente sin drift.

## Reglas

- **Siempre** usar `rg` para buscar texto (nunca `grep` crudo).
- **Siempre** usar `fd` para buscar archivos (nunca `find` crudo).
- **Siempre** usar `eza` para listar directorios (nunca `ls` crudo).
- **Siempre** usar `dprint` (vía `dprint-py` en `uv`) y `ruff format` para formatear código.
- Para búsqueda **estructural/AST** usar `ast-grep` (CLI) o serena (LSP), no regex frágiles.
- Para operaciones **semánticas de símbolo** (definición, referencias, overview, rename)
  preferir serena (`find_symbol`, `find_referencing_symbols`, `get_symbols_overview`,
  `replace_symbol_body`) sobre búsqueda textual.
- Enrutar cada intención a la **tool MCP correcta** (ver tabla de enrutamiento).
- Cada agente declara **solo** los MCP de su fila en la matriz fase→MCP (menor privilegio).
- **Nunca** quitar el Bash de tarea de una fase al normalizar la búsqueda (ver "Bash de
  búsqueda vs Bash de tarea").
- **Nunca** declarar tool names de Antigravity (`Replace`, `ReplaceChunk`, `View`, `List`)
  ni `mcp__github_memory__*` en los `tools:` (no resuelven en Claude Code / runtime).

## Mapeo shell canónico

| Intención                  | Tool preferida                                                                        | Evitar                        |
| -------------------------- | ------------------------------------------------------------------------------------- | ----------------------------- |
| buscar texto               | `rg`; símbolos → serena `find_symbol`/`find_referencing_symbols`/`search_for_pattern` | `grep`                        |
| listar directorios         | `eza` (`eza -la`, `eza --tree`)                                                       | `ls`                          |
| buscar archivos            | `fd`                                                                                  | `find`                        |
| búsqueda estructural / AST | `ast-grep` (CLI) · serena (LSP)                                                       | regex multilínea              |
| formateo de código         | `dprint` (vía `uv run dprint`) · `ruff format`                                        | formateadores globales crudos |
| leer archivo               | filesystem `read_file` · serena `get_symbols_overview` · `bat`/`cat`                  | —                             |

## Enrutamiento MCP por intención

| MCP                  | Cuándo usarlo                                                                         |
| -------------------- | ------------------------------------------------------------------------------------- |
| `serena`             | Navegación/edición semántica de símbolos, diagnósticos LSP (`ty check`).              |
| `filesystem`         | Lectura/escritura de archivos del workspace fuera de símbolos.                        |
| `github`             | Memoria FSM: issues, PRs, labels (owner `Bajmein`, repo `pulse`).                     |
| `omega-memory`       | Memoria cognitiva unificada (cross-session, graph, entidades).                        |
| `sequentialthinking` | Razonamiento, planificación, análisis y deducción explícitos.                         |
| `pulse-engine`       | Transiciones FSM, dashboard, gates y lifecycle del Change.                            |
| `context7`           | Ingesta o consulta de memoria distribuida, vectores y bases de conocimiento externas. |

## Baseline universal

Todo agente SDD, según su fase, declara/permite como mínimo:
`Bash(rg *)` + `Bash(fd *)` + `Bash(eza *)` + `Bash(ast-grep *)` + `pulse-engine`,
más `github`/`filesystem` cuando su fase los necesita. Sobre ese baseline se suman **solo**
los MCP de la fila correspondiente de la matriz.

## Matriz fase → MCP (targeted, menor privilegio)

| Agente                       | MCP adicionales (sobre baseline)                   | Bash de tarea (además de búsqueda) | serena                    |
| ---------------------------- | -------------------------------------------------- | ---------------------------------- | ------------------------- |
| orchestrate (hilo principal) | omega-memory, sequentialthinking, context7         | —                                  | —                         |
| explore-agent                | serena, omega-memory, sequentialthinking, context7 | — (read-only)                      | lectura                   |
| specify-agent                | serena, omega-memory, sequentialthinking, context7 | —                                  | lectura                   |
| design-agent                 | serena, omega-memory, sequentialthinking, context7 | —                                  | lectura                   |
| apply-agent                  | serena, sequentialthinking, context7               | `Bash(uv run *)`                   | **full** (edita símbolos) |
| spec-compliance-agent        | serena                                             | `Bash(git *)` (diff/log read-only) | lectura                   |
| code-quality-agent           | serena, github (PR)                                | `Bash(uv run *)` (toolchain)       | lectura                   |
| review-agent                 | — (orquestador delgado)                            | —                                  | —                         |
| close-agent                  | — (baseline mínimo)                                | `Bash(git *)`, `Bash(gh *)`        | —                         |

> **serena lectura** = navegación/inspección (`find_symbol`, `find_referencing_symbols`,
> `find_declaration`, `find_implementations`, `get_symbols_overview`, `search_for_pattern`,
> `get_diagnostics_for_file`). **serena full** = lo anterior + edición de símbolos
> (`replace_symbol_body`, `insert_*`, `rename_symbol`, ...). Solo `apply` recibe full.

## Bash de búsqueda vs Bash de tarea

Normalizar la búsqueda **no** significa quitar el Bash que cada fase necesita para su trabajo:

- `apply` / `code-quality` conservan `Bash(uv run *)` para la toolchain (`ruff`/`dprint`/`ty`/`pytest`).
  - **Nota sobre dprint**: `dprint` es un formateador de código ultra-rápido escrito en Rust (con sistema de plugins). Para invocarlo usamos **dprint-py**, su empaquetado para Python, que permite ejecutar el CLI directamente desde el entorno virtual con `uv run dprint fmt` sin requerir Node o instalación global.
- `spec-compliance` conserva `Bash(git *)` (solo lectura: `git diff`/`git log`/`git status`).
- `close` conserva `Bash(git *)` y `Bash(gh *)` para merge/cleanup/release.

"Reemplazar `grep` por `rg`" reconfigura la parte de **búsqueda/listado/lectura**, nunca el
Bash de tarea de la fase.

## Lo que los agentes NO deben hacer

- No usar `grep`/`ls`/`find` crudos cuando existe `rg`/`eza`/`fd`.
- No declarar `Replace`/`ReplaceChunk`/`View`/`List` (tool names de Antigravity inexistentes
  en Claude Code) ni `mcp__github_memory__*` (servidor no cableado; redundante con `github`).
- No conceder `serena` full a agentes read-only (`explore`/`specify`/`design`/gates de review).
- No ampliar un agente con MCP fuera de su fila de la matriz.

## Referencias

- Issue #85 — estandarización de tooling (este cambio).
- `AGENTS.md` § _Standard MCP Toolchain_ — mandato + matriz resumida (enlaza aquí).
- ADR-09 `docs/architecture/09-github-memory-plugin.md` — _superseded/diferido_ (#85).
- `.claude/settings.local.json` — allowlist `Bash(rg|fd|eza|ast-grep *)`.
- `eval-tdd-conventions.md` — Doctrina EDD+TDD: criterios ejecutables (specify/design) y test-first (apply).
- Issue #40 — Patrones Ruflo (formalización de Swarm, AgentShield, Hooks Adapter).
- Issue #84 — Declarative Gates (impacto en persistencia FSM y orquestación).
