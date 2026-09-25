# Tooling — convenciones de shell y MCP

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
| `github`             | Issues, PRs, labels (owner `ramaDben`, repo `genesis`).                                |
| `omega-memory`       | Memoria cognitiva unificada (cross-session, graph, entidades).                        |
| `sequentialthinking` | Razonamiento, planificación, análisis y deducción explícitos.                         |
| `context7`           | Ingesta o consulta de memoria distribuida, vectores y bases de conocimiento externas. |

## Lo que los agentes NO deben hacer

- No usar `grep`/`ls`/`find` crudos cuando existe `rg`/`eza`/`fd`.
- No declarar `Replace`/`ReplaceChunk`/`View`/`List` (tool names de Antigravity inexistentes
  en Claude Code) ni `mcp__github_memory__*` (servidor no cableado; redundante con `github`).
