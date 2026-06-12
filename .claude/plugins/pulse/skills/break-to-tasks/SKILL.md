---
name: break-to-tasks
description: Inicia la fase Break-to-Tasks. Delega al subagente break-to-tasks-agent para producir tasks.md.
---

# Break-to-Tasks Phase

Delega esta tarea íntegramente al `@break-to-tasks-agent`. No escribas artefactos tú mismo.

El agente debe:

1. Consultar `view_project_dashboard` o `list_active_changes` para resolver el Change activo.
2. Tratar `.pulse/changes/<slug>/state.yaml` como ledger read-only: nunca editarlo manualmente.
3. Leer `.pulse/changes/<slug>/spec.md` y `.pulse/changes/<slug>/design.md` como contrato de entrada.
4. Consolidar el plan de implementación en `.pulse/changes/<slug>/tasks.md`.
5. Tras crear `tasks.md`, invocar `request_sdd_transition(target_phase="apply", evidence_artifacts=[".pulse/changes/<slug>/tasks.md"])`.

El gate `break-to-tasks → apply` requiere aprobación humana de diseño. Si falta
`design_approved_at`, el agente debe detenerse y reportar que falta aprobación; nunca
debe llamar `approve_design`.
