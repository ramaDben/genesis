## RI-E6 / R70 — redondeo de `sizing_hint` a `volume_step`, PR #68 (2026-08-28)

Bug de producción real, no de infraestructura: el diseño ya documentado (RI-E6/R70,
`.pulse/changes/archive/8-e-.../design.md`) decía explícitamente "el redondeo es del Inspector,
no del candidato" — pero nunca se implementó. `_is_lot_size_out_of_bounds`
(`src/genesis/strategy/inspector.py`) solo *verificaba* proximidad a un múltiplo de
`volume_step` (`lot_step_tolerance`, default `1e-9` ≈ cero) y rechazaba en vez de redondear.

**Esto es exactamente lo que `mem:perf-simulador-y-tickcache` había dejado como "pendiente de
issue propio antes de cualquier corrida del torneo"** (Candidato B rechazado al 100% por
`lot_size_out_of_bounds` en la corrida D) — quedó confirmado hoy contra el broker real (Moneta,
`volume_step=0.1`): config de producción sin overrides rechazaba ~100% de las señales de B
(`WfaConfigError: MIN_TRADES_IS`).

**Fix**: `_rounded_to_volume_step(intent, figure)` nuevo en
`src/genesis/backtest/simulator.py`, aplicado **una sola vez**, justo después de
`intents = self.candidate.on_bar(bar)` en `_process_new_entries`, antes de `risk_levels()` e
`inspect()`. Único punto de inserción correcto porque `wfa.py` y `dsr_pbo.py` instancian el mismo
`Simulator` (verificado por grep, sin caminos duplicados). `risk_levels()` no consume
`sizing_hint` para el cómputo real (patrón pop-on-read vía `self._pending_risk_levels`) —
reordenar es seguro.

**Verificación empírica** (no solo unit tests): con `InspectorFunnelConfig` de producción real
(`min_rr=2.0`, `lot_step_tolerance=1e-9`, sin overrides) sobre datos reales de Moneta,
antes del fix → 0 trades / `MIN_TRADES_IS`; después → 5 ventanas, 48 trades OOS. 729/729 tests,
`ty check` limpio.

Commit `b389ef9` en `main`.
