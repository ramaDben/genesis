*(2026-09-30)*

# Change #130 (B.6): C1 se mide contra el universo declarado, no contra lo que trae el bundle

Cerrado el 2026-09-30 (`closed_at` 14:32Z, bump v0.5.0 → v0.6.0, `f6e25e7`). Commit del delta
`0d797dc`, PR #133. Design aprobado por bbenja11 el 2026-09-30.

## El problema que cerró

C1 (fracción de símbolos que pasan) usaba como denominador **los símbolos que el bundle traía**.
Una estrategia evaluada sobre un solo mercado daba 1/1 = 100 % y emitía GO. Ningún control lo
impedía.

## Lo que quedó

- `CandidateValidationBundle.declared_universe: frozenset[str]` **sin default**, más
  `not_applicable_symbols` (default vacío). Todo símbolo evaluado o marcado "no aplica" debe
  pertenecer al universo; si no, `VerdictConfigError`.
- `build_candidate_gate_summary` abre con la guarda **`|U| < 2 → VerdictConfigError`**: sin
  al menos dos mercados declarados no hay veredicto. C1 = `#PASS / |U|`. Los símbolos ausentes y
  los "no aplica" cuentan como **no superados**.
- `SymbolGateOutcome.status: SymbolGateStatus` (`PASS | FAIL | NOT_APPLICABLE`); `all_pass` pasó a
  property derivada. C2 se calcula sobre `FAIL`, así que no cambia para entradas existentes.
- **H1-A (decisión humana):** se eliminó `_find_go_parcial_candidate`. Con el denominador corregido,
  la rama GO-PARCIAL (`0 < c1 < 0.60`) convertía el GO falso de un símbolo en un GO-PARCIAL falso.
  El SSoT prohíbe eso ("GO-PARCIAL nunca es una vía para eludir C1").
- **H2:** el manifest lleva `verdict_schema_version`; `CONFIG_VERSION` de capa 4 pasó a `/3`.
- Genoma: sección opcional `declared_universe:`, **excluida de `raw_config`**, así que **no entra
  al `trial_id`**. Cambiar el universo declarado no crea un ensayo nuevo en el ledger (D4, H3
  informativo).
- `scripts/run_pipeline.py --declared-universe SYM_A,SYM_B` resuelve el universo **antes de leer
  datos**, para que un universo inválido no queme un ensayo sin registrarlo en el ledger (D5).

Relacionado: el #131 (estrategias de un solo mercado nunca pueden emitir veredicto) es la
consecuencia de política de esta guarda.

## Trampas de este cierre

- El contenedor de pulse del plugin volvió a montar `grupo-analisis-mercado` en vez de genesis
  (misma trampa de `mem:close-change-109-y-la-trampa-del-contenedor-equivocado`). El cierre se
  hizo por JSON-RPC directo (`mem:pulse-engine-sin-plugin`). **Detalle nuevo:** los argumentos de
  las tools van envueltos en `input_data`: `{"input_data": {"slug": "..."}}`. Con `{"slug": ...}`
  suelto el engine responde `Missing required argument input_data`.
- `mise run lint` puede reportar OK con "sources up-to-date, skipping" sin volver a ejecutar;
  para una verificación real, `mise run --force lint:<tarea>`.
