# Cuello de botella del diagnóstico del Candidato A — RESUELTO (Change #46, v0.1.15)

Estado al 2026-08-08: **resuelto y mergeado** (PR #50, `7de0f784`). Issues #38 y #46 cerrados.

## Resultado, medido antes/después en la misma máquina

US500.cash, 232.487 barras M1 reales, ficha FTMO, vía `scripts/bench_diagnose.py --from-store`:

| Etapa | Antes | Después |
|---|---|---|
| `detect_ct_events` | 2.070,89 s | **42,70 s** (48,5×) |
| `iter_bars` | 12,81 s | 12,31 s (sin tocar) |
| `summarize_raw_edge` | 16,75 s | 17,29 s (sin tocar) |
| **TOTAL** | **35,0 min** | **1,2 min** (29×) |
| Los 8 símbolos | 4,7 h | 9,6 min |

**Eventos CT: 15.478 antes y después.** La salida no cambió.

## Los dos cambios, en orden

1. **`liquidity.py`: mitigar es eliminar, no marcar.** `apply_close` hace `del self._levels[id]`
   en vez de `replace(level, mitigated=True)`. Seguro porque `smc/engine.py:203-205` ya
   descartaba los trackers cuyo nivel salió del mapa, y `get()` solo se invoca con ids que
   están en `active_levels()`. El campo `mitigated` se conserva (forma pública) pero ya nunca
   es `True` en el mapa.

2. **`engine.py`: no reconstruir trackers idénticos.** `refreshed = tracker if tracker.level is
   current_level else replace(...)`. Eran **44,8 M de llamadas** a `dataclasses.replace` (y 269 M
   `getattr`) para rehacer objetos iguales.

## La lección: el perfil se mueve cuando lo optimizas

Esta memoria registraba antes que `replace` era "palanca menor, 2,08 %" y que la palanca
dominante era purgar. **Ambas cosas eran ciertas solo en ese momento**: purgar bajó `apply_close`
a 5,5 s de 350 s, y entonces `replace` pasó a ser **dos tercios** del tiempo restante. El
re-perfilado posterior al primer fix es lo que reveló dónde estaba el tiempo de verdad.

Corolario práctico: **perfilar antes de optimizar, y otra vez después.** El segundo perfilado
también evitó trabajo inútil — descartó indexar `add_swing` por `(timeframe, direction)` (la
palanca 5 del issue #38), porque tras la purga `active_levels` + `get` + `apply_close` suman
~6 % y el índice tocaba el orden de iteración que decide qué nivel absorbe un swing.

## Qué queda sin medir

`estimate_roundtrip_cost` (capa 4, lee ticks) sigue fuera del alcance de `bench_diagnose.py`.

Ver también `mem:perf-simulador-y-tickcache` y `mem:entorno-de-desarrollo`.
