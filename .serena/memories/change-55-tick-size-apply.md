*(Actualizado 2026-08-29 — CERRADO de verdad)*

# Change #55 — cerrado el 2026-08-29, tras 18 días atascado

## Resultado final

- Código en `main` desde el 2026-08-11 (PR #56, commit `d7906a9`): `SymbolFigure.tick_size` +
  `value_per_point`.
- **Cierre real del change ejecutado el 2026-08-29** (PR #72, squash `c994c82`). Produjo:
  - `promote_delta`: **+296 líneas** en `.pulse/specs/data/spec.md` — la spec del #55 entró a la
    SSoT del dominio `data`, donde faltaba desde agosto.
  - `HeuristicsExtracted` en `.pulse/audit.jsonl` (bucle de aprendizaje #63).
  - Bump `0.1.17 → 0.1.18` (el engine lo commitea solo).
  - `closed_at = 2026-08-29T19:23:38Z` y archivado en `.pulse/changes/archive/`.
- `list_active_changes` volvió a `[]`.

## Lo que costó el atasco: la guarda G2

Esto es lo que **no** estaba documentado y explica el daño real. `create_change_from_issue`
rechaza crear cualquier change nuevo mientras exista uno sin `closed_at`:

```python
# G2 (#103): si existe otro Change activo sin cerrar, el switch de contexto
# debe ser explícito (`switch_active=True`); por defecto se bloquea.
if active is not None and active.closed_at is None:
    raise PulseGuardError(f"Ya existe un Change activo sin cerrar: {active_slug}. ...")
```

**El flujo SDD del proyecto no se abandonó por indisciplina: dejó de ser posible el 2026-08-11**,
el día que el #55 quedó atascado. La ruta muerta de Docker en `mise-tasks/mcp.toml` (corregida en
el PR #71) llegó con la migración a WSL2 el ~22 de agosto — fue un segundo muro sobre uno que ya
existía, no la causa.

## Cómo se destrabó

La salida es la que `mem:entorno-de-desarrollo` ya documentaba desde el #53 (2026-08-10) y que
esta memoria, en su versión anterior, declaraba prohibida: revertir `current_phase` a `"review"`
a mano y recién ahí llamar `close_change`. Se aplicó con autorización humana explícita, tocando
**solo** ese campo, en los dos sitios que lo persisten:

- `.pulse/changes/<slug>/state.yaml`
- el blob JSON de `.pulse/state.sqlite` (tabla `project_state`, fila `singleton`)

No se saltó ningún gate: `design_approved_at` (humano) y `tests_passed_at` ya estaban registrados
y quedaron intactos, y `close_change` corrió después el gate determinista de verdad.

## Lección de proceso, no de código

La trampa **ya estaba escrita** en `mem:entorno-de-desarrollo`, con el mismo diagnóstico y la
misma salida, desde el #53. Esta memoria, en cambio, la declaraba sin solución y prohibía el
workaround. Dos memorias en conflicto sobre el mismo hecho, y se actuó sobre la equivocada.

Regla: ante un síntoma de pulse, **leer las dos** (`mem:entorno-de-desarrollo` tiene las trampas
del engine; esta tiene el historial del change). Y cuando una memoria dice "sin salida", buscar si
otra dice lo contrario antes de darla por buena.

## Causa raíz upstream, sin reportar todavía

La skill `pulse:review` instruye llamar `request_sdd_transition(target_phase="close")` cuando
ambos gates son ✅. Eso es lo que rompe: `close_change` es quien debe hacer esa transición, y
exige fase `review`. Mientras esa skill no se corrija, el bug se reproduce en cada change.

Ver `mem:entorno-de-desarrollo` (regla operativa: nunca transicionar a `close`, llamar
`close_change` directo desde `review`) y `mem:pulse-engine-sin-plugin` (cómo operar el engine
cuando el plugin no carga).
