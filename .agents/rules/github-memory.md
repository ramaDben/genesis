# github-memory.md — GitHub as FSM Memory

Este documento es la **fuente única de verdad (SSoT)** sobre cómo los agentes interactúan con GitHub, el cual funciona como la memoria principal y motor de estado (FSM Memory) del proyecto Pulse.

---

## 1. Identidad del Repositorio

- **Owner**: `Bajmein`
- **Repo**: `pulse`
- _Nota_: Aunque las rutas locales puedan contener `BenjaLabs`, el owner canónico en GitHub para todas las llamadas MCP es `Bajmein`.

## 2. Taxonomía de Etiquetas (Labels)

El ciclo Spec-Driven Development (SDD) confía en un sistema de etiquetas estrictamente prefijado.

**Regla de oro**: NUNCA crear nuevas etiquetas ni nuevas taxonomías sin autorización explícita humana.

Las familias de etiquetas permitidas son:

- `domain:*` (ej. `domain:mcp`, `domain:fsm`, `domain:workflow`)
- `state:*` (ej. `state:1-explore`, `state:4-apply`, `state:6-close`)
- `type:*` (ej. `type:feat`, `type:fix`, `type:chore`, `type:docs`)
- `scope:*` (ej. `scope:backend`, `scope:plugin`)

**Impacto en el Release**: La etiqueta `type:*` no es meramente descriptiva; dicta matemáticamente el bump de versión semántica (PATCH/MINOR/MAJOR) en `pyproject.toml` durante la transición `close_change`.

## 3. Context Hydration

Antes de comenzar a implementar o diseñar una tarea, el agente debe hidratar su contexto interrogando a GitHub:

- Utilizar `mcp__github__search_issues` filtrando por el issue asignado o por la etiqueta `domain:*` correspondiente.
- El contexto en GitHub representa el estado real del issue, por lo que actúa como la base sobre la que se genera el artefacto FSM en `.pulse/changes/`.

## 4. MCP vs CLI

- **Tool Split**: Utilizar siempre las herramientas del servidor MCP `github` (ej. `mcp__github__search_issues`, `mcp__github__create_pull_request`) por defecto. Proporcionan inputs validados por esquema (Pydantic) y son predecibles.
- **Fallback (`gh`)**: Utilizar la herramienta CLI `gh` únicamente cuando la capacidad requerida no esté expuesta vía MCP (ej. administración profunda de labels o queries GraphQL complejas).
