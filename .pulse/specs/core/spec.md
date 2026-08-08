
<!-- change:46-perf-core-reducir-complejidad-algor-tmica-del-camino-caliente-y -->
<!-- change:46-perf-core-reducir-complejidad-algor-tmica-del-camino-caliente-y -->
<!-- change:46-perf-core-reducir-complejidad-algor-tmica-del-camino-caliente-y -->
# Specification: perf(core) — reducir complejidad algorítmica del camino caliente y unificar helpers duplicados (Issue #46)

SSoT: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` — los gates G/C/P/T **nunca se
relajan**; ningún requisito de este documento los toca (este Change no cambia ningún cálculo de
negocio, solo el camino de cómputo). Formaliza `idea.md` y `proposal.md` de este Change en
requisitos verificables. Verificado contra el código real en el commit `feb6515`; toda cita
`archivo:línea` de este documento fue releída en esa base antes de escribirse.

Convención de numeración: `R1..Rn` son **propios de este Change** (no continúan la numeración de
ningún spec de módulo previo — mismo criterio que `validation/spec.md` §2 aplicó para H/I/J).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Reducir la complejidad algorítmica y el trabajo invariante recalculado en el camino caliente de
`data/`, `backtest/` y una porción acotada de `validation/`, y decidir de forma explícita y
verificable si se consolidan los helpers duplicados de `validation/` que ADR-H5/ADR-I1/ADR-I2
documentan — sin alterar en ningún caso el resultado observable de un backtest/WFA ya corrido
(equivalencia bit-a-bit, §4). El torneo de candidatos multiplica cada corrida por 27 combos × k
ventanas × 8 símbolos (`wfa.py:210`, C9); este Change paga esa deuda antes de que haya
profundidad de datos suficiente para que el coste se vuelva prohibitivo.

### 1.2. Alcance IN

Ocho bloques de trabajo, cada uno mergeable por separado (§6), sobre:

- `strategy/candidate_a/smc/liquidity.py` (Bloque 1, C1).
- `data/store.py` (`AnnotatedBar`, `iter_bars`) + `backtest/simulator.py`
  (`_enforce_session_close_and_guard`) (Bloque 2, C4+N1).
- `backtest/simulator.py` (`_day_ticks_cache` → `TickCache` compartido) + `validation/wfa.py`
  (`_run_execution_combo`) + `validation/dsr_pbo.py` (`build_signal_trial_matrix`) +
  `validation/sensitivity.py` (Bloque 3, C2+C9).
- `backtest/ticks.py` (`has_sufficient_tick_coverage`, `ticks_in_bar_window`) (Bloque 4, C3+C5).
- `strategy/inspector.py` (`inspect`) + `backtest/simulator.py`
  (`_process_new_entries`/`_register_news_breaches`) (Bloque 5, C6).
- `backtest/metrics.py` (`profit_factor`/`sharpe_pointwise`/`max_drawdown`/`win_rate`) (Bloque 6,
  C7).
- `backtest/simulator.py:551-554` (P&L duplicado en `_close_position`, sin condición) +,
  opcionalmente, módulo(s) interno(s) nuevos de `validation/` para consolidar `_clip` /
  `_default_block_size` / partición contigua / geometría de ventanas, y la decisión de tocar
  `wfa.py`/`montecarlo.py` para importar `_returns.py` (Bloque 7, Q6 + delta de spec, §7).
- `scripts/bench_simulator.py` nuevo, no-pytest (Bloque 0, bench-first, precondición de los
  Bloques 2, 3, 4 y 6).

### 1.3. Alcance OUT (YAGNI explícito)

- **N2** (`data/mt5_export.py:345-352`, manifest O(chunks²)): corre una sola vez por export, no
  en el bucle ×27×k×8 de validación/torneo; el coste dominante real de `run_export` es la latencia
  de red MT5 + la pausa deliberada `pause_range` (`mt5_export.py:554-556`), órdenes de magnitud
  por encima de reescribir un JSON de cientos de KB. Sigue siendo una ineficiencia real y del
  mismo patrón estructural que C1, pero no es camino caliente medido. Follow-up independiente si
  se decide atacarla.
- **N3** (`validation/purged_cv.py:152-192`, rescan de trades por fold): `O(n_folds · n_trades)`
  lineal en la práctica (`PurgedCvConfig.n_folds: int = 5` por defecto); sin evidencia de que se
  configure con valores grandes. Documentado, no se toca.
- **Vectorización de Monte Carlo/PropSim** (`montecarlo.py`, `prop_sim.py`): no cambia la clase de
  complejidad (sigue `O(n_paths·n)`), es el ítem de mayor riesgo frente a la invariante de §4
  (exige demostrar que `cumsum`/`percentile` no reordenan la acumulación *dentro* de cada
  trayectoria) y no hay medición de que sea una fracción significativa del tiempo total de WFA.
  Diferido a un Change propio con su propio bench-first.
- **Reducir 27→9 combos de ejecución** en `wfa.py`/`dsr_pbo.py`: **prohibido explícitamente**, no
  una omisión. `risk_pct` altera el equity del run, que dispara breaches en momentos distintos y
  hace divergentes los caminos tras el primer breach — no es una optimización válida bajo ninguna
  interpretación de este Change (viola §4 directamente: cambiaría qué se computa, no solo cómo).
- **CSCV combinatorio de `dsr_pbo.py`** (`math.comb(n_splits, n_splits // 2)` combinaciones):
  inherente a la definición del método (Bailey, Borwein, López de Prado & Zhu, 2015), no un
  defecto de implementación.
- **`backtest/ticks.py:166-180`** (fallback escalar en transición DST, `_has_dst_transition`): rama
  deliberada y ya documentada (Issue #24) para el puñado de chunks/año con transición real; no se
  vectoriza.
- **`strategy/candidate_b/`**: confirmado limpio en `idea.md` (estado incremental puro, sin
  bucles de recorrido); no se re-audita aquí.
- **Duplicados de `validation/` no enumerados explícitamente en Bloque 7** (§6.7): en particular
  `montecarlo.py:269` (`_extract_exit_returns_by_day`) vs. `prop_sim.py:229`
  (`_extract_exit_deltas_by_day`) — mismo patrón ADR-H8/ADR-I1, pero `proposal.md` no lo incluyó
  en su inventario de Q6 y este documento no le agrega alcance nuevo; y `MIN_TRADES_IS`
  (constante redefinida en `wfa.py`/`dsr_pbo.py` a propósito, spec `validation/spec.md:988`) —
  no es una de las 4 duplicaciones que `proposal.md` puso sobre la mesa.
- Todos los módulos listados como "verificados limpios" en `idea.md`/`proposal.md`
  (`data/calendar.py`, `data/metadata.py`, `data/profile.py`, `data/symbols.py`,
  `data/sessions.py` salvo su frecuencia de invocación (C4/N1), `data/quality.py`,
  `data/mt5_export.py` salvo N2, `validation/montecarlo.py`/`prop_sim.py`/`sensitivity.py`/
  `verdict.py` salvo lo explícitamente listado en Bloque 7, `strategy/common/vwap_engine.py`,
  `strategy/common/zones.py`).

---

## 2. Convenciones de esta especificación

- Requisitos numerados `R1..Rn`, **DEBE**/**NO DEBE**, cada uno verificable por al menos un test o
  una aserción `rg`/`fd`.
- Identificadores en inglés; docstrings y mensajes de error en español.
- **"Equivalencia bit-a-bit"** (usado en todo el documento): dos artefactos (`Ledger`,
  `WfaResult`, `McSymbolResult`, etc.) producidos con el mismo dataset + semilla + config son
  **byte-idénticos** salvo el campo `git_commit` de su metadata de procedencia. Definición
  operativa en §4.
- **"Bloque"**: unidad de trabajo de `proposal.md` §"Bloques de trabajo", revisable y mergeable
  por separado; las dependencias entre bloques son de orden de revisión, no de imposibilidad
  técnica, salvo donde se indique lo contrario (Bloque 4 depende de la estructura de caché del
  Bloque 3).

---

## 3. Resolución de las preguntas abiertas de `idea.md`/`proposal.md`

`proposal.md` cerró las 6 preguntas de `idea.md` con recomendación; este documento las fija como
normativas:

| # | Pregunta | Resolución normativa | Requisitos |
|---|---|---|---|
| 1 | ¿C4+N1 en el mismo Change? | Sí, un solo fix (comparten clave de memoización `trading_day` y multiplicador ×27 de C9) | R20-R27 |
| 2 | ¿Es seguro extender `AnnotatedBar`? | Sí — inventario completo de 6 call-sites de `iter_bars` + 3 construcciones manuales, ninguna hace unpacking posicional | R6-R14 |
| 3 | ¿N2 entra en alcance? | No (§1.3) | — |
| 4 | ¿Vectorizar Monte Carlo? | No (§1.3) | — |
| 5 | ¿`mitigated` de `LiquidityMap` es seguro de purgar? | Sí — confirmado de nuevo en esta sesión (`engine.py:203-205`, `smc/engine.py` es el único consumidor externo de `.get()`/`active_levels()`, ambas llamadas a `.get()` condicionadas a `level_id in active_level_ids`) | R15-R19 |
| 6 | ¿Se levantan R25/R56/R61 de `validation/spec.md`? | Sí, **acotado a este Change** y solo para los pares de helpers verificados como duplicados reales (§7); no para `_extract_exit_returns` de `wfa.py`/`montecarlo.py` salvo decisión explícita adicional (§7.3) | R56-R71 |

Adicionalmente, el bench-first que `proposal.md` exige antes de comprometer N1/N4 (Bloque 0) se
formaliza en R28-R33.

---

## 4. La invariante central: equivalencia observacional bit-a-bit

Esta sección es transversal a los 8 bloques; ningún requisito de §6/§7 puede contradecirla.

- **R1** (DEBE). Para un mismo `(dataset_hash, seed, config)`, todo artefacto producido por el
  código modificado por este Change (`Ledger`, `WfaResult`, `WindowResult`, `McSymbolResult`,
  `McPortfolioResult`, `PurgedCvResult`, `DsrPboResult`, `SensitivityResult`) DEBE ser
  **byte-idéntico** al producido por el código pre-Change, campo por campo, con la única
  excepción de `git_commit` dentro de cualquier metadata de procedencia embebida.
- **R2** (NO DEBE). Ninguna optimización de este Change NO DEBE reordenar una acumulación de
  `float`: `sum(...)` (builtin de Python, orden de iteración de izquierda a derecha) NO DEBE
  sustituirse por `np.sum`/`math.fsum`/una reducción vectorizada de `numpy` sobre el mismo eje de
  acumulación. Verificable: `rg -n "np\.sum\(|math\.fsum\(" src/genesis/backtest/simulator.py
  src/genesis/backtest/metrics.py` DEBE retornar 0 coincidencias nuevas respecto al estado
  pre-Change de esos archivos.
- **R3** (NO DEBE). Ninguna optimización de este Change NO DEBE cambiar el **orden de
  iteración**: `iter_bars` sigue siendo forward-only por `trading_day`/`timestamp_utc` ascendente
  (R32 de `data/spec.md`); el bucle de `_process_bar` sigue procesando `(0) reset diario → (a)
  reloj → (1) gestión de posiciones abiertas → (2) breaches → (3)/(4) cierre de sesión → (5)
  nuevas entradas` en ese orden exacto (`simulator.py:298-324`); `Ledger.entries` sigue siendo
  append-only en el mismo orden de aparición.
- **R4** (DEBE). Toda memoización introducida (Bloques 2, 3, 4) DEBE ser **por invariante real de
  construcción** (`trading_day`, `(símbolo, trading_day)`): el valor cacheado DEBE ser
  matemáticamente idéntico al que se recalcularía sin caché, nunca una aproximación ni un valor
  "suficientemente parecido". Ninguna memoización introduce un `TTL` ni una política de
  invalidación por tiempo de reloj — solo por el avance forward-only del propio dato
  (`trading_day` ya superado).
- **R5** (NO DEBE). Si una optimización propuesta durante `apply` no puede demostrarse
  bit-idéntica mediante un test de equivalencia (golden test comparando ledger/artefacto
  antes/después sobre el mismo fixture y semilla), **se descarta esa optimización**: no se
  documenta como "diferencia aceptable", no se relaja R1 con una tolerancia numérica, y no se
  hace merge del bloque correspondiente. Este es el motivo explícito por el que la vectorización
  de Monte Carlo (§1.3) queda fuera de alcance: nadie ha producido ese test todavía.
- **R6** (DEBE). Cada bloque (1-7) DEBE incluir, como parte de su propio criterio de aceptación
  (§11), un test de equivalencia bit-a-bit específico — no basta con que la suite general de 639
  tests siga en verde; un cambio de complejidad puede preservar todas las aserciones existentes
  y aun así alterar un caso borde no cubierto (p. ej. orden de fills en un empate de timestamp).

---

## 5. Contrato de `AnnotatedBar` (extensión aditiva)

`AnnotatedBar` (`data/store.py:27-38`) es un `@dataclass(frozen=True, slots=True)` con 8 campos,
ninguno con valor por defecto. Este Change lo extiende para que `iter_bars` deje de descartar el
resultado exacto de `session_window` (hoy solo propaga el booleano `in_session`,
`store.py:102-103`), eliminando el doble pago de `session_window` por barra que hoy sufre
`Simulator._enforce_session_close_and_guard` (`simulator.py:414`).

- **R7** (DEBE). `AnnotatedBar` DEBE ganar dos campos nuevos, en este orden, al final de los 8
  existentes: `session_open_utc: datetime`, `session_close_utc: datetime`. Ambos **obligatorios**
  (sin valor por defecto) — válido como extensión de dataclass en Python porque ningún campo
  existente tiene default (regla real: "ningún campo sin default puede seguir a uno con
  default", no "los campos nuevos deben tener default").
- **R8** (DEBE). `iter_bars` DEBE calcular `session_open_utc`/`session_close_utc` invocando
  `session_window(symbol, trading_day)` — la misma invocación que hoy ya hace en la línea 102
  para derivar `in_session` — y exponer la tupla completa en vez de descartar `open_utc`/
  `close_utc`. NO DEBE introducir una segunda invocación de `session_window` por barra: una sola
  llamada por barra basta para derivar `in_session` **y** los dos campos nuevos.
- **R9** (DEBE). Los valores de `session_open_utc`/`session_close_utc` DEBEN ser exactamente los
  mismos que retornaría `session_window(symbol, trading_day)` invocado independientemente para
  ese `trading_day` — ninguna lógica nueva, solo exposición del resultado ya calculado (R31 de
  `data/spec.md`: "marca de sesión derivada de `sessions.session_window`, no de una tabla
  duplicada").
- **R10** (DEBE). `Simulator._enforce_session_close_and_guard` (`simulator.py:410-434`) DEBE
  consumir `bar.session_close_utc` en vez de volver a invocar `session_window(self.symbol,
  bar.trading_day)` (línea 414 actual). `rg -n "session_window\(" src/genesis/backtest/
  simulator.py` DEBE retornar como máximo 1 coincidencia tras el fix (la validación del
  constructor con `_SESSION_PROBE_DATE`, línea 245, que corre una vez por `Simulator`, no por
  barra — no se toca).
- **R11** (DEBE). Las 3 construcciones manuales de `AnnotatedBar` fuera de `iter_bars` DEBEN
  actualizarse para poblar los 2 campos nuevos:
  - `validation/signal_diagnostic.py:84` (`_tick_lookup_bar`) DEBE poblarlos con el valor
    **real**: `session_window(event.symbol, event.trading_day)` (el evento ya trae `.symbol`,
    `strategy/candidate_a/diagnostics.py:42`) — sustituye la promesa actual de "relleno inerte"
    (docstring de la función) por un valor exacto, a costo despreciable (una vez por evento, no
    por barra, fuera de cualquier camino caliente medido).
  - `tests/strategy/fakes.py:35-56` (`make_annotated_bar`) y `tests/strategy/test_clock.py:14-24`
    (`_bar`) DEBEN poblarlos con un valor derivable de `timestamp_utc`/fijo (ninguno de los tests
    que los usan lee esos dos campos hoy) — la firma exacta (parámetro opcional nuevo con default
    vs. valor hardcodeado) se resuelve en `design.md`, sin bloquear este documento.
- **R12** (NO DEBE). Ningún campo nuevo de `AnnotatedBar` NO DEBE tener tipo `Optional`/valor
  `None` como salida silenciosa: si un consumidor futuro construye `AnnotatedBar` sin pasar
  ambos campos, DEBE fallar en tiempo de construcción (`TypeError` de dataclass, detectado por
  `ty`/la suite de tests en el acto), nunca degradar a un `None` que un consumidor olvide poblar.
  Es la razón explícita por la que este documento exige campos obligatorios y no opcionales con
  default `None`.
- **R13** (DEBE). Ningún consumidor existente que solo tipe `bar: AnnotatedBar` sin construirlo
  (`strategy/contract.py:58` `StrategyCandidate.on_bar`, `strategy/clock.py:32`
  `BarClock.advance`) DEBE requerir cambio de código — ambos leen atributos con nombre, ninguno
  hace unpacking posicional ni indexado (`bar[0]`/`*bar`), confirmado por `rg -n "AnnotatedBar\("
  src tests` + inspección manual de los 2 archivos.
- **R14** (DEBE). `tests/` DEBE incluir un test que verifique R8: instrumentando/contando llamadas
  a `session_window` durante una ejecución de `iter_bars` sobre un frame con `N` barras y `D`
  `trading_day` distintos (`D < N`), el número de invocaciones DEBE ser exactamente `D`, no `N`.

---

## 6. Requisitos por bloque de trabajo

### 6.0. Bloque 0 — bench-first (precondición de los Bloques 2, 3, 4 y 6)

`data/store.py::iter_bars` está medido en 0,8% del diagnóstico de Candidato A
(`detect_ct_events`) — un pipeline que **no** pasa por `wfa.py`/`Simulator`. En el pipeline de
WFA el mismo coste se paga ×27 combos × k ventanas × 8 símbolos (C9). El criterio de aceptación
del issue ("mejora medida, no argumentada") exige convertir esa aritmética en un dato antes de
comprometer los Bloques 2/3/4/6.

- **R15** (DEBE). Este Change DEBE agregar `scripts/bench_simulator.py`, mismo patrón no-pytest
  que `scripts/bench_diagnose.py`/`scripts/bench_iter_ticks.py` (no bloquea `mise run ci`).
- **R16** (DEBE). `bench_simulator.py` DEBE cronometrar `Simulator.run(frame)` sobre una ventana
  IS real leída de `--from-store`, reportando desglose por etapa (como mínimo: `iter_bars`,
  `has_sufficient_tick_coverage`, resolución de fills/`ticks_in_bar_window`, `session_window`)
  vía `cProfile` + un flag `--profile-stage`, igual patrón que `bench_diagnose.py`.
- **R17** (DEBE). `bench_simulator.py` DEBE repetir la ejecución **27 veces** sobre el mismo
  slice (replicando el patrón real de `_run_execution_combo`, `wfa.py:210`), de modo que el
  número reportado sea directamente el coste que C9 paga hoy, no una extrapolación aritmética
  post-hoc.
- **R18** (DEBE). `bench_simulator.py` DEBE extrapolar a `k` ventanas × 8 símbolos con un flag
  `--symbols` (mismo patrón que `bench_diagnose.py`).
- **R19** (DEBE). `bench_simulator.py` DEBE poder correrse **hoy** contra el dataset FTMO ya
  exportado (161-174 días, memoria Serena `dataset-ftmo-respaldo`) aunque esté por debajo del
  umbral de 378 días que exige `run_wfa`: apunta a `Simulator.run`/`iter_bars` directamente, no a
  la guarda de historia insuficiente de `run_wfa`.
- **R20** (DEBE). El bloque 0 DEBE producir un reporte baseline (JSON o texto, archivado como
  evidencia del Change) **antes** de aplicar los Bloques 2, 3, 4 o 6, y un reporte posterior tras
  cada uno de esos bloques, con la cifra de mejora medida — ninguno de esos 4 bloques se
  considera cerrado sin su par de reportes antes/después.

### 6.1. Bloque 1 — C1: purga de `LiquidityMap`

Verificado en esta sesión (Q5): `smc/engine.py:191-209` es el único consumidor externo de
`LiquidityMap.get()`/`active_levels()`; ambas invocaciones de `.get()` (líneas 193, 206) están
condicionadas a `level_id in active_level_ids` (línea 191, y el `continue` de la línea 204-205
antes de llegar a la línea 206); `active_level_ids` se construye exclusivamente desde
`active_levels()`, que ya filtra `not level.mitigated`. `SweepTracker.level` es una copia
(`LiquidityLevel` es `frozen`), nunca una referencia viva. `tests/strategy/candidate_a/smc/
test_liquidity.py` solo hace asserts contra `active_levels()` (0 usos de `.get()`, confirmado por
`rg`).

- **R21** (DEBE). `LiquidityMap.apply_close` (`liquidity.py:75-86`) DEBE eliminar (`del
  self._levels[level_id]`) los niveles cuyo cierre los mitiga, en vez de reemplazarlos con
  `replace(level, mitigated=True)`.
- **R22** (DEBE). `LiquidityMap.add_swing` (`liquidity.py:47-73`) DEBE eliminar el chequeo `if
  level.mitigated: continue` (línea 51-52): tras R21, ningún nivel mitigado puede existir en
  `self._levels`, así que el chequeo queda muerto — dejarlo sería un filtro vacío confuso.
- **R23** (DEBE). `LiquidityMap.get(level_id)` DEBE documentar explícitamente en su docstring que
  lanza `KeyError` si `level_id` fue purgado (comportamiento ya real de un `dict`, pero hoy la
  docstring promete "el nivel vigente... para `level_id`" sin condicionar sobre la purga).
- **R24** (NO DEBE). Ningún cambio de este bloque NO DEBE alterar la firma pública de
  `LiquidityMap`/`LiquidityLevel`/`active_levels()` ni el campo `mitigated` de `LiquidityLevel`
  (sigue existiendo como campo del value object emitido antes de purgarse — solo cambia si el
  nivel *mitigado* permanece o no en el dict interno).
- **R25** (DEBE). `tests/strategy/candidate_a/smc/test_liquidity.py` DEBE extenderse con un test
  que confirme: tras `apply_close` mitigar un nivel, `level_id not in` el diccionario interno (o
  equivalente observable vía una API de test), y que `.get(level_id)` lanza `KeyError` para ese
  id.
- **R26** (DEBE). `scripts/bench_diagnose.py --from-store` DEBE correrse antes/después de este
  bloque (patrón ya establecido, no requiere el bench nuevo del Bloque 0) y reportar la mejora
  medida sobre el 98,2%/68× ya documentado (memoria Serena `mem:perf-diagnose-detect-ct-events`).
- **R27** (DEBE, equivalencia bit-a-bit). El resultado de `detect_ct_events`/`summarize_raw_edge`
  sobre el mismo dataset y semilla DEBE ser bit-idéntico antes/después de este bloque — purgar
  del diccionario interno no cambia ningún valor observable de `active_levels()`/`.get()` para
  ningún `level_id` alcanzable (R5, R6).

### 6.2. Bloque 2 — C4+N1: memoización de `session_window`

Requisitos normativos ya fijados en §5 (`R7-R14`). Adicionalmente:

- **R28** (DEBE). Tras aplicar este bloque, `bench_simulator.py` (Bloque 0) DEBE reportar que
  `session_window` se invoca **una vez por `trading_day` distinto** dentro de una ejecución
  completa de `Simulator.run`, no una vez por barra ni dos veces por barra (el doble pago actual
  entre `store.py:102` y `simulator.py:414`).
- **R29** (DEBE, equivalencia bit-a-bit). El `Ledger` producido por `Simulator.run(frame)` sobre
  el mismo dataset/semilla/config DEBE ser bit-idéntico antes/después de este bloque — memoizar
  `session_window` por `trading_day` no cambia el valor de `in_session`/`close_utc` para ninguna
  barra, solo cuántas veces se recalcula.

### 6.3. Bloque 3 — C2+C9: caché de ticks compartida entre combos

Hoy `Simulator.__init__` crea `self._day_ticks_cache: dict[date, list[TickRow]] = {}`
(`simulator.py:263`), sin evicción, con alcance de vida igual al del propio `Simulator`. Cada uno
de los 27 combos de `_run_execution_combo` (`wfa.py:210-247`) instancia un `Simulator` **nuevo**
(R24 de `validation/spec.md`, decisión deliberada, no se revierte: `CandidateB` es stateful por
símbolo/balance de referencia) — cada instancia nueva relee los ticks del disco desde cero para
cada día que toca, 27 veces por ventana.

- **R30** (DEBE). Este Change DEBE introducir un objeto de caché de ticks (`TickCache` o nombre
  equivalente fijado en `design.md`) desacoplado del ciclo de vida de un `Simulator` individual:
  construido **una vez por ventana** (fuera del loop de 27 combos), inyectado en cada instancia
  de `Simulator` de esa ventana.
- **R31** (DEBE). `Simulator.__init__` DEBE aceptar el `TickCache` compartido como parámetro
  (aditivo: si no se provee, DEBE construir uno propio de alcance-`Simulator`, preservando el
  comportamiento actual para cualquier caller que no lo pase explícitamente — p. ej. tests
  existentes que instancian `Simulator` directamente sin pasar por `wfa.py`).
- **R32** (NO DEBE). Arreglar únicamente C2 (evicción acotada dentro de un `Simulator`) sin
  compartir el caché entre las 27 instancias de una ventana NO satisface este bloque: seguiría
  releyendo los ticks del disco 27 veces por ventana (riesgo declarado en §9). La verificación de
  este requisito es que el caché sea el **mismo objeto** (misma identidad, no solo mismo
  contenido) a través de las 27 llamadas de `_run_execution_combo` dentro de una ventana.
  `dsr_pbo.py::build_signal_trial_matrix` y `sensitivity.py::run_sensitivity` (que re-ejecutan
  backtests con el mismo patrón "`Simulator` nuevo por combo") DEBEN heredar el mismo mecanismo
  sin trabajo propio adicional (ya lo hacen gratis si el `TickCache` se inyecta por parámetro
  aditivo, R31).
- **R33** (DEBE). El `TickCache` DEBE tener evicción **acotada**: no retener ticks de todos los
  días de un run completo (el problema original de C2, "6-8 GB/proceso observados en
  producción"). El mecanismo exacto (evicción por tamaño fijo de días vivos, o por
  `trading_day` ya superado según el guard forward-only existente) se fija en `design.md`
  (pregunta abierta #2 de `proposal.md`, §10 de este documento).
- **R34** (NO DEBE). El `TickCache` compartido NO DEBE introducir ningún acceso hacia adelante:
  la evicción es siempre hacia atrás (días ya procesados y superados por el reloj forward-only),
  nunca una prefetch especulativa de días futuros.
- **R35** (DEBE, equivalencia bit-a-bit). El `Ledger`/`WfaResult` producido con el `TickCache`
  compartido DEBE ser bit-idéntico al producido con el `_day_ticks_cache` actual por-`Simulator`,
  para el mismo dataset/semilla/config — compartir el caché entre instancias no cambia qué ticks
  ve cada `Simulator`, solo evita releerlos del disco.
- **R36** (NO DEBE). Este bloque NO DEBE, bajo ninguna circunstancia, intentar reducir las 27
  combinaciones de ejecución a 9 (optimización explícitamente prohibida, §1.3) como forma
  alternativa de abaratar la relectura.
- **R37** (DEBE). `bench_simulator.py` (Bloque 0) DEBE reportar la mejora medida en tiempo de
  I/O de ticks antes/después de este bloque, sobre el mismo slice IS y N=27 repeticiones.

### 6.4. Bloque 4 — C3+C5: cobertura y ventana de ticks

Depende del Bloque 3 (comparte la clave `(símbolo, trading_day)` del caché, `proposal.md`
§"Bloques de trabajo").

- **R38** (DEBE). `has_sufficient_tick_coverage` (`ticks.py:234-262`) DEBE memoizar, por
  `(symbol, trading_day)`, el resultado de `chunk_exists` (hoy 1-3 `Path.exists()` por barra vía
  `store.has_chunk`, invariante por día — el chunk no cambia entre barras del mismo día).
- **R39** (DEBE). `ticks_in_bar_window` (`ticks.py:265-274`) DEBE invocarse **una sola vez por
  barra** dentro de `Simulator._process_bar` y su cadena de llamadas (`_manage_open_positions`,
  `_enforce_session_close_and_guard`/`_force_close_all_positions`, `_process_new_entries`/
  `_open_position`), reutilizando el mismo resultado en vez de reconstruirlo en cada punto que
  hoy lo invoca de forma independiente (`simulator.py:132,181,505,547` según el inventario de
  `idea.md`).
- **R40** (NO DEBE). La slice retornada por `_bisect_window_bounds` (`ticks.py:219-231`) NO DEBE
  copiarse dos veces: `ticks_in_bar_window` ya retorna `list(day_ticks[start_idx:end_idx])`
  (`ticks.py:274`) — ningún llamador nuevo DEBE volver a envolver ese resultado en `list(...)`
  sobre un slice que ya es una lista nueva.
- **R41** (DEBE, equivalencia bit-a-bit). El conjunto de ticks efectivamente usado para resolver
  cada fill (entrada, salida, cierre forzado) DEBE ser exactamente el mismo antes/después de este
  bloque — memoizar `chunk_exists` y compartir `ticks_in_bar_window` por barra no cambia qué
  ticks caen en la ventana `(T-60s, T]` de cada barra, solo cuántas veces se recalcula el mismo
  resultado.
- **R42** (DEBE). `bench_simulator.py` DEBE reportar la mejora medida en la etapa
  `has_sufficient_tick_coverage`/resolución de fills antes/después de este bloque.
- **R43** (DEBE). Este bloque DEBE incluir un test que cuente invocaciones a `store.has_chunk`
  (mock/spy) durante la ejecución de una barra para confirmar que la existencia de chunk se
  consulta como máximo una vez por `(symbol, trading_day)` distinto, no una vez por barra.

### 6.5. Bloque 5 — C6: hoist de `news_windows`

Ver riesgo declarado en §9 — este es el único bloque que cambia el **momento** de una excepción
existente.

- **R44** (DEBE). `news_windows(self.news_events, self.symbol, self.firm_profile)` DEBE
  calcularse **una sola vez** por `Simulator` (en su constructor, ya que recibe `news_events`/
  `symbol`/`firm_profile` en `__init__`), en vez de recalcularse en cada invocación de
  `inspect()` (`inspector.py:102`, una vez por intent propuesto) y en cada cierre de posición
  (`_register_news_breaches`, `simulator.py:597`).
- **R45** (DEBE). Como `inspect()` es una función pura de `genesis.strategy.inspector` (capa 2)
  que hoy recibe `news_events: Sequence[EconomicEvent]` y calcula `news_windows` internamente
  (`inspector.py:102`), este bloque DEBE decidir en `design.md` uno de dos mecanismos, ambos
  aditivos: **(a)** extender la firma de `inspect()` con un parámetro `news_windows` ya
  calculado (manteniendo `news_events` para compatibilidad o retirándolo), o **(b)** que
  `Simulator` calcule `news_windows` una vez y lo use solo para `_register_news_breaches`,
  dejando la llamada de `inspect()` sin memoizar (fix parcial, documentado como tal si se elige).
  Este documento no prejuzga cuál: exige que la decisión sea explícita en `design.md`, no
  implícita en el código.
- **R46** (DEBE). Los tests existentes que construyen un `Simulator` con eventos de calendario
  **naive** (sin `tzinfo`) sin cerrar ninguna posición DEBEN auditarse y actualizarse: hoy esos
  tests no fallan porque `news_windows` nunca se invoca si no hay cierre de posición ni intent
  propuesto con eventos naive; tras este bloque, `CalendarError` se dispara en la construcción
  del `Simulator` (riesgo §9), y esos tests fallarían de forma distinta a como fallan hoy si es
  que fallan.
- **R47** (DEBE, equivalencia bit-a-bit). Para cualquier ejecución que hoy **no** dispara
  `CalendarError` (eventos ya tz-aware, o ningún evento HIGH relevante para el símbolo), el
  resultado de `Simulator.run` DEBE ser bit-idéntico antes/después de este bloque.
- **R48** (NO DEBE). Este bloque NO DEBE capturar ni envolver silenciosamente el
  `CalendarError` adelantado — sigue siendo fail-fast, solo más temprano (mismo criterio que R5
  de `validation/spec.md`: ninguna excepción de dominio se envuelve).
- **R49** (DEBE). `bench_simulator.py`/tests de este bloque DEBEN confirmar que `news_windows` se
  invoca exactamente una vez por `Simulator` construido (spy/contador), no una vez por intent ni
  una vez por cierre.

### 6.6. Bloque 6 — C7: una sola pasada de métricas del ledger

`profit_factor`, `sharpe_pointwise`, `max_drawdown`, `win_rate` (`backtest/metrics.py:42-83`)
invocan cada uno, independientemente, a `_exit_deltas`/`_running_equity_deltas`
(`metrics.py:21-39`), que recorren `ledger.entries` completo — confirmado: 4 recorridos O(N)
separados por invocación conjunta de las 4 métricas.

- **R50** (DEBE). Este Change DEBE consolidar el recorrido de `ledger.entries` que hoy hacen
  `profit_factor`/`sharpe_pointwise`/`max_drawdown`/`win_rate` en, como máximo, **una** pasada
  compartida cuando las 4 métricas se invocan sobre el mismo `Ledger` en el mismo punto de
  llamada (p. ej. un snapshot/objeto intermedio que las 4 funciones públicas consumen, o
  memoización por identidad del `Ledger`). El mecanismo exacto (`_ledger_metrics_snapshot`
  compartido vs. memoización por `id(ledger)`) se fija en `design.md` (pregunta abierta #3).
- **R51** (NO DEBE). Este bloque NO DEBE cambiar la **firma pública** de
  `profit_factor`/`sharpe_pointwise`/`max_drawdown`/`win_rate` (siguen aceptando `ledger: Ledger`
  y retornando `float`) — la consolidación es un detalle de implementación interno, no un cambio
  de API consumida por `wfa.py`/`montecarlo.py`/`sensitivity.py`/`verdict.py`.
- **R52** (DEBE, equivalencia bit-a-bit). Cada una de las 4 métricas DEBE retornar exactamente el
  mismo valor `float` antes/después de este bloque, para el mismo `Ledger` — consolidar el
  recorrido no cambia el orden en que se suman los deltas (R2/R3: sigue siendo `sum()` sobre la
  misma secuencia en el mismo orden de aparición).
- **R53** (DEBE). `bench_simulator.py` (extendido, R20) DEBE medir la porción de `metrics.py`
  dentro de una corrida completa antes/después de este bloque — mismo criterio de "medir antes"
  que N1/N4, dado que este bloque tampoco cambia la clase de complejidad (sigue siendo O(N) por
  invocación conjunta, solo con constante menor).
- **R54** (DEBE). Este bloque DEBE incluir, además del test de equivalencia (R52), una prueba de
  que el número de recorridos completos de `ledger.entries` se redujo (instrumentación/spy sobre
  `_running_equity_deltas`/`_exit_deltas` o su reemplazo), no solo que el resultado no cambió.
- **R55** (DEBE). `simulator.py:551-554` (`_close_position`) y `simulator.py:334-338`
  (`_floating_pnl`) — que hoy calculan la misma fórmula de P&L en puntos (`direction_sign` ×
  `points`/`pnl_points` × `sizing_hint` × `tick_value`) de forma independiente en el mismo
  archivo — DEBEN consolidarse: `_close_position` DEBE invocar `self._floating_pnl(position,
  fill.price)` para obtener `pnl_gross`/`pnl_points` en vez de reimplementar la fórmula. Este
  requisito es **incondicional**: no depende de la decisión de Bloque 7 (mismo archivo, sin
  excusa arquitectónica de módulos cerrados).
- **R56** (DEBE, equivalencia bit-a-bit). El valor de `pnl_gross`/`account.balance` tras cerrar
  una posición DEBE ser exactamente el mismo antes/después de R55 — es la misma expresión
  aritmética, solo invocada desde un único punto.

### 6.7. Bloque 7 — Consolidación de duplicados de `validation/` y delta de spec

Ver §7 (delta de spec normativo) y §9 (riesgos). Verificado en esta sesión, no heredado
literalmente de `proposal.md`:

- `_clip` (`max(low, min(high, value))`) es **byte-idéntico** en `montecarlo.py:107-108`,
  `prop_sim.py:220-221`, `purged_cv.py:27-28` — 3 copias reales, consolidables sin cambio de
  comportamiento en ningún call-site.
- `_default_block_size` es **idéntico** en `montecarlo.py:111-113`/`prop_sim.py:224-226`
  (`clip(round(n ** (1/3)), 5, 60)`) pero **DISTINTO** en
  `strategy/candidate_a/diagnostics.py:166-176` (`clip(round(n ** (1/3)), 1, max(1, n))` — la
  propia docstring de esta última lo llama "variante local sin piso de 5"). **No son 3 copias de
  lo mismo**: son 2 copias reales + 1 variante deliberada con bounds distintos.
- `_first_fill_record` difiere en firma y excepción entre `montecarlo.py:98-104`
  (`(ledger) -> FillRecord`, lanza `MonteCarloConfigError`) y `purged_cv.py:87-96`
  (`(ledger, *, candidate_id) -> FillRecord`, lanza `PurgedCvConfigError`) — mismo algoritmo
  (primer `FillRecord` del ledger), distinta interfaz.
- `_contiguous_partition_bounds` (`purged_cv.py:108-117`, retorna `list[tuple[int, int]]`) y
  `_contiguous_blocks` (`dsr_pbo.py:99-114`, retorna `list[list[int]]`) son el mismo algoritmo de
  partición contigua `±1`, con forma de retorno distinta — `dsr_pbo.py:102-105` documenta
  explícitamente la duplicación como deliberada (ADR-H5/ADR-I1).
- `_windowing.py` (`validation/_windowing.py:1-10`, ADR-I2) ya es un módulo interno compartido
  entre `dsr_pbo.py`/`sensitivity.py` que **reimplementa** (no importa) la geometría de
  `wfa.py._plan_windows`/`_iter_window_bounds`/`_slice_frame_by_days`, precisamente para no
  importar símbolos privados de `wfa.py` (cita literalmente "R25" en su propio docstring).
- `wfa.py._extract_exit_returns` (`wfa.py:94-109`) y `montecarlo.py._extract_exit_returns`
  (`montecarlo.py:72-87`) son **byte-idénticos**; `validation/spec.md:799-807` documenta que
  ADR-I1 (`_returns.py`) se creó explícitamente **sin** tocar este par ("decisión de H que no se
  revierte").

Requisitos:

- **R57** (DEBE). Este Change DEBE crear al menos un módulo interno nuevo bajo
  `src/genesis/validation/` (prefijo `_`, NO exportado en `__init__.__all__`, mismo patrón que
  `_dsr.py`/`_returns.py`/`_windowing.py`) que contenga una única definición de `_clip`, y
  actualizar `montecarlo.py`, `prop_sim.py`, `purged_cv.py` para importarla en vez de redefinirla
  localmente. El nombre exacto del módulo (`_shared_math.py`, ampliar `_returns.py`, u otro) se
  fija en `design.md` (pregunta abierta #1 de `proposal.md`).
- **R58** (NO DEBE). Este bloque NO DEBE consolidar `strategy/candidate_a/diagnostics.py`'s
  `_default_block_size` con el de `montecarlo.py`/`prop_sim.py` **salvo** que el helper
  compartido acepte `low`/`high` como parámetros explícitos (no hardcodeados), de forma que cada
  call-site seleccione sus propios bounds (`5, 60` para `montecarlo.py`/`prop_sim.py`; `1,
  max(1, n)` para `diagnostics.py`) y produzca exactamente el mismo valor que produce hoy. Fusionar
  las 3 definiciones a ciegas (mismos bounds para las 3) violaría R1/R5 al cambiar el
  comportamiento observable de `diagnostics.py`.
- **R59** (DEBE). Si se consolida `_default_block_size` (montecarlo.py + prop_sim.py, las 2
  copias byte-idénticas), la función compartida DEBE seguir devolviendo exactamente
  `clip(round(n ** (1/3)), 5, 60)` para ambos call-sites — un test de igualdad, no solo de
  comportamiento paralelo (a diferencia de `tests/validation/test_extract_returns.py`, que hoy
  solo verifica equivalencia de comportamiento entre pares, no una prohibición de import
  verificada por CI).
- **R60** (DEBE). La consolidación de `_first_fill_record` (si se decide, opcional) DEBE
  preservar, por call-site, tanto el valor de retorno como el **tipo de excepción** lanzado hoy
  (`MonteCarloConfigError` para `montecarlo.py`, `PurgedCvConfigError` para `purged_cv.py`) — un
  helper compartido DEBE aceptar la excepción/mensaje como parámetro (p. ej. una función factory
  o un parámetro `error_cls`), nunca unificar a un único tipo de excepción que rompería R59
  para uno de los dos call-sites.
- **R61** (DEBE). La consolidación de `_contiguous_partition_bounds`/`_contiguous_blocks` (si se
  decide, opcional) DEBE preservar la forma de retorno de cada call-site (`list[tuple[int,
  int]]` para `purged_cv.py`, `list[list[int]]` para `dsr_pbo.py`) — vía una función base
  compartida más un adaptador de forma en cada módulo, o exponiendo ambas formas desde el módulo
  compartido.
- **R62** (DEBE). Si `design.md` decide levantar la protección de ADR-H5 para
  `_extract_exit_returns` (haciendo que `wfa.py`/`montecarlo.py` importen una función compartida
  en vez de redefinirla), DEBE hacerlo como una decisión **explícita y documentada** en el propio
  código (docstring de la función/módulo compartido citando que reemplaza ADR-H5 para este
  Change, con el número de Change), no un cambio silencioso de import. Este documento NO exige
  que se haga (§7.3) — solo fija la condición si se hace.
- **R63** (NO DEBE). Ningún módulo interno nuevo de este bloque NO DEBE exportarse en
  `src/genesis/validation/__init__.py` (`__all__`) — mismo patrón de visibilidad que `_dsr.py`/
  `_returns.py`/`_windowing.py`. `rg -n "^from genesis\.validation\._" src/genesis/validation/
  __init__.py` DEBE retornar 0 coincidencias nuevas.
- **R64** (DEBE, equivalencia bit-a-bit). Para cada función consolidada, un test DEBE confirmar
  que el resultado del helper compartido es **igual** (no solo "de comportamiento equivalente")
  al de cada una de las implementaciones que reemplaza, sobre el mismo conjunto de casos que
  cubrían los tests previos de cada copia.
- **R65** (DEBE). Si, durante `apply`, se decide **no** levantar ninguna protección de ADR-H5/
  ADR-I1/ADR-I2 (mantener las duplicaciones como decisión permanente), los Bloques 1-6 de este
  Change permanecen intactos: Bloque 7 es el único opcional y revertible sin bloquear ningún otro.

---

## 7. Delta de spec: alcance y límites de la relajación de R25/R56/R61 (`validation/spec.md`)

### 7.1. Corrección de la cita heredada de `idea.md`

`idea.md` cita "ADR-H5, R25/R56/R61: prohibido importar símbolos privados de un módulo cerrado"
como si los tres números refirieran a la misma regla. Verificado contra
`.pulse/specs/validation/spec.md`: **no es así**, y este documento corrige la cita antes de
decidir sobre ella.

| Regla citada | Documento/línea | Texto real | ¿Es "prohibición de importar privados"? |
|---|---|---|---|
| R61 (Issue H) | `validation/spec.md:425-427` | "Ningún archivo de `data/`, `strategy/`, `backtest/` DEBE modificarse en este Change [H]" | No — es congelamiento de alcance de H, no una regla de import |
| R9 (Issue I, ADR-I1) | `validation/spec.md:865-868` | "`_returns.py` NO DEBE ser importado por `wfa.py` ni `montecarlo.py`" | Sí — la regla real de no-acoplar módulos cerrados vía import |
| R25 (Issue I, ADR-I2) | `validation/spec.md:939-944` + `_windowing.py:1-10` | "`build_signal_trial_matrix` ... SIN importar ningún símbolo privado de `wfa.py`" | Sí — esta es la cita correcta para "prohibido importar privados" |
| R56 (Issue I) | `validation/spec.md:1091-1096` | "Ningún archivo de `data/`, `strategy/`, `backtest/`, `wfa.py`, `montecarlo.py`, `_dsr.py`, `window_config.py` DEBE modificarse en este Change [I]" | No — congelamiento de alcance de I, no una regla de import |
| R61 (Issue I) | `validation/spec.md:1115-1117` | "Ningún artefacto de este Change DEBE serializarse a disco" | No — regla de persistencia, sin relación con imports |

La regla efectivamente en juego para Bloque 7 es **R9/R25 (Issue I, ADR-I1/ADR-I2)**: "no
importar símbolos con prefijo `_` de un módulo cerrado". Las declaraciones de congelamiento
(R61 de H, R56 de I, y R57 de `backtest/spec.md:392-393` de Issue G, mismo patrón) son
**per-change** ("en este Change [pasado]"): no vinculan a Change 46, que es un Change nuevo y
posterior — no hace falta derogarlas para que Change 46 modifique `data/`, `backtest/`,
`wfa.py`, `montecarlo.py`; simplemente no aplican fuera del Change que las declaró. Este
documento lo deja explícito para que `apply` no interprete erróneamente que hace falta un
"levantamiento" formal de esas tres declaraciones de alcance histórico.

### 7.2. Qué se deroga/modifica realmente, y dónde

- **R66** (DEBE). Para el alcance específico de este Change (`_clip`, y opcionalmente
  `_default_block_size` parametrizado, `_first_fill_record` parametrizado,
  `_contiguous_partition_bounds`/`_contiguous_blocks` parametrizado — Bloque 7, §6.7), la
  convención de ADR-I1/ADR-I2 ("nunca importar símbolos privados de un módulo cerrado, siempre
  reimplementar") se **relaja**, reemplazándose por: "estos helpers migran a un módulo interno
  compartido nuevo, importado por los módulos que hoy los duplican, siempre que la migración
  preserve R64 (igualdad exacta por call-site)". Esta relajación es **acotada a los símbolos
  listados en §6.7** — no es una reversión general de ADR-H5/ADR-I1/ADR-I2 (que siguen aplicando
  íntegramente a cualquier otro par de módulos no tocado por este Change).
- **R67** (NO DEBE). Esta relajación NO DEBE extenderse a `_extract_exit_returns` de
  `wfa.py`/`montecarlo.py` salvo que `design.md` lo decida explícitamente bajo R62 — por defecto,
  ADR-H5 permanece intacto para ese par específico.
- **R68** (DEBE). Si `design.md` decide tocar `wfa.py`/`montecarlo.py` para Bloque 3 (C9, R30-R37)
  y/o Bloque 6 (C7, R50-R56), ninguna de esas modificaciones DEBE reabrir por sí sola la
  discusión de R67 — tocar `wfa.py` por C9 no obliga a tocar también su `_extract_exit_returns`.
- **R69** (DEBE). El módulo/superficie pública nueva que reemplaza los símbolos consolidados
  (§6.7) DEBE quedar documentada en el propio código (docstring de módulo, mismo patrón que
  `_returns.py`/`_windowing.py`) citando explícitamente: qué copias reemplaza, por qué esta vez sí
  se consolida (razón: "el propio Change ya reabre estos archivos por otro motivo", no
  "conveniencia"), y qué llamador. sigue sin poder importarla (si alguno).
- **R70** (DEBE). Este documento (`spec.md` de Change 46) es, en sí mismo, el delta de spec
  exigido: no requiere una edición retroactiva de `validation/spec.md` de Issues H/I (esos
  documentos describen fielmente lo que esos Changes hicieron en su momento); el delta vive en
  este documento y, cuando `apply` cierre este Change, en el nuevo bloque `<!-- change:46-... -->`
  que se anexe a `validation/spec.md` (mismo patrón de anexado que usan H/I/J) documentando R66-R69
  como la resolución vigente para los símbolos de §6.7.
- **R71** (DEBE). El nuevo bloque anexado a `validation/spec.md` (R70) DEBE, como mínimo, declarar
  su propia versión de "R56-equivalente" (congelamiento de alcance de **este** Change) listando
  los archivos que Change 46 sí modificó — igual que H declaró la suya y I la suya — para que un
  Change futuro sepa qué encontrará ya tocado.

### 7.3. Decisión explícita pendiente para `design.md`

Este documento **no** obliga a levantar la protección de `_extract_exit_returns` (wfa.py/
montecarlo.py) — lo deja como decisión de `design.md`, condicionada a R62/R67/R68. La
consolidación de `_clip` (R57-R59) sí es exigida por este documento porque es un caso sin
ambigüedad (3 copias byte-idénticas, cero riesgo de comportamiento distinto).

---

## 8. Invariantes transversales adicionales

- **R72** (DEBE). Ningún bloque de este Change DEBE introducir un índice de adelanto ni una forma
  de inspeccionar datos posteriores al punto de lectura forward-only actual — extiende R32/R33 de
  `data/spec.md` y R36 de `validation/spec.md` (propiedad anti-lookahead del WFA) a todos los
  bloques nuevos.
- **R73** (DEBE). Ninguna excepción de dominio existente (`BacktestConfigError`,
  `SessionBoundaryError`, `CalendarError`, `DayBoundaryError`, `WfaConfigError`,
  `MonteCarloConfigError`, `PurgedCvConfigError`, `DsrPboConfigError`, `SensitivityConfigError`)
  DEBE capturarse ni envolverse silenciosamente por ningún bloque de este Change — mismo criterio
  R5/R34/R45 heredado de `validation/spec.md`.
- **R74** (NO DEBE). Ningún bloque de este Change NO DEBE alterar lo que alimenta
  `dataset_hash`/`firm_profile_hash`/`risk_profile_hash`/`CONFIG_VERSION`
  (`RunProvenance`, `simulator.py:270-276`, `ledger.py:18` = `"genesis-backtest/1"`) — son cambios
  de camino de cómputo interno sobre las mismas entradas, no cambios de esquema de datos ni de
  configuración. Excepción a vigilar: el adelanto de fail-fast de C6 (Bloque 5) es un cambio de
  comportamiento observable aunque no de esquema — ver pregunta abierta §10.4.
- **R75** (DEBE). `uv run mise run test` (639 tests existentes + los nuevos de cada bloque) DEBE
  pasar en verde tras cada bloque individual (no solo al final del Change completo) — cada bloque
  es mergeable por separado (§1.2).
- **R76** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre el estado
  final del Change.
- **R77** (DEBE). La propiedad central de la suite (`hypothesis`: ningún output de `on_bar(t)`
  cambia si se mutan barras posteriores a `t`) DEBE seguir verificándose sin modificación de su
  enunciado tras cualquiera de los 8 bloques.
- **R78** (NO DEBE). Ningún bloque NO DEBE añadir una dependencia de runtime nueva a
  `pyproject.toml` — todos los fixes son de reorganización de cómputo existente sobre `numpy` +
  `pandas` + stdlib ya declarados.

---

## 9. Riesgos declarados y mitigación

| # | Riesgo | Bloque | Mitigación exigida |
|---|---|---|---|
| Rg-1 | El adelanto de fail-fast de C6: hoy `CalendarError` (eventos naive) se dispara en el primer punto que invoca `news_windows` con esos eventos — hoy, en la práctica, puede ser el primer cierre de posición (`_register_news_breaches`) si ningún intent con esos eventos se propuso antes; tras hoistear a la construcción del `Simulator`, se dispara **siempre** ahí, incluso para runs que nunca habrían cerrado una posición ni propuesto un intent | 5 (C6) | R46: auditar y actualizar todo test que construya un `Simulator` con eventos naive sin cerrar posiciones; R47: equivalencia bit-a-bit para cualquier ejecución que hoy no dispara la excepción |
| Rg-2 | Interacción C2+C9: arreglar C2 (evicción acotada) con un caché **por-instancia de `Simulator`** conservaría la relectura ×27 de C9 — un fix parcial que "se ve" resuelto (memoria acotada) pero no ataca el multiplicador real | 3 (C2+C9) | R30-R32: el caché DEBE ser un objeto compartido por **ventana**, no por `Simulator`, verificado por identidad de objeto a través de las 27 instancias |
| Rg-3 | Consolidar `_default_block_size`/`_first_fill_record`/partición contigua a ciegas (mismos bounds/firma/forma de retorno para todos los call-sites) cambiaría comportamiento observable en al menos un call-site (`diagnostics.py`'s bounds distintos, excepciones distintas de `_first_fill_record`, formas de retorno distintas de la partición) | 7 (Q6) | R58, R60, R61: la consolidación exige parametrización explícita por call-site + test de igualdad (R64), no de comportamiento paralelo |
| Rg-4 | Interpretar erróneamente que hace falta "levantar" formalmente R57 (backtest/G), R61 (validation/H), R56 (validation/I) para que Change 46 toque `data/`/`backtest/`/`wfa.py`/`montecarlo.py` | 2, 3, 6, 7 | §7.1: estas son declaraciones de alcance histórico per-change, no leyes permanentes; no requieren derogación, solo esta aclaración documentada |
| Rg-5 | El cambio de `_close_position` para invocar `_floating_pnl` (R55) podría, si se hace descuidadamente, introducir una diferencia de redondeo de punto flotante si el orden de las multiplicaciones cambia | 6 (C7) | R56: test de equivalencia bit-a-bit específico; si el reordenamiento de operandos cambiara el resultado en el último bit, R5 exige descartar el cambio, no aceptar la diferencia |
| Rg-6 | El bench del Bloque 0 podría no ejecutarse antes de aplicar los Bloques 2/3/4/6 en `apply`, dejando "mejora medida, no argumentada" sin evidencia real | 0, 2, 3, 4, 6 | R20: ninguno de esos 4 bloques se considera cerrado sin su reporte antes/después archivado |

---

## 10. Preguntas abiertas para `design.md`

1. Nombre/ubicación exacta del/de los módulo(s) interno(s) del Bloque 7 (¿un solo
   `_shared_math.py`, o ampliar `_returns.py`/`_windowing.py` existentes?) — no bloquea R57-R59,
   solo su forma concreta.
2. Mecanismo exacto de evicción del `TickCache` del Bloque 3 (¿por tamaño fijo de días vivos, o
   por `trading_day` ya superado según el guard forward-only?) — ambos consistentes con R33.
3. Mecanismo exacto de consolidación de C7 (Bloque 6): ¿`_ledger_metrics_snapshot` compartido, o
   memoización por `id(ledger)`? Ambos consistentes con R50-R51.
4. ¿El adelanto de fail-fast de C6 (Bloque 5, Rg-1) amerita una nota de versión aunque no cambie
   `CONFIG_VERSION` (`"genesis-backtest/1"`, sin cambio de esquema)? No se encontró convención
   explícita en el repo que lo exija para cambios de *timing* de excepciones (sí para cambios de
   *esquema*/cálculo, R74).
5. Placeholder exacto de `session_open_utc`/`session_close_utc` en `make_annotated_bar`/`_bar`
   (§5, R11): ¿parámetro opcional nuevo con default, o valor hardcodeado derivado de
   `timestamp_utc`? Detalle de `design.md`, no bloquea R7-R14.
6. Mecanismo exacto de R45 (Bloque 5): ¿`inspect()` gana un parámetro `news_windows` ya calculado
   (cambio de firma de capa 2), o el fix se acota a `_register_news_breaches` únicamente (fix
   parcial de C6, documentado como tal)? Decisión de diseño con impacto en qué tan "cerrado" queda
   `strategy/inspector.py` tras este Change.
7. ¿Se decide en `apply` levantar la protección de ADR-H5 para `_extract_exit_returns`
   (`wfa.py`/`montecarlo.py`, R62/R67)? Este documento deja la puerta abierta pero no lo exige.

---

## 11. Criterios de aceptación por bloque (evals ejecutables)

```
DADO   scripts/bench_simulator.py corrido con --repeat 27 sobre una ventana IS real del dataset
       FTMO ya exportado
CUANDO se compara el reporte baseline (pre-Bloques) contra el reporte tras aplicar Bloque 2
ENTONCES el desglose por etapa muestra `session_window` invocada 1 vez por trading_day distinto,
         no 1 vez por barra ni 2 veces por barra (R8, R10, R28)
```

```
DADO   un dataset sintético con >=2 trading_day distintos
CUANDO se instrumenta session_window (spy/contador) y se consume iter_bars(frame, symbol,
       profile) completo
ENTONCES el contador de invocaciones es exactamente igual al número de trading_day distintos, no
         al número de barras (R14)
```

```
DADO   un Ledger/WfaResult producido antes de aplicar cualquier bloque (baseline archivado)
CUANDO se aplica cada bloque (1-6) por separado sobre el mismo dataset/seed/config
ENTONCES el artefacto resultante es byte-idéntico al baseline salvo el campo git_commit (R1, R27,
         R29, R35, R41, R47, R52, R56)
```

```
DADO   LiquidityMap con un nivel mitigado por apply_close
CUANDO se invoca .get(level_id) sobre ese level_id purgado
ENTONCES lanza KeyError (documentado en la docstring, R23) y active_levels() nunca lo retorna
         (R21, R25)
```

```
DADO   27 instancias de Simulator construidas por _run_execution_combo dentro de la misma
       ventana WFA
CUANDO se inspecciona el objeto _day_ticks_cache/TickCache de cada una
ENTONCES las 27 instancias comparten la misma identidad de objeto de caché (no 27 objetos
         distintos) (R30, R32)
```

```
DADO   un Simulator construido con EconomicEvent(s) naive (sin tzinfo)
CUANDO se construye el Simulator (tras Bloque 5)
ENTONCES lanza CalendarError inmediatamente, sin esperar al primer cierre de posición (R44, Rg-1)
```

```
DADO   _clip definido en montecarlo.py, prop_sim.py y purged_cv.py antes de Bloque 7
CUANDO se aplica Bloque 7 (R57)
ENTONCES rg -n "^def _clip" src/genesis/validation/montecarlo.py src/genesis/validation/
         prop_sim.py src/genesis/validation/purged_cv.py retorna 0 coincidencias (las 3
         redefiniciones locales se eliminan) y las 3 importan desde el módulo compartido nuevo
```

```
DADO   strategy/candidate_a/diagnostics.py::_default_block_size con bounds (1, max(1, n))
CUANDO se aplica cualquier consolidación de Bloque 7 que toque _default_block_size
ENTONCES diagnostics.py sigue produciendo exactamente clip(round(n**(1/3)), 1, max(1, n)) para
         cualquier n de prueba (R58, R64) — nunca (5, 60)
```

---

## 12. Referencias

- Issue #46 (`ramaDben/genesis`) + adenda; `idea.md`, `proposal.md` de este Change.
- `src/genesis/data/store.py:27-114` (`AnnotatedBar`, `iter_bars`).
- `src/genesis/backtest/simulator.py:213-286,298-324,334-345,410-434,551-612` (constructor,
  `run`, `_process_bar`, `_floating_pnl`, `_enforce_session_close_and_guard`, `_close_position`,
  `_register_news_breaches`).
- `src/genesis/backtest/ticks.py:209-275` (`_tick_in_bar_window`, `_bisect_window_bounds`,
  `has_sufficient_tick_coverage`, `ticks_in_bar_window`).
- `src/genesis/backtest/metrics.py:21-83`.
- `src/genesis/strategy/candidate_a/smc/liquidity.py` (`LiquidityMap`, `LiquidityLevel`),
  `src/genesis/strategy/candidate_a/smc/engine.py:185-209` (único consumidor externo).
- `src/genesis/strategy/inspector.py:96-114` (`inspect`), `src/genesis/data/calendar.py:69-99`
  (`news_windows`).
- `src/genesis/validation/wfa.py:94-109,210-247` (`_extract_exit_returns`,
  `_run_execution_combo`), `montecarlo.py:72-113`, `purged_cv.py:1-117`, `dsr_pbo.py:90-114`,
  `prop_sim.py:210-227`, `_returns.py`, `_windowing.py`.
- `.pulse/specs/validation/spec.md:425-427,799-807,865-868,939-944,1091-1096,1115-1117` (R61-H,
  ADR-H5, ADR-I1, R9-I, R25-I/ADR-I2, R56-I, R61-I).
- `.pulse/specs/backtest/spec.md:392-393` (R57-G, mismo patrón de congelamiento per-change).
- `.pulse/specs/data/spec.md:300-314,342-349` (R28-R33, R40-R41, `AnnotatedBar`/`session_window`).
- `tests/strategy/candidate_a/smc/test_liquidity.py`, `tests/strategy/fakes.py:35-56`,
  `tests/strategy/test_clock.py:14-24`, `tests/validation/test_extract_returns.py`.
- `scripts/bench_diagnose.py`, `scripts/bench_iter_ticks.py` (patrón a replicar en
  `scripts/bench_simulator.py`).
- Memoria Serena `mem:perf-diagnose-detect-ct-events` (C1, 98,2%/68×), `mem:dataset-ftmo-respaldo`
  (dataset FTMO ya exportado, base del bench del Bloque 0).
