# Ledger de ensayos (#53) — decisiones de diseño e implementación (2026-08-10)

Observación fechada del `design.md` del Change
`53-feat-validation-ledger-de-ensayos-persistente-entre-corridas-pre`, **implementado en `apply`
el 2026-08-10** (gate `approve_design` ya satisfecho: `design_approved_at = 2026-08-10T16:54:51Z`,
`bbenja11`). Verificar contra el código antes de afirmarlo si esta memoria envejece. Contexto
previo/posterior: `mem:arquitecto-estrategias-y-ledger-ensayos` (el ledger era el prerrequisito
que desbloqueaba al arquitecto de estrategias; el bloqueador del `n_trials` entre corridas queda
resuelto con este Change).

## Lo que resolvió el diseño

- **Composición sobre G4 (P1 del spec)**: en el **punto de llamada** de `verdict.py`, recomputando
  `_dsr.deflated_sharpe_ratio` con `n_trials = n_trials_signal_total + extra`. `dsr_pbo.py` **no se
  toca en ninguna línea** → el docstring normativo de `deflated_sharpe_ratio_gate`
  ("`n_trials` proviene exclusivamente de `wfa_result.n_trials_signal_total`") sigue siendo
  literalmente cierto y R19/R23/Rg-1 se preserva. Descartada la alternativa `extra_trials: int = 0`
  en la firma de `deflated_sharpe_ratio_gate` (reabre un módulo cerrado de Issue I).
  Precedente que lo justifica: `_compute_t1` ya recompone `n_trials` en el punto de llamada.
- **Cortocircuito de byte-identidad**: si `extra == 0`, se reutiliza `dsr_pbo_result.dsr` verbatim
  en vez de recomputar → la no-regresión con `ledger=None` se cumple por construcción, no por
  argumento numérico.
- **Semántica del N con auto-exclusión** (decisión más allá de la letra del spec, **aprobada por el
  humano el 2026-08-10**): `extra = |trial_ids_del_ledger \ trial_ids_de_los_candidatos_evaluados|`, no
  `n_trials_total` crudo. Dos motivos: (a) los ensayos de la corrida en curso ya los cuentan
  `n_trials_signal_total` (G4) y `(n_candidatos_torneo - 1)` (T1) → sumarlos otra vez es doble
  conteo; (b) sin auto-exclusión, dos `run_verdict` idénticos sobre el mismo ledger dan resultados
  distintos (el segundo lee lo que escribió el primero) — rompe reproducibilidad. La idempotencia
  de `append_trial` no basta: evita la fila duplicada, no el cambio de denominador.
- **Orden de operaciones**: un único snapshot de lectura al inicio de `run_verdict` → cómputo
  completo → registro **fuera** de `run_verdict`, en el borde (ver hueco 1b). Da independencia del
  orden de iteración de `candidates` (R94) y hace que el manifest referencie el estado **consumido**.
- **Sin defaults en los helpers privados**: `ledger_extra_trials` es keyword-only obligatorio en
  `_build_symbol_gate_outcome` / `_compute_t1` / `_find_go_parcial_candidate`. Un default de `0` en
  una función privada es el mecanismo por el que un punto de llamada olvidado relaja el gate en
  silencio; sin default, `ty` lo caza en CI. Solo las públicas conservan default (R12/R21).

## Huecos del spec que el diseño detectó (no estaban en `spec.md`)

1. `run_verdict` **no recibe hoy** `dataset_hash_by_symbol` / `firm_profile_hash` /
   `risk_profile_hash` / `git_commit` (los recibe `verdict_result_to_manifest_json`), y
   `CandidateValidationBundle` **no contiene ninguna configuración de candidato** (solo resultados:
   `WfaResult`, `DsrPboResult`, ...). R15/R4 no eran satisfacibles con la firma actual.
   Solución aprobada (2026-08-10), en dos piezas: (a) `CandidateValidationBundle` gana
   `candidate_config: Mapping | None = None` — la config es la identidad de *lo evaluado*, su sitio
   es el bundle; (b) `TrialIdentityContext` reducido a las 4 claves institucionales de la corrida,
   inyectado en el constructor de `TrialLedger`, para que `run_verdict` gane **un solo** parámetro
   (R12/D1). Fail-fast si un bundle evaluado tiene `candidate_config is None`.
   **Descartado a propósito** poner un `trial_id: str` ya calculado en el bundle: sería más simple,
   pero permitiría un id derivado con hashes distintos de los de la corrida ⇒ colisión silenciosa
   ⇒ sub-conteo (el error asimétrico de D2). La derivación tiene una sola implementación,
   `TrialLedger.trial_id_for_config`.
1b. **Enmienda a R15 (autorizada por el humano el 2026-08-10; única modificación del `spec.md`)**:
   R15 obligaba a `run_verdict` a **escribir** en un archivo versionado en git, rompiendo el patrón
   "núcleo puro + I/O en el borde" (toda la escritura de `verdict.py` vivía en
   `write_verdict_artifacts`, R100-R102). Ahora `run_verdict` **solo lee**; el registro vive en
   `record_trial_completions(...)`, invocada junto a `write_verdict_artifacts`. Beneficios: un fallo
   a mitad del cómputo no deja el ledger con ensayos de un veredicto que nunca existió, y la
   idempotencia fuerte se cumple de forma más robusta porque `run_verdict` no escribe en absoluto.
2. `_find_go_parcial_candidate` llama a `_compute_t1` por su cuenta (`verdict.py:762`): hay que
   propagarle el `extra` o la rama `GO_PARCIAL` gatearía con un denominador distinto que `GO`.
3. **CRLF, en las dos direcciones**: `.gitattributes` (`* text=auto eol=lf`) cubre el *checkout*, no
   el proceso. `append_trial` necesita `newline="\n"` explícito al escribir, **y** la lectura para
   el `content_hash` debe ser **binaria** (`read_bytes()`, troceo por `b"\n"`): en modo texto la
   traducción de finales de línea produciría un hash que no describe los bytes en disco, justo en
   el campo cuya única razón de existir es la reproducibilidad byte a byte.
4. `recorded_at_utc` es el único campo no determinista del registro: inyectable y **fuera** de
   `compute_trial_id` (si participara, la idempotencia por `trial_id` sería imposible).

## Invariante nueva que el diseño se autoimpone

> El ledger solo puede **endurecer** un gate, nunca relajarlo: para todo `extra >= 0`,
> `dsr_efectivo(extra) <= dsr_efectivo(0)`. Property test obligatorio.

## Estado del gate DESIGN → APPLY (y de la implementación)

Las tres decisiones normativas fueron **discutidas y aprobadas por el humano el 2026-08-10**:
(1) que una fuente de datos en disco participe en un cálculo que gatea (G4/T1), aceptado con la
mitigación de que `run_verdict` solo lee; (2) la auto-exclusión del N, aunque sea menos severa que
la lectura literal del spec; (3) la enmienda de R15.

`approve_design` quedó registrado (`design_approved_at = 2026-08-10T16:54:51Z`, `bbenja11`) y las
18 tareas de `tasks.md` (T1-T18) se implementaron en `apply` el mismo día: `trial_ledger.py`
existe en `src/genesis/validation/`, con `TrialLedger`/`TrialRecord`/`compute_trial_id`/
`read_trial_summary`/`append_trial`; `verdict.py` gana `candidate_config` en
`CandidateValidationBundle`, `_trial_id_for_bundle`, el `extra` propagado a G4/T1/`GO_PARCIAL`,
`run_verdict(..., ledger=None)` de solo lectura y `record_trial_completions` en el borde de
escritura; `ledger/trials.jsonl` (vacío) + `ledger/README.md` están versionados; `__all__` de
`genesis.validation` re-exporta los 8 nombres de Q9. Toolchain verde (`ruff check`, `ruff format`,
`ty check`, `pytest` — 717 passed / 1 skipped, `deptry`, `bandit`, `vulture`) al cierre de `apply`.

**Trampa CRLF (PR-4), pagada en `apply`**: `newline="\n"` explícito en `append_trial` y lectura
**binaria** (`read_bytes()`, troceo por `b"\n"`) en `read_trial_summary` — necesarios los dos, uno
para lo que se escribe y otro para lo que se hashea, aunque `.gitattributes` ya normalice el
checkout (D4, sin regla nueva). **Ausencia de `rg`/`fd` en el WSL2 de `apply`** (N-1 de
`tasks.md`): los evals "estáticos" A4/A8 se implementaron en `tests/validation/
test_trial_ledger_artifact.py` con `pathlib.Path.read_text()` + `re`/`enum` en vez de shellear
`rg`; A5/A12 sí shellean `git check-ignore`/`git check-attr` porque `git` está disponible. `ty`
usa el comentario de supresión `# ty: ignore[...]`, **no** `# type: ignore[...]` (mypy) — un
`**kwargs: object` reenviado a una función con parámetros `str`/`Mapping` tipados concretos
tampoco se resuelve con una supresión: hubo que tipar `make_discarded_trial_record` con los mismos
kwargs explícitos que `make_trial_record` en vez de `**kwargs`.
