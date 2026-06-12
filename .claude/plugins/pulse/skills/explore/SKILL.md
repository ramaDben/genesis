---
name: explore
description: Inicia la fase Explore. Delega al subagente explore-agent para explorar el repo y producir idea.md.
---

# Explore Phase

Delega esta tarea íntegramente al `@explore-agent`. No explores el repositorio tú mismo.

El agente debe:

1. Consultar `view_project_dashboard` o `list_active_changes` para resolver el Change activo.
2. Tratar `.pulse/changes/<slug>/state.yaml` como ledger read-only: nunca editarlo manualmente.
3. Explorar el repositorio en modo lectura para recopilar contexto.
4. Consolidar los hallazgos en `.pulse/changes/<slug>/idea.md` (el **`<idea-doc>`**) con las secciones:
   _Problema, Contexto observado, Hipótesis de solución, Preguntas abiertas, Referencias_.
5. Tras crear el `<idea-doc>`, invocar `request_sdd_transition(target_phase="propose", evidence_artifacts=[".pulse/changes/<slug>/idea.md"])`.

El `<idea-doc>` es el **contrato `explore → propose`** — sin él, el SpecGateGuard bloqueará la transición.

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
