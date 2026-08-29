---
name: review
description: Inicia la fase Review.
---

# Review Phase — Two-Stage Gate

La fase Review implementa un proceso de dos gates secuenciales que garantizan que la
implementacion cumple el contrato de diseno (Gate 1) y los estandares de calidad del proyecto
(Gate 2) antes de avanzar a `close`.

Antes de delegar gates, consulta `view_project_dashboard` o `list_active_changes`
para resolver el Change activo. `.pulse/changes/<slug>/state.yaml` es ledger
read-only del engine: nunca debe editarse manualmente. Los cambios de estado se
solicitan solo mediante Pulse MCP.

## Secuencia de Gates

### Gate 1 — Spec-Compliance (`@spec-compliance-agent`)

Delega a `@spec-compliance-agent`. Este gate verifica:

- Que todos los requisitos de `tasks.md` estan implementados.
- Que no hay features fuera del alcance de `design.md`/`tasks.md` (no over-engineering).
- Que la implementacion no diverge de la direccion de `design.md`.

Resultado esperado: `SPEC_COMPLIANCE: ✅` o `SPEC_COMPLIANCE: ❌ <lista archivos:lineas>`.

**Si Gate 1 retorna ❌:**

- Leer `.pulse/changes/<slug>/spec_compliance_report.md`.
- Reportar al hilo principal con el contenido del report.
- **Detenerse.** No escalar a Gate 2.

### Gate 2 — Code-Quality (`@code-quality-agent`) — solo si Gate 1 es ✅

Delegar a `@code-quality-agent`. Este gate verifica:

- Patrones hexagonales: infraestructura→application→domain.
- Dominio solo importa stdlib + Pydantic V2.
- Secretos como `SecretStr`.
- Docstrings y descripciones en espanol (en archivos de `src/pulse/`).
- Toolchain real: `uv run ruff check` / `uv run ty` / `uv run pytest`.
- Cobertura y calidad de tests.

Resultado esperado: `CODE_QUALITY: ✅` o `CODE_QUALITY: ❌ <lista>`.

El gate crea/actualiza el PR enlazado al issue con **ambos veredictos** (sea ✅ o ❌).

## Regla de Transicion (invariante)

**NO** cerrar el Change hasta que:

1. `spec_compliance_report.md` exista y contenga `SPEC_COMPLIANCE: ✅`.
2. `code_quality_report.md` exista y contenga `CODE_QUALITY: ✅`.

Ambas condiciones deben cumplirse simultaneamente. Una sola falla basta para bloquear.

Cuando ambos son ✅, llamar **directamente**:

```
close_change(slug="<slug>")
```

El Change debe seguir en fase `review` al hacerlo: `close_change` **es** quien lo mueve a
`close`, junto con la promocion del delta, la captura de heuristicas, el bump de version,
`closed_at` y el archivado.

### Por que NO se transiciona a `close` a mano

Hasta el 2026-08-29 esta skill instruia
`request_sdd_transition(target_phase="close", evidence_artifacts=[...])` antes de cerrar. **Eso
deja el Change inservible** y ya ocurrio dos veces (issues #53 y #55):

- `close_change` exige fase `review` — `"close_change requiere un Change en fase review."`
- `close` es fase terminal, asi que no se puede volver — `"ACCESO DENEGADO (SpecGate):
  close solo puede avanzar a la fase siguiente."`
- Y como la guarda **G2** rechaza crear cualquier Change nuevo mientras exista uno sin
  `closed_at`, un solo Change atascado **detiene el flujo SDD entero**. Eso paso entre el
  2026-08-11 y el 2026-08-29.

La unica salida conocida es revertir `current_phase` a `"review"` a mano en
`.pulse/changes/<slug>/state.yaml` **y** en el blob JSON de `.pulse/state.sqlite`, con
autorizacion humana explicita, y recien ahi llamar `close_change`.

### Como verificar que el cierre fue real

- `HeuristicsExtracted` aparece en `.pulse/audit.jsonl` para el slug.
- El directorio del Change se movio a `.pulse/changes/archive/`.
- `list_active_changes` devuelve `[]`.

Si `current_phase` quedo en `"close"` con `closed_at: null`, el cierre **no** ocurrio.

## Prohibiciones

- **NO** hacer edits funcionales de codigo en esta fase.
- **NO** omitir Gate 1 y ejecutar Gate 2 directamente.
- **NO** cerrar con un solo gate ✅.
- **NO** llamar `request_sdd_transition(target_phase="close")` — es lo que rompe el Change.

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

1. Ejecuta `omega_welcome` si es inicio de sesion.
2. Ejecuta `omega_query` con el slug del issue/feature para recuperar contexto previo.
3. Si hay una tarea interrumpida, usa `omega_resume_task`.

Al finalizar esta fase:

1. Almacena decisiones clave con `omega_store` (tipo `decision`).
2. Registra lecciones aprendidas con `omega_store` (tipo `lesson`).
3. Si la tarea queda incompleta, usa `omega_checkpoint` para guardar estado.
4. Si hubo errores recurrentes, registralos con `omega_store` (tipo `error`).
