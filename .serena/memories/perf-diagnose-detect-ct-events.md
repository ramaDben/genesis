# Cuello de botella del diagnóstico del Candidato A

Medición definitiva con **barras reales** (232.487 M1 de `US500.cash`, ficha FTMO,
horizontes 5/15/30/60), vía `scripts/bench_diagnose.py --from-store US500.cash`:

| Etapa | Tiempo | % |
|---|---|---|
| `iter_bars` (capa 1) | 12,24 s | 0,8% |
| **`detect_ct_events`** (capa 2) | **1.540,92 s** | **98,2%** |
| `summarize_raw_edge` (capa 2) | 15,26 s | 1,0% |
| TOTAL | ~26,1 min por símbolo | |

**Es cuadrático**: al pasar de 78k a 232k barras (×2,98) el tiempo se multiplicó por **11,29**.

## Causa raíz

`src/genesis/strategy/candidate_a/smc/liquidity.py` — `LiquidityMap` **nunca purga los
niveles mitigados**. `apply_close` itera `list(self._levels.items())` completo y descarta por
`timeframe`/`mitigated` *después* de haber iterado. Con ~20.700 swings acumulados, las 84.500
llamadas recorren un diccionario que solo crece.

Palanca dominante verificada: recorrer solo los activos da **68×** con 20.000 niveles y 200
activos. Purgar es seguro — `mitigated` no se usa fuera de `liquidity.py` y `LiquidityMap.get()`
solo se llama con IDs presentes en `active_level_ids`.

Palanca menor: sustituir `dataclasses.replace` por el constructor rinde solo **2,08×**
(≈16,7 s de 199 s en la corrida de 78k, un 8%). No es la palanca principal.

## Trampas metodológicas ya pagadas

- La hipótesis intuitiva era `iter_bars` con `iterrows()`, por analogía con el #24 que vectorizó
  `iter_ticks`. **Mide 0,8%.** Optimizarlo habría sido trabajo perdido: perfilar antes de asumir.
- numba está **descartado** para esta iteración: el problema es algorítmico, y el bucle caliente
  usa frozen dataclasses, `StrEnum` y `dict`, nada compilable en `nopython`.
- El modo `--bars` sintético del bench está acotado a `_MAX_SYNTHETIC_BARS = 110_000` porque
  genera timestamps naive contiguos: al cruzar la transición DST del 2026-03-29 la secuencia deja
  de ser monótona en UTC y la capa 2 aborta con `LookaheadError` (correctamente — el dato de
  entrada es inválido). Para medir a escala real hay que usar `--from-store`.

Plan de optimización con las cinco palancas ordenadas por impacto: **issue #38**.
Falta perfilar `estimate_roundtrip_cost` (capa 4, lee ticks), que el bench no ejercita.
