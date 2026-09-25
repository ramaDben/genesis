# github-memory.md — GitHub como memoria del proyecto

Este documento es la **fuente única de verdad (SSoT)** sobre cómo los agentes interactúan con GitHub, que guarda el estado real del trabajo en issues, labels y PRs.

---

## 1. Identidad del Repositorio

- **Owner**: `ramaDben`
- **Repo**: `genesis`

## 2. Taxonomía de Etiquetas (Labels)

**Regla de oro**: NUNCA crear nuevas etiquetas ni nuevas taxonomías sin autorización explícita humana.

Las familias de etiquetas permitidas son:

- `domain:*` (ej. `domain:data`, `domain:validation`)
- `type:*` (ej. `type:feat`, `type:fix`, `type:chore`, `type:docs`)
- `scope:*` (ej. `scope:backend`)
- `state:diferido` — trabajo reservado a propósito; no se retoma sin decisión explícita.

## 3. Context Hydration

Antes de comenzar a implementar o diseñar una tarea, el agente debe hidratar su contexto interrogando a GitHub:

- Utilizar `mcp__github__search_issues` filtrando por el issue asignado o por la etiqueta `domain:*` correspondiente.
- El contexto en GitHub representa el estado real del issue.

## 4. MCP vs CLI

- **Tool Split**: Utilizar siempre las herramientas del servidor MCP `github` (ej. `mcp__github__search_issues`, `mcp__github__create_pull_request`) por defecto. Proporcionan inputs validados por esquema (Pydantic) y son predecibles.
- **Fallback (`gh`)**: Utilizar la herramienta CLI `gh` únicamente cuando la capacidad requerida no esté expuesta vía MCP (ej. administración profunda de labels o queries GraphQL complejas).
