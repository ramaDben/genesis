# `ledger/trials.jsonl` — ledger de ensayos persistente entre corridas

Archivo JSON Lines, versionado en git, que registra un `TrialRecord` por cada
ensayo de validación evaluado (Issue #53, `.pulse/changes/53-...`). No confundir
con `genesis.backtest.ledger` (el "ledger de fills" de una corrida de simulación):
este archivo vive un nivel más arriba — es el registro de **qué candidatos se han
evaluado**, no de qué operaciones ejecutó cada uno.

## Qué contiene

Una línea por ensayo, JSON válido, UTF-8, claves ordenadas (`sort_keys=True`) y
separadores compactos, de forma que `git diff` de un ensayo nuevo es exactamente
una línea añadida. Cada fila es la serialización de un
`genesis.validation.trial_ledger.TrialRecord`: identidad del ensayo (`trial_id`
derivado de la configuración completa del candidato + las claves de identidad
institucional de la corrida), `outcome` (`wfa-completado` o `descartado`, con
`discard_reason` obligatorio en el segundo caso) y las claves de trazabilidad
(`config_version`, `dataset_hash_by_symbol`, `firm_profile_hash`,
`risk_profile_hash`, `git_commit`, `recorded_at_utc`).

## Cómo se lee

Con `genesis.validation.trial_ledger.read_trial_summary(ledger_path)` (función
pura, no muta el archivo) o, preferentemente, a través de la fachada
`TrialLedger.read_summary()`. `run_verdict` (`genesis.validation.verdict`) lee un
único snapshot al inicio de cada invocación para componer el N acumulado sobre
los gates G4/T1; **nunca escribe** en el ledger.

## Cómo se escribe

**Restricción de un solo escritor a la vez.** La escritura es responsabilidad exclusiva de
`genesis.validation.trial_ledger.append_trial` (vía `TrialLedger.record`),
invocada desde `genesis.validation.verdict.record_trial_completions` en el borde
de escritura, junto a `write_verdict_artifacts`. La escritura es idempotente por
`trial_id`: registrar el mismo `trial_id` dos veces no agrega una fila nueva. La
concurrencia entre escritores está **fuera de alcance** de Issue #53 — no hay
locking entre procesos; coordinar corridas paralelas es responsabilidad externa
del orquestador hasta que un Change futuro lo aborde.

## Qué NO hacer

**Advertencia: no se edita a mano.** Cualquier edición manual puede introducir un `trial_id`
inconsistente con la configuración real evaluada (colisión silenciosa, es decir
sub-conteo del N que gatea G4/T1) o romper el formato JSON Lines que
`read_trial_summary` exige (fail-fast por línea malformada, sin saltear
silenciosamente ninguna fila). Si hace falta corregir el ledger, generar el
`TrialRecord` correcto por código y usar `append_trial`/`TrialLedger.record`.
