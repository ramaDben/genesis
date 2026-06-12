---
name: orchestrate
description: Orchestrate the full Pulse SDD lifecycle for a GitHub issue.
---

# Orchestrate Phase

Entry point: `/orchestrate <issue_number>`.

Actúa como orquestador del **hilo principal**. No invoques un subagente orquestador dedicado.

El hilo principal debe coordinar el ciclo; los subagentes de fase solo ejecutan su fase y reportan resultado.

## Flujo obligatorio

1. Hidrata el contexto del issue indicado con GitHub MCP (`mcp__github__search_issues` o `mcp__github__get_issue`).
2. Consulta `view_project_dashboard` y `list_active_changes`.
3. Si el Change no existe, llama `create_change_from_issue` con el issue hidratado, su dominio y labels.
4. Lee `next_agent_hint` del response MCP o del dashboard.
5. Si `awaiting_approval=true` o el Change está en `break-to-tasks` (o `design`) con `design_approved_at=null`, detente y reporta que falta aprobación humana.
6. Si existe `next_agent_hint.agent`, delega exactamente un nivel vía la tool `invoke_subagent` (o su equivalente) al subagente indicado, pasando `next_agent_hint.prompt_context` y el contexto relevante del issue.
7. Cuando el subagente termine, vuelve a consultar `view_project_dashboard` y repite.
8. En fase `review`, usa `close_change` solo cuando el cambio esté listo para promoverse y archivarse.

## Herramientas

Sigue las convenciones de tooling del repo: `.agents/rules/tooling-conventions.md`.
Enruta por intención a la tool MCP correcta (`serena` para símbolos/LSP, `filesystem` para archivos, `github` para memoria FSM, `memory`/`omega-memory` para persistencia cognitiva, `sequentialthinking` para razonamiento, `pulse-engine` para transiciones).

## Restricciones

- No escribas artefactos de fase (`idea.md`, `proposal.md`, `spec.md`, `design.md`, `tasks.md`) desde el hilo principal.
- No implementes código desde el hilo principal.
- No llames `request_sdd_transition` para suplir a un subagente de fase.
- No llames `approve_design`; esa tool es una acción humana externa.
- No encadenes subagentes desde dentro de otros subagentes.

## Memoria Persistente (Knowledge Graph)

Antes de comenzar esta fase:

1. Ejecuta `search_nodes` con el slug del issue/feature para recuperar contexto previo.
2. Revisa entidades relacionadas con `open_nodes`.

Al finalizar esta fase:

1. Crea/actualiza entidades para artefactos producidos.
2. Agrega observations con decisiones clave y su razonamiento.
3. Crea relaciones entre la entidad nueva y entidades existentes relevantes.

## Memoria Persistente (OMEGA)

Antes de comenzar esta fase:

1. Ejecuta `omega_welcome` si es inicio de sesión.
2. Ejecuta `omega_query` con el slug del issue/feature para recuperar contexto previo.
3. Si hay una tarea interrumpida, usa `omega_resume_task`.

Al finalizar esta fase:

1. Almacena decisiones clave con `omega_store` (tipo `decision`).
2. Registra lecciones aprendidas con `omega_store` (tipo `lesson`).
3. Si la tarea queda incompleta, usa `omega_checkpoint` para guardar estado.
4. Si hubo errores recurrentes, regístralos con `omega_store` (tipo `error`).
