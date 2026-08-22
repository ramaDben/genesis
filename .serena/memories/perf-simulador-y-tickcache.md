# Rendimiento del simulador y el `TickCache` (Change #46, v0.1.15)

Baselines archivados fuera del repo: `~/genesis-artifacts/out-change46/bench/*.json`
(el `out/` se mueve antes de cada `close_change`, ver `mem:entorno-de-desarrollo`).

## Medición sobre US500 (232.487 barras, 173 días, 5 repeticiones)

| Magnitud | Baseline | Final |
|---|---|---|
| Tiempo por corrida | 87,34 s | **59,43 s** |
| **Pico de RSS** | **4.005 MB** | **598 MB** |
| `session_window` (llamadas) | 464.974 | **173** |
| `has_chunk` (llamadas) | 232.833 | **519** |

`173` = una por día. `519` = 173 días × 3 chunks de servidor candidatos.

## El dato que más importa: la memoria era un bloqueo, no una molestia

El caché de ticks vivía en cada `Simulator` y **no evictaba nunca**: retenía los ticks de todo
el run. Los 4,0 GB medidos sobre 173 días proyectan **~8,7 GB para una ventana IS+OOS de 378
días**, contra los **7,9 GB** que tiene la VM de WSL. Sin `TickCache` acotado, el WFA no cabe en
memoria para un símbolo de tick alto (NAS100/XAUUSD son 2,5-3× US500).

`TickCache` (`backtest/ticks.py`): LRU acotada a `max_days=2`, **siempre activa, sin flag**. Se
construye una vez por ventana en `wfa._run_single_window` y se inyecta en los 27 combos + el OOS.

**Matiz honesto**: compartir el caché **no** elimina la relectura ×27 mientras los combos corran
en serie — con cota de 2 días, el combo siguiente ya no encuentra nada. Eliminar la relectura
exige invertir los bucles (día externo, combos en lock-step), que quedó fuera por no estar
medido. Lo que 3a resuelve es la **memoria**.

## `bench_simulator.py` reporta si hubo operaciones, y por algo

El bench cuenta `n_exit_fills`. Con la ficha real de la corrida D y `risk_pct=0,375 %`, el
Candidato B propone ~0,8 intents/día y el Inspector **los rechaza todos** por
`lot_size_out_of_bounds` (`tick_value=0,01` + riesgo 375 USD ⇒ lote fuera de `max_lot`).

Consecuencia doble: (a) el bench no ejercita el motor de fills, así que `ticks_in_bar_window` no
aparece en ningún perfil; (b) **si eso se reproduce con la config del torneo, B daría cero trades
OOS y fallaría G1 por construcción** — un NO-GO artificial. Pendiente de issue propio antes de
cualquier corrida del torneo. Sin verificar cuál de las tres es la causa: unidad de `tick_value`
en la ficha, convención del sizing de `CandidateB`, o los límites del `inspector_config.json`.
