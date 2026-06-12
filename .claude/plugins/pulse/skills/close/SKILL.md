---
name: close
description: Inicia la fase Close.
---

# Close Phase

You must delegate this task entirely to the `@close-agent`. Instruct the close agent to perform cleanup and merge the PR if appropriate.

El agente debe comenzar consultando `view_project_dashboard` o `list_active_changes`
para resolver el Change activo. `.pulse/changes/<slug>/state.yaml` es ledger
read-only del engine: nunca debe editarse manualmente. El cierre del Change, version
bump, promoción de delta y archivado deben ocurrir mediante `close_change(slug)`.

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
