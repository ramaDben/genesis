# Arquitecto de estrategias y ledger de ensayos (2026-08-10)

Contexto: la idea de un "arquitecto de estrategias" (búsqueda automatizada de configuraciones de
candidato vía un genoma declarativo, no Python) quedó bloqueada por un problema de conteo: el DSR
(`deflated_sharpe_ratio`, gate G4/T1 en `verdict.py`) descuenta por el número de ensayos
(`n_trials`) probados, pero antes de Issue #53 ese `n_trials` solo contaba lo evaluado **dentro de
la corrida en curso** (`n_trials_signal_total` de un `WfaResult` + `(n_candidatos_torneo - 1)` en
T1). Un arquitecto que lanza muchas corridas sucesivas — cada una evaluando y descartando
candidatos — haría que el DSR de una corrida posterior ignorase silenciosamente todos los ensayos
de las corridas anteriores, sub-contando sistemáticamente y relajando el gate de forma indebida
(el error asimétrico que `mem:ledger-de-ensayos-decisiones-de-diseno` llama D2). El bloqueador:
**el ledger de ensayos debía ir primero**, para que el arquitecto (Change futuro) tenga una fuente
de verdad persistente y entre-corridas de "qué ya se evaluó" antes de poder generar/descartar
candidatos en volumen.

## Estado del bloqueador: RESUELTO (Issue #53, implementado en `apply`, ver `mem:ledger-de-ensayos-decisiones-de-diseno`)

- `genesis.validation.trial_ledger` (nuevo módulo, solo stdlib + `errors.py`) persiste un
  `TrialRecord` por `(candidate_id, symbol)` evaluado en `ledger/trials.jsonl` (JSON Lines,
  versionado en git, un escritor). El `trial_id` es un hash determinista de la configuración
  completa del candidato + las 3 claves de identidad institucional de la corrida
  (`dataset_hash_by_symbol`, `firm_profile_hash`, `risk_profile_hash`) — es la única derivación
  sancionada (`TrialLedger.trial_id_for_config`), no hay forma de que un llamador calcule un id
  con otros hashes y produzca una colisión silenciosa.
- **Cómo compone el N**: `run_verdict(..., ledger=...)` toma **un único** snapshot de lectura al
  inicio (`ledger.read_summary()`), calcula
  `extra = len(snapshot.trial_ids - {trial_id de cada candidato evaluado en esta corrida})` y lo sube
  al DSR efectivo (recomputando `deflated_sharpe_ratio` en el punto de llamada, `dsr_pbo.py` sin
  tocar) y a T1 (mismo punto donde ya se suma `(n_candidatos_torneo - 1)`).
- **Por qué con auto-exclusión** (no `n_trials_total` crudo): sin restar los propios `trial_id` de
  la corrida en curso, se doble-cuenta (ya los cuenta `n_trials_signal_total`/T1) y además dos
  invocaciones idénticas de `run_verdict` sobre el mismo ledger darían resultados distintos según
  si el registro de la primera ya se escribió — rompiendo reproducibilidad e idempotencia fuerte.
  `run_verdict` **solo lee**; el registro ocurre en el borde (`record_trial_completions`, invocada
  junto a `write_verdict_artifacts`), nunca dentro del cómputo del veredicto.
- El ledger **solo puede endurecer** el gate G4, nunca relajarlo: `extra >= 0` ⇒
  `dsr_efectivo(extra) <= dsr_efectivo(0)` (invariante con property test).

## Lo que sigue abierto para un futuro Change "arquitecto de estrategias"

- `candidate_config: Mapping[str, object] | None` en `CandidateValidationBundle` es deliberadamente
  un `Mapping` libre, sin esquema fijo: cuando el genoma declarativo exista, entra por ahí sin
  cambiar el contrato del ledger.
- Concurrencia entre escritores (varias corridas del arquitecto en paralelo escribiendo al mismo
  `ledger/trials.jsonl`) queda **fuera de alcance** de Issue #53 — `append_trial` no es atómico
  entre procesos, ver `ledger/README.md`. Cualquier arquitecto que lance corridas paralelas necesita
  resolver esto (locking o un escritor único serializado) antes de escalar.
