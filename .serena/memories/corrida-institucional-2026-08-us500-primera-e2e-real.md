## Primera corrida real de punta a punta, ventana institucional (2026-08-28/29)

Primera vez que genesis corrió el pipeline completo (datos→WFA→Monte Carlo→purged K-fold→
DSR/PBO→sensibilidad→prop_sim→veredicto) con datos reales de broker (Moneta, ~3 años,
2023-09-01→2026-08-29, US500/SP500, 1.055.530 filas M1) y `WfaWindowConfig`/`GridConfig` por
defecto (IS=252/OOS=126/STEP=126 días, sin overrides). Corrida anterior con ventanas reducidas
(IS=45/OOS=10) había sido solo diagnóstico de la costura de RI-E6 (ver
`mem:fix-ri-e6-redondeo-lote-simulador`), no un resultado válido — su WFE=4.28 era ruido de
muestra chica (48 trades OOS vs. 405 en la corrida real).

**Resultado — VEREDICTO: no-go, `c1_fraction_passing=0.0000`**:
n_windows=5, WFE=0.3496, trades_oos=405, DSR=0.0019, PBO=0.1667, PF baseline=1.0676,
`has_cliff=True`, `breach_probability` (MC portfolio)=73.8%, `prop_sim.p_pass=0.122` (1000 paths).
Candidato B sobrevive mecánicamente (genera señales, pasa el redondeo de lote, corre las 5
ventanas) pero no despega en ningún gate económico. Tiempo total: 6184s (~1h43m), dominado por
`trial_matrix+dsr_pbo` (3140s) y `run_wfa` (2878s).

Artefactos en `verdict_artifacts_institucional/manifest.json` + `tearsheet.md` (fuera del repo,
scratchpad de sesión — no versionados).

**Gap explícito, no resuelto**: el `TrialLedger` (Issue #53, `mem:ledger-de-ensayos-decisiones-de-diseno`)
ya existe en el repo, pero ninguno de los runners ad-hoc de esta sesión llamó
`record_trial_completions` — `ledger/trials.jsonl` sigue vacío pese a 3 backtests reales
corridos hoy. El `DSR=0.0019`/`n_trials_signal_total=45` reportado es solo el conteo interno de
la grilla de esta corrida, no un conteo honesto acumulado entre corridas. Cualquier corrida
futura que use estos runners de scratchpad debe wiring el ledger explícitamente o el DSR seguirá
sub-contando entre sesiones.
