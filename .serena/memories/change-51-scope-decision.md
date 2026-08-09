# Change #51 — decisión de alcance (propose, 2026-08-09) + spec real (specify, 2026-08-09)

`idea.md` describía 3 capas para "un rechazo total de intents por sizing produce un NO_GO
falso": (1) tasa de autorización + veredicto/señal de inválido, (2) pre-flight algebraico de
factibilidad de sizing, (3) política de sizing configurable (`reject`/`clamp_to_min`/
`exclude_symbol`).

`proposal.md` (fase propose) acota el Change a la **Capa 1** y deja 2 y 3 como changes de
seguimiento futuros. `spec.md` (fase specify, escrito 2026-08-09) formaliza Capa 1 con R1-R7 +
evals A1-A7:

- La señal `sizing_evidence_insufficient: bool` vive en `SymbolGateOutcome`
  (`src/genesis/validation/verdict.py`, por símbolo) y se agrega en `CandidateGateSummary` como
  `symbols_with_insufficient_sizing_evidence: frozenset[str]`. **No** toca `VerdictKind` (R91,
  4 miembros) ni `run_verdict` (R92): se calcula en `_build_symbol_gate_outcome`, antes de que
  exista un `VerdictResult`. Decisión fijada por specify; si design la revierte, debe elevarse
  al humano explícitamente (no asumirse).
- Umbral fijado (R3): rechazo **total** (`intents_autorizados == 0 and intents_totales > 0`) con
  motivo dominante `LOT_SIZE_OUT_OF_BOUNDS`. Si `intents_totales == 0` (sin señal de entrada, no
  rechazo de sizing) la señal es `False` — distingue "sin evidencia por sizing" de "sin señal".
  Es un umbral fijo de este Change, no configurable (pregunta abierta P1 en `spec.md`: si el
  negocio quiere una banda de tolerancia en vez de 100 %, requiere decisión humana en un change
  de seguimiento).
- Granularidad (R4): por símbolo, igual que G1-G9, agregada hacia arriba sin colapsar/promediar.

**Hallazgo de verificación H1 (resuelve la pregunta abierta 7 del proposal, ya NO es pregunta
abierta)**: `_resolve_entry_fill` (`src/genesis/backtest/simulator.py:169-185`) tiene tipo de
retorno `ResolvedFill` **no opcional** — nunca `None`: si no hay cobertura de ticks cae al
fallback `bar.open`. `_open_position` (líneas 507-561) se invoca solo cuando
`verdict.authorized is True` y **siempre**, sin condicional, hace
`ledger.append(FillRecord(is_exit=False, ...))`. Conclusión: todo intent autorizado produce
exactamente un `FillRecord` de entrada, sin excepción — la asunción
`n_intents_totales = n_rejections + n_fills_de_entrada` es correcta **por construcción**, no una
inferencia post-hoc frágil. No hace falta un contador explícito de "intents vistos" en
`_process_new_entries` para este Change.

Otros hallazgos de código verificados en specify (2026-08-09): `wfa_result.oos_ledger_cosido`
(`src/genesis/validation/wfa.py:87`) es un `Ledger` completo (con `RejectionRecord`/`FillRecord`),
ya disponible en `_build_symbol_gate_outcome` sin I/O adicional — confirma que R2 es viable sin
tocar la firma de `WfaResult`. `_candidate_summary_payload`/`render_tearsheet`
(`verdict.py:826-930`) son la única fuente de datos compartida por tearsheet y manifest (R97):
ambos deben extenderse ahí (R6) para que la señal llegue a los artefactos serializados.

Ver también `mem:entorno-de-desarrollo`.

## Fase design (2026-08-09) — decisiones fijadas en `design.md`

`design.md` real ya escrito en el Change (reemplaza el placeholder de 151 bytes). Decisiones:

- **Q1/Q2**: función pura nueva `intent_authorization_counts(ledger) -> IntentAuthorizationCounts`
  en `src/genesis/backtest/metrics.py` (capa 3), con `intents_authorized`/`intents_total`/
  `rejections_by_reason: Mapping[str,int]`. **No filtra por símbolo** — precedente:
  `extract_trade_returns` (G1) y `profit_factor` (G3) tampoco filtran el mismo
  `oos_ledger_cosido`; filtrar solo en la función nueva crearía denominadores divergentes.
  `BreachEvent` no cuenta como intent (a diferencia de `rejection_rate_by_reason`, que sí lo
  mete en su denominador — esa función queda intacta, R7).
- **Q3**: `SymbolGateOutcome` gana 4 campos **sin default** (`sizing_evidence_insufficient`,
  `intents_total`, `intents_authorized`, `rejections_by_reason`), después de `all_pass`.
  Se persisten los conteos crudos para que un Change de seguimiento pueda cambiar el umbral sin
  re-ejecutar backtests.
- **Q4**: `CandidateGateSummary.symbols_with_insufficient_sizing_evidence: frozenset[str]`,
  serializado como lista `sorted()` (determinismo).
- **Q5**: solo se extiende `_candidate_summary_payload` (fuente única R97); tearsheet gana una
  columna `sizing_insuf` (paridad mecánica) + una línea por candidato (lectura humana).
- **Q6**: **no** hizo falta un quinto `VerdictKind`. La cláusula de escalado de R5 no se activa.

### Hallazgos de verificación de design (nuevos, no estaban en specify)

- **H2**: `.pulse/specs/validation/spec.md:1819` (R59) y `:1866` (R67) especifican los campos de
  `SymbolGateOutcome`/`CandidateGateSummary` con la fórmula **"con, como mínimo"** → añadir
  campos es compatible con el spec normativo; **este Change no requiere delta de
  `.pulse/specs/validation/spec.md`**.
- **H3**: `src/genesis/backtest/__init__.py` **no** re-exporta nada de `metrics.py` (ni
  `profit_factor`). La función nueva tampoco entra en `__all__` → `test_public_api.py` de
  backtest y validation no cambian; R117/R118 intactos.
- **H4** (cierra el Riesgo 2 del `spec.md`): `SymbolGateOutcome(` se construye en **un único
  sitio** de todo el repo (`verdict.py`; 0 ocurrencias en `tests/`), por eso los campos nuevos
  pueden ir sin default. `tests/validation/test_report_golden.py` congela
  `SignalDiagnosticReport`, **no** el tearsheet/manifest de veredicto; las aserciones de
  `test_verdict.py` sobre tearsheet/manifest son por contenido (`in`), no por igualdad literal.

## Gate humano DESIGN — aprobado 2026-08-09

`approve_design(slug=51-..., approver="bbenja11")` ejecutado el 2026-08-09T15:19:51Z desde la
sesión principal, por instrucción explícita del humano ("apruebo").
`request_sdd_transition(target_phase="break-to-tasks")` con `design.md` como evidencia:
`ok`, `current_phase = break-to-tasks`.

**D1 resuelto por la aprobación**: la contradicción entre R3 ("motivo dominante = mayor conteo",
que sugiere estrictamente mayor) y el eval A7 (`n_lot_size >= n_otros`, el empate favorece a
`LOT_SIZE_OUT_OF_BOUNDS`) queda zanjada **a favor del criterio de A7**, que es el que adopta
`design.md`. No se corrige A7 en `spec.md`; apply implementa el empate favorable a
`LOT_SIZE_OUT_OF_BOUNDS`.

Sigue abierta P1 (umbral 100 % vs. banda de tolerancia), diferida a un change de seguimiento
igual que las capas 2 y 3 del `idea.md`.

**Nota operativa**: los subagentes de propose, specify y design reportaron los tres que
`pulse-engine` no estaba disponible y por eso ninguno ejecutó su transición; desde la sesión
principal el engine respondió al primer intento. Ver la trampa documentada en
`mem:entorno-de-desarrollo`.

## Fase apply (2026-08-09) — resultado real de la implementación

Implementado T1.1-T5.2 de `tasks.md` íntegro, TDD test-first en cada tarea que toca `src/`.

- **Motivo dominante (D1) tal como se implementó**: `_is_sizing_evidence_insufficient` en
  `src/genesis/validation/verdict.py` aplica exactamente el predicado operativo de `tasks.md`:
  `intents_total > 0 and intents_authorized == 0 and n_lot_size > 0 and n_lot_size >=
  max(conteo de cualquier otro motivo, default 0)`. El empate favorece a
  `LOT_SIZE_OUT_OF_BOUNDS`, confirmado por property test (`hypothesis`,
  `test_property_sizing_evidence_insufficient`) sobre `(n_lot_size, n_otros, n_fills)` en
  `[0, 200]³`.
- **Forma final de los campos**: `IntentAuthorizationCounts` (`intents_authorized`,
  `intents_total`, `rejections_by_reason: Mapping[str, int]`) nueva en
  `src/genesis/backtest/metrics.py`, sin filtrar por símbolo/candidato (Q2), `BreachEvent`
  excluido del conteo. `SymbolGateOutcome` ganó 4 campos sin default después de `all_pass`
  (`sizing_evidence_insufficient`, `intents_total`, `intents_authorized`,
  `rejections_by_reason`); `CandidateGateSummary` ganó
  `symbols_with_insufficient_sizing_evidence: frozenset[str]` después de `passes_g_c_p`. Ninguno
  entra en `gN_pass`/`all_pass`/`c1_pass`/`c2_pass`/`pN_pass`/`passes_g_c_p` (verificado por test:
  `passes_g_c_p` se recalcula igual con y sin el campo nuevo).
- **Serialización**: `_candidate_summary_payload` (única fuente compartida, R97) gana las 4
  claves por símbolo (`rejections_by_reason` como `dict(sorted(...))`) y
  `symbols_with_insufficient_sizing_evidence` (lista `sorted()`) por candidato.
  `render_tearsheet` gana la columna `sizing_insuf` en la tabla por símbolo y la línea
  `- Símbolos sin evidencia de sizing: …` por candidato, leyendo solo de ese payload.
  `verdict_result_to_manifest_json`/`VerdictKind` no se tocaron (R5/A6 verificados: 4 miembros).
- **Sin desviaciones de alcance**: no se tocó `run_verdict`, `VerdictKind`, ningún `__init__.py`,
  `test_public_api*`, `rejection_rate_by_reason`, ni `.pulse/specs/**` (H2/H3 confirmados en el
  diff real). `git diff --name-only` tras apply: solo
  `src/genesis/backtest/metrics.py`, `src/genesis/validation/verdict.py`,
  `tests/backtest/test_metrics.py`, `tests/validation/fixtures/ledgers.py`,
  `tests/validation/test_verdict.py` (más este archivo de memoria).
- **Toolchain final**: `mise run ci` exit 0 (ruff check + format, bandit, vulture, deptry, `ty
  check`, `pytest`); `pytest` 666 passed, 1 skipped (baseline previo al Change: 655 passed, 1
  skipped — 11 tests nuevos, ninguno desaparecido).
- **Fixture nueva**: `build_ledger_with_rejections` en `tests/validation/fixtures/ledgers.py`
  (Q8), reutilizada por A1-A4, A7 y el eval propio de T3.1.
