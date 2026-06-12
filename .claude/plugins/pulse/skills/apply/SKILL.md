---
name: apply
description: Inicia la fase Apply. Delega al subagente apply-agent.
---

# Apply Phase

Delega esta tarea íntegramente al `@apply-agent`. No implementes los cambios tú mismo.

El agente debe:

1. Consultar `view_project_dashboard` o `list_active_changes` para resolver el Change activo.
2. Tratar `.pulse/changes/<slug>/state.yaml` como ledger read-only: nunca editarlo manualmente.
3. Leer `design.md` y `tasks.md` bajo el Change activo (`.pulse/changes/<slug>/`) como contrato vinculante.
4. Trabajar en la feature branch creada por el hilo principal (no en la rama por defecto).
5. Implementar todas las tareas de `tasks.md` con edits reales de archivos, respetando las invariantes
   hexagonales (`src/pulse/CLAUDE.md`).
6. Correr la toolchain y dejarla verde: `uv run ruff check` / `uv run ruff format` / `uv run ty` /
   `uv run pytest`.
7. Invocar `mark_tests_passed` y `request_sdd_transition(target_phase="review", ...)` al finalizar.

> **Doctrina TDD (test-first):** Para cada tarea que modifica código ejecutable en `src/`, escribe el
> test primero (RED) antes de implementar (GREEN). Tareas doc-only quedan exentas de tests nuevos,
> pero la suite existente debe quedar verde. Ver `.agents/rules/eval-tdd-conventions.md`.

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
