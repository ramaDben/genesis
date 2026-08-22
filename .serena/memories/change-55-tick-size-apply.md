*(Actualizado 2026-08-11 — cierre)*

# Change #55 — cerrado en los hechos (PR mergeado), pulse-engine atascado

## Resultado final

- **PR #56 mergeado** (squash) a `main`: commit `d7906a9e7e73fd270f6255b0a9e6fe3b55db2280`. CI y CodeRabbit verdes. Ramas
  remota y local (`fix/55-symbolfigure-tick-size`) eliminadas. `main` local en WSL actualizado (fast-forward).
- El trabajo de código de #55 (`SymbolFigure.tick_size` + `value_per_point`) está **completo y en `main`**.
- El **issue #55 sigue abierto en GitHub** — no se cerró manualmente (decisión del usuario: dejar la
  inconsistencia documentada en vez de forzar cierre a mano o version bump).

## Bug/inconsistencia confirmada en `pulse-engine`: Change atascado en fase `close` sin `close_change`

`list_active_changes` / `get_current_phase` muestran `current_phase: "close"` para el slug
`55-fix-data-symbolfigure-no-captura-tick-size-el-sizing-costos-asum`, con `closed_at: null`,
`version_bumped_to: null`. Es decir: **la FSM ya avanzó a la fase terminal `close` sin que
`close_change` se haya ejecutado nunca** (no hay `closed_at`, no hay bump de versión, no hubo
promoción de delta/archivado).

`close_change(slug)` — la única tool que hace el bump de versión + promoción de delta + archivado —
**rechaza la llamada**: `"close_change requiere un Change en fase review."`. Es decir, exige
`current_phase == "review"` como precondición, pero el estado real ya es `"close"`.

Intenté recuperarlo con `request_sdd_transition(target_phase="review", ...)` para volver a fase
`review` y reintentar `close_change` desde ahí — **rechazado también**:
`"ACCESO DENEGADO (SpecGate): Transición inválida para Change activo: close solo puede avanzar a
la fase siguiente."` La FSM no permite retroceder desde `close`, que es fase terminal.

**Conclusión**: el Change quedó en un estado sin salida con las tools actuales — no hay forma de
ejecutar `close_change` (exige fase `review`) ni de retroceder a `review` (la FSM lo prohíbe desde
`close`). Ninguna otra tool de `pulse-engine` hace el bump de versión/archivado (`create_change_from_issue`,
`approve_design`, `mark_tests_passed`, `request_sdd_transition`, `view_project_dashboard`,
`list_active_changes` son las únicas además de `close_change`).

**Hipótesis de causa raíz**: algo (una sesión anterior, posiblemente el `review-agent` al emitir
ambos gates `si/si`, o un `request_sdd_transition(target_phase="close")` manual) avanzó la fase a
`close` sin pasar por `close_change` — probablemente `close_change` debería ser la tool que hace
*ambas* cosas (transición review→close + archivado), y alguien llamó solo a la transición FSM sin
la tool de cierre real.

## Trampa operativa para la próxima vez

Si un Change llega a `/pulse:close` y `list_active_changes` ya muestra `current_phase: "close"`
con `closed_at: null`, **no asumir que solo falta invocar `close_change`** — probablemente está en
este mismo estado atascado. Verificar con `get_current_phase` + intentar `close_change` primero;
si falla con "requiere fase review", es este bug, no un error de uso. No intentar
`request_sdd_transition` hacia atrás (confirmado que la FSM lo bloquea). Reportar al usuario en vez
de forzar workarounds (edición manual de `state.yaml` está prohibida — es ledger read-only del
engine).

## Pendiente

- Reportar el bug de `pulse-engine` (close_change/FSM inconsistente) — no se abrió issue para esto
  todavía, evaluar si corresponde a este repo o al repo del engine (`ghcr.io/bajmein/pulse`).
  Ver `mem:datos-ftmo-y-respaldos` y CLAUDE.md sobre `mise run docker:pull` — la imagen `:latest`
  del engine ya tiene un problema conocido similar en `promote_delta` (no construir desde ahí,
  usar `main`).
- Issue #55 en GitHub sigue **abierto** — decisión explícita del usuario de no cerrarlo a mano.
- Version bump (`v0.1.17 -> v0.1.18` esperado, label `bug` sin `type:` explícito → fallback patch)
  **no se ejecutó**. `pyproject.toml`/changelog siguen en `v0.1.17`.
- Archivo de `.pulse/changes/55-.../` no se archivó/limpió (queda como Change activo en el ledger
  del engine, aunque el código ya está en `main`).

## Referencia — trabajo de la fase apply (histórico, sin cambios)

T1-T10 implementados y verificados en su momento; toolchain verde (ruff, ty, pytest 729 passed/1
skipped, bandit/vulture sin hallazgos, deptry con 1 hallazgo preexistente no relacionado). T12/T13
no bloqueantes por diseño explícito (G7). Detalles de las trampas de `git stash` y de subagentes
sin `pulse-engine` disponible: ver historial de este mismo archivo en git (`git log -p -- 
.serena/memories/change-55-tick-size-apply.md`) si se necesita el detalle completo.
