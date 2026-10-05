
<!-- change:6-g-feat-backtest-simulador-equity-intrad-a-fills-por-ticks-cierre -->
<!-- change:6-g-feat-backtest-simulador-equity-intrad-a-fills-por-ticks-cierre -->
# Specification: Simulador de backtest (equity intradía, fills por ticks, cierre por sesión, breaches) + costos + ledger + métricas (Issue #6 / G)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §1.1, §1.3,
§2.3, §3, §5.2, §8, §9, §11. Este documento formaliza `idea.md` y `proposal.md` de este Change en
requisitos verificables. Los gates G/C/P/T del spec **nunca se relajan**; ningún requisito de este
documento puede contradecirlos.

Convención de rutas: el spec usa pseudocódigo `python/backtest/...` (§5.2); el repo real usa
`src/genesis/backtest/...` (`[project] name = "genesis"` en `pyproject.toml`). Todas las rutas de
este documento son las reales del repo.

Este Change resuelve las 9 decisiones ya tomadas en `proposal.md` (composición de `SimulationClock`,
`RiskProfile` propio, `SessionBoundaryError` como guard defensivo, `iter_ticks` propio, breaches
continuables vs. `SessionBoundaryError` fail-fast, fills SL-primero + gap de apertura, puerto
`RiskLevelsProvider`, sin dependencias runtime nuevas, `GenesisBacktestError` raíz independiente) y
formaliza con criterios ejecutables los 6 trade-offs que `proposal.md` dejó explícitamente
pendientes para esta fase (§3 de este documento).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir la capa 3 agnóstica a la estrategia (`src/genesis/backtest/`): el simulador
event-driven M1 (`simulator.py`), el modelo de costos (`costs.py`), el ledger de decisiones
(`ledger.py`) y el motor de métricas (`metrics.py`), más los módulos de soporte que `idea.md`/
`proposal.md` identificaron como necesarios (`errors.py`, `clock.py`, `risk_profile.py`,
`ticks.py`). Esto consume el contrato ya cerrado de Issue C (`genesis.strategy.{contract, clock,
inspector, errors}`) y la capa de datos cerrada de Issue B (`genesis.data.{store, sessions,
profile, symbols, metadata, calendar, mt5_export}`) sin modificar ninguno de los dos árboles, y
desbloquea Issue H (WFA + Monte Carlo), que depende de este Change (spec §11, tabla de issues:
"G — depende solo de C").

### 1.2. Alcance IN

- `src/genesis/backtest/errors.py`: `GenesisBacktestError` (raíz propia), `SessionBoundaryError`,
  `BacktestConfigError`.
- `src/genesis/backtest/clock.py`: `SimulationClock` (compone un `BarClock` de C, añade estado
  propio de ejecución: `trading_day` vigente, `previous_day_close_balance`).
- `src/genesis/backtest/risk_profile.py`: `RiskProfile`, `MaxLossLimitKind`, `load_risk_profile`,
  `risk_profile_hash`, recurso empaquetado `risk_profile.json`.
- `src/genesis/backtest/ticks.py`: `iter_ticks` (lector forward-only propio, consume
  `genesis.data.mt5_export.RawParquetStore.read_chunk` ya público).
- `src/genesis/backtest/simulator.py`: loop event-driven, `RiskLevelsProvider` (Protocol
  adicional), cálculo de fills (ticks reales + fallback conservador + regla de gap de apertura),
  detección en línea de breaches, cierre forzado por sesión del Candidato B.
- `src/genesis/backtest/costs.py`: `spread_for`, `commission_for`, `slippage_for`, `swap_for`,
  parámetro `stress` de primera clase, `load_costs_config`, recurso empaquetado
  `costs_config.json`.
- `src/genesis/backtest/ledger.py`: `CONFIG_VERSION`, `BreachKind`, `BreachEvent`, `LedgerEntry`,
  `reconstruct_equity_series`.
- `src/genesis/backtest/metrics.py`: métricas clásicas (PF, Sharpe, drawdown, win rate) + métricas
  prop (peor excursión diaria flotante, distancia mínima al límite diario, exposición concurrente
  máxima, tasa de rechazo por motivo).
- `src/genesis/backtest/__init__.py`: `__all__` mínimo y curado (patrón
  `src/genesis/strategy/__init__.py`).
- `tests/backtest/`: `conftest.py`, `fakes.py`, tests planos, replicando el patrón de
  `tests/strategy/`.
- Test de propiedad forward-only a nivel de simulación completa (spec §9) y test de propiedad de
  equity intradía reconstruida del ledger idéntica a la del simulador (spec §9).

### 1.3. Alcance OUT (YAGNI explícito)

- Todo `src/genesis/validation/` (WFA, Monte Carlo, purged K-fold, DSR/PBO, `prop_sim`, veredicto
  de torneo) — Issues H/I/J. `metrics.py` de este Change produce los insumos; no calcula gates
  G/C/P/T.
- Lógica de negocio de cualquier candidato concreto (`candidate_a/`, `candidate_b/`,
  `candidate_c/`) — Issues D/E/F/K. Este Change solo consume `StrategyCandidate`/`EntryIntent` ya
  cerrados por C y ejercita el simulador con `FakeStrategyCandidate` en sus propios tests.
- Modificación de cualquier archivo bajo `src/genesis/data/` o `src/genesis/strategy/` (R57):
  `max_loss_limit_pct`, `weekend_holding` y el balance del día anterior se resuelven con una
  ficha propia (`RiskProfile`) y estado de ejecución dentro de `genesis.backtest`, nunca
  extendiendo `FirmProfile`.
- Dependencias de runtime nuevas (`scipy`, `statsmodels`, `matplotlib`, `quantstats`): quedan
  explícitamente diferidas a Issue H en adelante (Decisión 8 del proposal; spec §3: "núcleo
  propio... periferia con `scipy`/`statsmodels`/`quantstats`/`matplotlib`" asignada a la capa 4).
- Ventana deslizante de barras en `SimulationClock` (`window(n)`, `peek_confirmed(t)`): ninguna
  hipótesis de este Change la requiere (el cierre forzado usa `sessions.session_window`, no
  historia de `BarClock`). Si el trailing estructural del Candidato A (Issue F, futuro) la
  necesita, es responsabilidad de F extenderla de forma aditiva (ADR-C3 ya lo autoriza a
  cualquier consumidor, no en exclusiva a G) — ver R8 y Riesgo Rg-4.
- CLI de `mise run` / comando `backtest` (spec §6, tabla de CLI): este Change entrega las
  funciones puras/orquestador programático; la superficie de CLI unificada (`export`, `quality`,
  `diagnose`, `backtest`, `wfa`, `mc`, `prop-sim`, `full-validation`, `verdict`) es una decisión
  de integración que el spec no ata a un issue único — se difiere hasta que exista al menos un
  candidato real que ejecutar (Issue E), evitando construir una interfaz de línea de comandos
  sin caso de uso verificable en este Change.
- `fixtures/mql5_reference.csv` / paridad MQL5↔Python: no aplica a esta capa (era deuda de C,
  `common/vwap_engine.py`).

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **DEBERÍA** (SHOULD), numerados `R1..Rn`, cada uno
  verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones son **normativos** (deben existir exactamente con ese
  nombre, verificable por `rg`); firmas exactas (tipos de parámetros, orden) se resuelven en
  `design.md` respetando el comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- `AnnotatedBar.timestamp_utc` (`src/genesis/data/store.py:31`) es el `confirmed_time` normativo
  ya fijado por C; este Change lo reutiliza sin adaptador. `SimulationClock` (§4.2) compone, no
  hereda, el `BarClock` de C (`src/genesis/strategy/clock.py:14`).

---

## 3. Resolución de los trade-offs pendientes de `proposal.md`

`proposal.md` (§"Riesgos que specify debe acotar") dejó 6 decisiones sin cerrar. Esta sección fija
la resolución normativa de cada una; los requisitos que la formalizan viven en la §4.

| # | Trade-off pendiente | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | Comportamiento si el candidato no implementa `RiskLevelsProvider` | Requisito duro documentado: el simulador verifica `isinstance(candidate, RiskLevelsProvider)` al construir la simulación (antes de procesar la primera barra) y lanza `BacktestConfigError` si no lo implementa — no es un `RejectionReason` nuevo ni un rechazo silencioso por `EntryIntent`. | R21 |
| 2 | Semántica de "cuenta agotada" tras breach total | Estado terminal: tras un breach `TOTAL`, el simulador deja de invocar `candidate.on_bar` para el resto de ese run (candidato+símbolo); el proceso Python no aborta (otros runs del mismo batch continúan). Se registra un evento terminal en el ledger. | R30, R31 |
| 3 | Criterios exactos de la regla de gap de apertura | Tres ramas BDD explícitas: gap desfavorable → fill a `bar.open`; gap favorable → fill al nivel de TP (cap conservador); sin gap → SL primero. La regla de gap **solo** aplica al fallback sin ticks (o con cobertura insuficiente, trade-off 6); con ticks reales se recorre la secuencia de ticks en orden y gana el primer nivel tocado. | R32, R33, R34, R35 |
| 4 | Ventana deslizante de `SimulationClock` para el trailing del Candidato A | No se implementa en este Change (ninguna hipótesis actual la requiere); queda documentado como extensión aditiva diferida a quien la necesite primero (Issue F), autorizada por ADR-C3 sin reabrir este Change. | R8 |
| 5 | Necesidad de `BacktestConfigError` | Confirmada como necesaria: cubre (a) config inválida de `load_risk_profile`/`load_costs_config`, (b) candidato sin `RiskLevelsProvider` (trade-off 1), y (c) símbolo fuera de la tabla `SESSIONS` al resolver el cierre forzado (envuelve el `KeyError` de `sessions.session_window` con contexto de dominio). | R3, R12, R21, R39 |
| 6 | Umbral de cobertura de ticks para preferir fills reales | Criterio de dos niveles: (a) día — `RawParquetStore.has_chunk(symbol, TICK, day_window)` debe ser `True` para `bar.trading_day`; (b) vela — debe existir al menos un tick con `timestamp` dentro del minuto de la vela. Ambas condiciones deben cumplirse para esa vela puntual; si (a) es `True` pero (b) es `False` para una vela concreta, esa vela usa el fallback sin invalidar el uso de ticks reales en el resto del día. | R18, R19 |

---

## 4. Requisitos por módulo

### 4.1. `errors.py` — jerarquía de excepciones propia (Decisión 9, ADR-C4)

**Requisitos**:

- **R1** (DEBE). `errors.py` DEBE definir `GenesisBacktestError(Exception)` como raíz propia de la
  jerarquía de excepciones de `genesis.backtest`. NO DEBE heredar de
  `genesis.strategy.errors.GenesisStrategyError` ni de `genesis.data.errors.GenesisDataError`
  (Decisión 9: sin raíz `GenesisError` compartida entre capas, siguiendo ADR-C4).
- **R2** (DEBE). `errors.py` DEBE definir `SessionBoundaryError(GenesisBacktestError)`, lanzada
  cuando una posición del Candidato B permanece abierta al procesar la primera `AnnotatedBar`
  fuera de `sessions.session_window(symbol, trading_day)` pese al cierre proactivo (R23/R24) —
  guard defensivo fail-fast (Decisión 3), nunca resultado esperado de un run con datos limpios
  (spec §2.3, §8: "el cierre forzado es invariante, no best-effort").
- **R3** (DEBE). `errors.py` DEBE definir `BacktestConfigError(GenesisBacktestError)` para: (a)
  config inválida/incompleta de `load_risk_profile`/`load_costs_config`; (b) un candidato que no
  implementa `RiskLevelsProvider` al iniciarse la simulación (R21); (c) un símbolo fuera de la
  tabla `SESSIONS` de `genesis.data.sessions` al resolver el cierre forzado del Candidato B
  (envuelve el `KeyError` de `session_window` con contexto de dominio, en vez de dejarlo
  propagar sin tipar).
- **R4** (DEBE). Todo mensaje de excepción nueva de este Change DEBE incluir contexto explícito
  (símbolo, timestamp, `candidate_id`, valor involucrado) — fail-fast con contexto (spec §8).

### 4.2. `clock.py` — `SimulationClock` (Decisión 1)

**Requisitos**:

- **R5** (DEBE). `clock.py` DEBE definir `SimulationClock` que **compone** (no hereda) un
  `BarClock` de `genesis.strategy.clock` como atributo interno, delegando `current_time`
  (property), `advance(bar)` y `require(timestamp)` a él. `rg -n "class SimulationClock"
  src/genesis/backtest/clock.py` DEBE retornar ≥1 coincidencia y `rg -n
  "class SimulationClock\(BarClock\)" src/genesis/backtest/clock.py` DEBE retornar 0.
- **R6** (DEBE). `SimulationClock.advance(bar)` DEBE, tras delegar a `BarClock.advance`, actualizar
  el `trading_day` vigente comparando con `bar.trading_day` de la `AnnotatedBar` recibida.
- **R7** (DEBE). `SimulationClock` DEBE exponer `previous_day_close_balance: float | None` como
  estado propio no delegado, actualizado por el consumidor del loop (`simulator.py`) al cruzar un
  `daily_reset_time` — NUNCA leído de `FirmProfile` (Decisión 2: el balance del día anterior es
  estado de ejecución, no config estática).
- **R8** (NO DEBE). `SimulationClock` NO DEBE exponer una ventana deslizante de barras (`window(n)`,
  `peek_confirmed(t)`) en este Change (trade-off 4, §3): `rg -n "def window|def peek_confirmed"
  src/genesis/backtest/clock.py` DEBE retornar 0 coincidencias.
- **R9** (DEBE). `tests/backtest/` DEBE incluir al menos un test que verifique que
  `SimulationClock.advance`/`require` preservan exactamente la semántica de `LookaheadError` del
  `BarClock` interno (delegación transparente, no reimplementación del guard).

### 4.3. `risk_profile.py` — ficha propia de riesgo (Decisión 2)

**Requisitos**:

- **R10** (DEBE). `risk_profile.py` DEBE definir `MaxLossLimitKind` como `StrEnum` con miembros
  `STATIC` y `TRAILING` (spec §1.1: "DD máximo... tipo: estático o trailing; ancla del trailing").
- **R11** (DEBE). `risk_profile.py` DEBE definir `RiskProfile` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `max_loss_limit_pct: float`, `max_loss_limit_kind:
  MaxLossLimitKind`, y `weekend_holding_allowed: bool` (spec §1.1, campo `weekend_holding` de
  `prop_profile.json`, no expuesto por `FirmProfile`) — sin duplicar ningún campo que
  `FirmProfile` ya expone (`daily_loss_limit_pct`, `daily_reset_time`, etc. se siguen leyendo de
  `FirmProfile`).
- **R12** (DEBE). `risk_profile.py` DEBE definir `load_risk_profile(path: Path | None = None) ->
  RiskProfile` que cargue desde `path` o desde el recurso empaquetado
  `genesis.backtest/risk_profile.json` (patrón `load_firm_profile`), con defaults del spec §1.3
  (`max_loss_limit_pct=10.0`, `max_loss_limit_kind=STATIC`, `weekend_holding_allowed=True` —
  "permitido en índices" para The5ers); DEBE lanzar `BacktestConfigError` con contexto ante
  config inválida/incompleta.
- **R13** (DEBE). `risk_profile.py` DEBE definir `risk_profile_hash(profile: RiskProfile) -> str`,
  hash `sha256` determinista sobre JSON canónico ordenado (patrón `firm_profile_hash`), para
  incorporarse a cada `LedgerEntry` (R45).
- **R14** (NO DEBE). El balance al cierre del día anterior (`previous_day_close_balance`, R7) NO
  DEBE persistirse como campo de `RiskProfile` ni de ningún recurso empaquetado — es estado
  mutable de ejecución, nunca config estática (Decisión 2).

### 4.4. `ticks.py` — lector de ticks forward-only propio (Decisión 4)

**Requisitos**:

- **R15** (DEBE). `ticks.py` DEBE definir `iter_ticks` (nombre exacto normativo) que consuma
  `genesis.data.mt5_export.RawParquetStore.read_chunk(symbol, Granularity.TICK, window)` sin
  añadir ningún método nuevo a `genesis.data.mt5_export` ni a `genesis.data.store`. `rg -n
  "RawParquetStore" src/genesis/backtest/ticks.py` DEBE retornar ≥1 coincidencia; `git diff
  --stat -- src/genesis/data` DEBE estar vacío.
- **R16** (DEBE). `iter_ticks` DEBE retornar una secuencia/generador vacío (nunca lanzar) cuando
  `RawParquetStore.has_chunk(...)` es `False` para `(symbol, trading_day)` — la ausencia de ticks
  es el caso normal (PA-2 de Issue B), no una excepción.
- **R17** (DEBE). `iter_ticks` DEBE lanzar `BacktestConfigError` si el chunk existe pero su esquema
  es inválido (columnas `bid`/`ask`/`last` ausentes o de tipo incorrecto) — fail-fast solo ante
  datos presentes-pero-inválidos, nunca ante datos ausentes.
- **R18** (DEBE). El simulador DEBE considerar "cobertura suficiente de ticks" para el fill de una
  `AnnotatedBar` si y solo si: (a) `RawParquetStore.has_chunk(symbol, TICK, day_window)` es
  `True` para `bar.trading_day`, y (b) existe al menos un tick con `timestamp` dentro del minuto
  de la vela (`[bar.timestamp_utc` menos un minuto`, bar.timestamp_utc]`). Si (a) es `True` pero
  (b) es `False` para una vela puntual, esa vela usa el fallback conservador (R32-R35) sin
  invalidar el uso de ticks reales en otras velas del mismo día (trade-off 6, §3).
- **R19** (DEBE). `tests/backtest/` DEBE incluir un test que ejercite R18 con un chunk de ticks
  sintético que cubre solo parte del día (huecos intra-día): al menos una vela con ticks
  disponibles (fill por tick) y al menos una vela sin ticks dentro del mismo `trading_day` (fill
  por fallback).

### 4.5. `simulator.py` — loop event-driven, fills, breaches, cierre forzado

**Requisitos**:

- **R20** (DEBE). `simulator.py` DEBE definir `RiskLevelsProvider` como `Protocol
  @runtime_checkable` con un único método `risk_levels(self, intent: EntryIntent) -> tuple[float,
  float]` (`stop_loss`, `take_profit`) (Decisión 7), sin modificar
  `src/genesis/strategy/contract.py` (`git diff --stat -- src/genesis/strategy` vacío).
- **R21** (DEBE). El simulador DEBE verificar `isinstance(candidate, RiskLevelsProvider)` al
  construir la simulación para un candidato dado, antes de procesar la primera `AnnotatedBar`; si
  no lo implementa, DEBE lanzar `BacktestConfigError` de inmediato (trade-off 1, §3):
  `RiskLevelsProvider` es un requisito duro documentado para cualquier candidato usado con este
  simulador, no un fallback silencioso ni un `RejectionReason` nuevo.
- **R22** (DEBE). El loop principal (`Simulator` o `run_backtest`, nombre exacto a fijar en
  `design.md`) DEBE, por cada `AnnotatedBar` emitida por `store.iter_bars`: (a)
  `SimulationClock.advance(bar)`; (b) `candidate.on_bar(bar)`; (c) por cada `EntryIntent`,
  construir el contexto pre-trade completo (`symbol`, `intent_time`, `proposed_rr` vía
  `RiskLevelsProvider.risk_levels`, `figure`, `firm_profile`, `news_events`, `config`) e invocar
  `inspector.inspect(...)`; (d) si autorizado, calcular el fill (R18, R32-R35) y actualizar
  equity/posiciones; (e) evaluar breaches en línea (R25-R31); (f) aplicar cierre forzado de
  sesión del Candidato B (R23-R24).
- **R23** (DEBE). El cierre forzado del Candidato B DEBE ejecutarse de forma **proactiva** en la
  última oportunidad de fill dentro de `session_window(symbol, trading_day)` (Decisión 3), usando
  exclusivamente `genesis.data.sessions.session_window` como fuente de horarios (sin tabla
  duplicada).
- **R24** (DEBE). El simulador DEBE lanzar `SessionBoundaryError` si, tras el intento de cierre
  proactivo (R23), una posición del Candidato B permanece abierta al procesar la primera
  `AnnotatedBar` con `timestamp_utc` posterior al `close_utc` de `session_window` de ese
  `trading_day` — guard defensivo, no camino esperado con datos limpios (R2).
- **R25** (DEBE). El simulador DEBE evaluar en línea, por cada `AnnotatedBar` procesada con
  posiciones abiertas, el breach **diario** (base doble §1.3: el mayor entre la pérdida contra el
  equity flotante intradía y la pérdida contra `SimulationClock.previous_day_close_balance`)
  contra `FirmProfile.daily_loss_limit_pct`.
- **R26** (DEBE). El simulador DEBE evaluar en línea el breach **total** contra
  `RiskProfile.max_loss_limit_pct` (R11).
- **R27** (DEBE). El simulador DEBE registrar un breach de **noticias** (`BreachKind.NEWS`, R43)
  cuando el intervalo `[entry_time, exit_time]` de una posición abierta se solapa con alguna
  ventana de `news_windows(news_events, symbol, firm_profile)` — evento informativo agregado por
  `metrics.py` (R49), distinto del rechazo pre-trade `RejectionReason.NEWS_WINDOW` de C (que
  bloquea la entrada, no la tenencia). La condición exacta de solape se fija en `design.md`; ver
  Riesgo Rg-3.
- **R28** (DEBE). El simulador DEBE registrar un breach de **fin de semana**
  (`BreachKind.WEEKEND`, R43) cuando una posición permanece abierta al cruzar el cierre de sesión
  del último día hábil de la semana para ese símbolo (`session_window` del viernes) mientras
  `RiskProfile.weekend_holding_allowed` es `False`.
- **R29** (DEBE). El simulador DEBE **continuar** su ejecución (seguir invocando
  `candidate.on_bar` el resto del `trading_day`/símbolo) tras un breach diario (R25), de noticias
  (R27) o de fin de semana (R28) — estos tres tipos NUNCA abortan el run (Decisión 5; spec §5.2
  usa "detecta", no "aborta").
- **R30** (DEBE). Tras un breach **total** (R26), el simulador DEBE marcar la cuenta simulada de
  ese `(candidate_id, symbol)` como agotada y DEBE dejar de invocar `candidate.on_bar` para el
  resto de ese run (trade-off 2, §3) — estado terminal, distinto del breach diario (que permite
  continuar al día siguiente). El proceso Python NO DEBE abortar con una excepción: el run de
  otros símbolos/candidatos en el mismo proceso batch continúa sin interrupción.
- **R31** (DEBE). El simulador DEBE registrar en el ledger un evento terminal (`BreachEvent` con
  `kind=BreachKind.TOTAL` y un indicador de cuenta agotada, forma exacta a fijar en `design.md`)
  en el momento del breach total, de modo que `metrics.py` pueda identificar el punto de corte de
  la serie de equity de ese run.
- **R32** (DEBE). El motor de fills intrabar DEBE aplicar, para el fallback sin ticks o con
  cobertura insuficiente (R18), la regla **SL-primero** cuando tanto SL como TP caen dentro de
  `[bar.low, bar.high]` sin gap de apertura.
- **R33** (DEBE). Ante gap de apertura **desfavorable** (`bar.open` ya más allá del SL en la
  dirección adversa a la posición), el fill DEBE ejecutarse a `bar.open`, no al nivel teórico de
  SL (trade-off 3, rama 1, §3).
- **R34** (DEBE). Ante gap de apertura **favorable** (`bar.open` ya más allá del TP en la
  dirección favorable a la posición), el fill DEBE ejecutarse al nivel de TP, no a `bar.open`
  (cap conservador, trade-off 3, rama 2, §3).
- **R35** (DEBE). La regla de gap de apertura (R33/R34) DEBE aplicarse únicamente al fallback sin
  ticks o con cobertura insuficiente (R18); cuando hay cobertura suficiente de ticks, el fill DEBE
  resolverse recorriendo la secuencia de ticks reales en orden temporal, aplicando el primer nivel
  (SL o TP) que el precio de algún tick toque (trade-off 3, rama 3, §3).
- **R36** (DEBERÍA). `tests/backtest/` DEBERÍA incluir una tabla golden con al menos 5 casos de
  fill intrabar: SL primero sin gap, TP primero sin gap, gap desfavorable (fill a `bar.open`), gap
  favorable (fill a TP), y fill por tick real dentro de la ventana de cobertura (R18).

### 4.6. `costs.py` — modelo de costos con stress de primera clase

**Requisitos**:

- **R37** (DEBE). `costs.py` DEBE definir funciones puras `spread_for(symbol, timestamp,
  ticks_window | None) -> float`, `commission_for(...)`, `slippage_for(...)`, `swap_for(symbol,
  days_held, figure, is_long)` (triple rollover usando `SymbolFigure.swap_rollover_day`/
  `swap_long`/`swap_short`).
- **R38** (DEBE). Toda función de costos de R37 DEBE aceptar un parámetro `stress: float = 1.0` de
  primera clase que multiplica el costo total antes de aplicarlo (gate G9 del spec: `×1.5`;
  `sensitivity.py` futuro de Issue I: `×2`).
- **R39** (DEBE). `costs.py` DEBE definir `load_costs_config(path: Path | None = None)` que cargue
  defaults desde el recurso empaquetado `genesis.backtest/costs_config.json` (patrón
  `load_firm_profile`/`load_inspector_funnel_config`), lanzando `BacktestConfigError` con contexto
  ante config inválida/incompleta.
- **R40** (DEBE). El simulador DEBE fallar explícitamente (`BacktestConfigError`) si se le pide
  correr sin un modelo de costos válido — "sin costos no hay reporte" (spec §5.2, cita textual).
- **R41** (NO DEBE). `costs.py` y `metrics.py` NO DEBEN importar `scipy`, `statsmodels`,
  `matplotlib` ni `quantstats` (Decisión 8): solo `numpy` + stdlib. `rg -n
  "^import scipy|^import statsmodels|^import matplotlib|^import quantstats"
  src/genesis/backtest/` DEBE retornar 0 coincidencias.

### 4.7. `ledger.py` — registro append-only y reconstrucción de equity

**Requisitos**:

- **R42** (DEBE). `ledger.py` DEBE definir `CONFIG_VERSION: str = "genesis-backtest/1"` a nivel de
  módulo (patrón `CONFIG_VERSION` de `genesis.data.metadata`/`genesis.strategy.contract`).
- **R43** (DEBE). `ledger.py` DEBE definir `BreachKind` como `StrEnum` con exactamente los
  miembros `DAILY`, `TOTAL`, `NEWS`, `WEEKEND`.
- **R44** (DEBE). `ledger.py` DEBE definir `BreachEvent` (`@dataclass(frozen=True, slots=True)`)
  con, como mínimo, `kind: BreachKind`, `trading_day`, `timestamp_utc`, y la magnitud vs. umbral
  que disparó el breach.
- **R45** (DEBE). `ledger.py` DEBE definir `LedgerEntry` (o estructura equivalente) que registre
  **todas** las decisiones del embudo (autorizadas y rechazadas, con `RejectionReason` de C si
  vino del Inspector, o `BreachKind`/`SessionBoundaryError` si vino de G), cada una con
  `candidate_id`, `config_version` (R42), `dataset_hash` (`sha256_of` reutilizado de
  `genesis.data.metadata`), `firm_profile_hash` (reutilizado), y `risk_profile_hash` (R13) — spec
  §5.2: "todas las decisiones... + `config_version` + hash del dataset + ficha de firma".
- **R46** (DEBE). `ledger.py` DEBE definir una función pura `reconstruct_equity_series(entries) ->
  ...` que reconstruya la serie de equity intradía por día exclusivamente a partir del ledger
  persistido, sin depender de ningún estado en memoria del `Simulator` en ejecución (spec §9,
  propiedad central de equity).
- **R47** (DEBE). `tests/backtest/` DEBE incluir un test de propiedad (`hypothesis`,
  `max_examples>=1000`, marcado `pytest.mark.unit`) que verifique: para una secuencia arbitraria
  de decisiones de simulación, `reconstruct_equity_series(ledger)` produce una serie idéntica a la
  serie de equity mantenida en vivo por el `Simulator` durante la misma ejecución (spec §9: "la
  serie de equity intradía reconstruida del ledger es idéntica a la del simulador").

### 4.8. `metrics.py` — métricas clásicas y prop

**Requisitos**:

- **R48** (DEBE). `metrics.py` DEBE definir funciones puras sobre un ledger ya poblado (no
  acopladas al loop del simulador) para las métricas clásicas: profit factor, Sharpe puntual,
  drawdown máximo, win rate.
- **R49** (DEBE). `metrics.py` DEBE definir funciones puras para las métricas prop: peor excursión
  diaria flotante, distancia mínima al límite diario, exposición concurrente máxima, y tasa de
  rechazo por motivo (agregando `RejectionReason` de C + `BreachKind` de G, incluyendo los eventos
  `NEWS`/`WEEKEND` de R27/R28).
- **R50** (NO DEBE). Ninguna función de `metrics.py` DEBE mutar el ledger recibido como argumento
  (funciones puras sobre datos ya persistidos, spec §5.2).

### 4.9. Testing (`tests/backtest/`)

**Requisitos**:

- **R51** (DEBE). `tests/backtest/conftest.py` y `tests/backtest/fakes.py` DEBEN existir,
  replicando el patrón de `tests/strategy/{conftest.py, fakes.py}` (reutilizando
  `FakeStrategyCandidate` y `make_annotated_bar` donde aplique, sin duplicar su construcción).
- **R52** (DEBE). `tests/backtest/` DEBE incluir al menos un test de propiedad `hypothesis`
  (`max_examples>=1000`, marcado `pytest.mark.unit`) que extienda el invariante forward-only del
  spec §9 al nivel de simulación completa: el ledger/equity resultante de simular una secuencia de
  `AnnotatedBar` hasta el instante `t` NO DEBE cambiar si se mutan (agregan/alteran) barras con
  `timestamp_utc > t` en la secuencia de entrada.
- **R53** (DEBE). `tests/backtest/` DEBE incluir un golden test de sesión sintética con
  ruptura/falsa ruptura del rango y cierre forzado del Candidato B (mini-dataset construido a
  mano, spec §9).
- **R54** (DEBE). `tests/backtest/` DEBE incluir un golden test de breach diario calculado a mano
  (base doble §1.3: equity flotante vs. balance del día anterior) y un golden test de breach total
  calculado a mano (`RiskProfile.max_loss_limit_pct`), cada uno con el resultado esperado
  (`BreachEvent` con `kind` y magnitud) fijado por cálculo manual, no por el propio código bajo
  prueba (spec §9: "escenarios de challenge calculados a mano").
- **R55** (DEBE). `tests/backtest/` DEBE incluir un test de integración (marcado
  `pytest.mark.integration`) que ejecute el pipeline completo sobre un dataset de muestra
  (`iter_bars` → `Simulator` → `ledger.py` → `metrics.py`) en segundos, verificando que produce un
  ledger no vacío y métricas finitas (spec §9: "en CI, por candidato").
- **R56** (DEBE). `uv run pytest tests/backtest/ -v` DEBE pasar en verde (exit code 0).

---

## 5. Invariantes transversales

- **R57** (DEBE). Ningún archivo de `src/genesis/data/` ni de `src/genesis/strategy/` DEBE
  modificarse en este Change (`git diff --stat -- src/genesis/data src/genesis/strategy` vacío).
- **R58** (NO DEBE). Este Change NO DEBE añadir ninguna dependencia de runtime nueva a
  `pyproject.toml` (`[project.dependencies]`); `costs.py` y `metrics.py` se implementan
  exclusivamente con `numpy` + stdlib (Decisión 8, R41).
- **R59** (DEBE). Toda excepción de dominio nueva de este Change DEBE heredar de
  `GenesisBacktestError` y llevar mensaje con contexto explícito (R4).
- **R60** (DEBE). `src/genesis/backtest/__init__.py` DEBE exportar un `__all__` mínimo y curado
  (patrón `src/genesis/strategy/__init__.py`), incluyendo como mínimo `GenesisBacktestError`,
  `SessionBoundaryError`, `BacktestConfigError`, `CONFIG_VERSION`.
- **R61** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/backtest/` y `tests/backtest/` nuevos.

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `GenesisBacktestError` | `genesis.backtest.errors` | Raíz de la jerarquía de la capa 3 | — |
| `SessionBoundaryError` | `genesis.backtest.errors` | Posición del Candidato B viva tras el cierre proactivo de sesión (R23/R24) | Aborta el run (guard defensivo, spec §2.3, §8) |
| `BacktestConfigError` | `genesis.backtest.errors` | Config de `RiskProfile`/costos inválida; candidato sin `RiskLevelsProvider` (R21); símbolo fuera de `SESSIONS` | Aborta el run antes de procesar la primera barra (fail-fast) |
| `BreachEvent(kind=DAILY)` | `genesis.backtest.ledger` | Base doble del breach diario (R25) | Evento de ledger; el run continúa (R29) |
| `BreachEvent(kind=NEWS)` | `genesis.backtest.ledger` | Posición abierta solapada con ventana de noticias (R27) | Evento de ledger; el run continúa (R29) |
| `BreachEvent(kind=WEEKEND)` | `genesis.backtest.ledger` | Posición abierta cruzando el fin de semana sin permiso (R28) | Evento de ledger; el run continúa (R29) |
| `BreachEvent(kind=TOTAL)` | `genesis.backtest.ledger` | Breach de `RiskProfile.max_loss_limit_pct` (R26) | Cuenta simulada agotada: deja de invocar `on_bar` para ese run (R30); el proceso Python no aborta |
| (heredado) `LookaheadError` | `genesis.strategy.errors` | `SimulationClock` delega a `BarClock` (R5, R9) | Sin cambios respecto a C |
| (heredado) `DayBoundaryError` | `genesis.data.errors` | `store.iter_bars` (capa 1, sin cambios) | Sin cambios respecto a B |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/backtest/errors.py
CUANDO rg -n "class GenesisBacktestError" src/genesis/backtest/errors.py
       y rg -n "class SessionBoundaryError" src/genesis/backtest/errors.py
       y rg -n "class BacktestConfigError" src/genesis/backtest/errors.py
ENTONCES las tres retornan >=1 coincidencia; SessionBoundaryError y BacktestConfigError heredan
         de GenesisBacktestError; GenesisBacktestError no hereda de GenesisStrategyError ni de
         GenesisDataError
```

```
DADO   el archivo src/genesis/backtest/clock.py
CUANDO rg -n "class SimulationClock" src/genesis/backtest/clock.py
       y rg -n "class SimulationClock\(BarClock\)" src/genesis/backtest/clock.py
ENTONCES la primera retorna >=1 coincidencia; la segunda retorna 0 coincidencias (composición,
         no herencia)
```

```
DADO   una SimulationClock recién construida y una AnnotatedBar con timestamp_utc anterior a la
       última barra procesada
CUANDO se invoca SimulationClock.advance(bar)
ENTONCES se lanza LookaheadError (delegación transparente al BarClock interno, R9)
```

```
DADO   el archivo src/genesis/backtest/risk_profile.py
CUANDO rg -n "class RiskProfile" src/genesis/backtest/risk_profile.py
       y rg -n "max_loss_limit_pct|max_loss_limit_kind|weekend_holding_allowed"
          src/genesis/backtest/risk_profile.py
ENTONCES la primera retorna >=1 coincidencia; la segunda retorna >=3 coincidencias (un campo por
         concepto normativo)
```

```
DADO   un archivo de configuración de RiskProfile incompleto (sin max_loss_limit_pct)
CUANDO se invoca load_risk_profile(path)
ENTONCES se lanza BacktestConfigError con el nombre del campo faltante en el mensaje
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "def iter_ticks" src/genesis/backtest/ticks.py
       y rg -n "RawParquetStore" src/genesis/backtest/ticks.py
ENTONCES ambas retornan >=1 coincidencia
```

```
DADO   un RawParquetStore sin chunk de ticks persistido para (symbol, trading_day)
CUANDO se invoca iter_ticks(store, symbol, trading_day)
ENTONCES retorna una secuencia vacía sin lanzar ninguna excepción (R16)
```

```
DADO   un candidato que NO implementa RiskLevelsProvider
CUANDO se construye la simulación para ese candidato (antes de procesar la primera AnnotatedBar)
ENTONCES se lanza BacktestConfigError (R21, trade-off 1)
```

```
DADO   una posición del Candidato B abierta y una AnnotatedBar con timestamp_utc posterior al
       close_utc de session_window(symbol, trading_day), tras haber intentado el cierre proactivo
CUANDO el simulador procesa esa AnnotatedBar
ENTONCES se lanza SessionBoundaryError (R24)
```

```
DADO   una posición con SL/TP definidos y una vela cuyo bar.open ya está más allá del SL en la
       dirección adversa (gap desfavorable), sin cobertura suficiente de ticks (R18)
CUANDO se calcula el fill de cierre de esa posición
ENTONCES el fill se ejecuta al precio bar.open, no al nivel teórico de SL (R33)
```

```
DADO   una posición con SL/TP definidos y una vela cuyo bar.open ya está más allá del TP en la
       dirección favorable (gap favorable), sin cobertura suficiente de ticks (R18)
CUANDO se calcula el fill de cierre de esa posición
ENTONCES el fill se ejecuta al nivel de TP, no a bar.open (R34)
```

```
DADO   una simulación en la que se dispara un breach diario (BreachKind.DAILY)
CUANDO el simulador continúa procesando barras del mismo trading_day
ENTONCES candidate.on_bar sigue siendo invocado (el run no aborta, R29)
```

```
DADO   una simulación en la que se dispara un breach total (BreachKind.TOTAL)
CUANDO el simulador procesa la siguiente AnnotatedBar de ese (candidate_id, symbol)
ENTONCES candidate.on_bar NO es invocado para el resto del run de ese símbolo/candidato (R30), y
         el proceso Python no lanza ninguna excepción
```

```
DADO   el archivo src/genesis/backtest/ledger.py
CUANDO rg -n "class BreachEvent" src/genesis/backtest/ledger.py
       y rg -n "class BreachKind" src/genesis/backtest/ledger.py
       y rg -n "DAILY|TOTAL|NEWS|WEEKEND" src/genesis/backtest/ledger.py
ENTONCES las dos primeras retornan >=1 coincidencia cada una; la tercera retorna >=4
         coincidencias (los 4 miembros de BreachKind, R43)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/backtest/ -v
ENTONCES pasa en verde, incluyendo:
         - >=1 test de propiedad hypothesis (max_examples>=1000) del invariante forward-only a
           nivel de simulación completa (R52)
         - >=1 test de propiedad de "equity reconstruida del ledger == equity del simulador"
           (R47)
         - >=1 golden test de sesión sintética con cierre forzado del Candidato B (R53)
         - >=1 golden test de breach diario y >=1 de breach total calculados a mano (R54)
         - >=1 test de integración marcado pytest.mark.integration (R55)
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy
ENTONCES no retorna ninguna línea (R57: Changes B y C permanecen intactos)
```

```
DADO   el archivo pyproject.toml tras completar este Change
CUANDO rg -n "scipy|statsmodels|matplotlib|quantstats" pyproject.toml
ENTONCES no muestra ninguna de esas dependencias añadida a [project.dependencies] respecto al
         estado previo al Change (R58) — verificable también con git diff -- pyproject.toml
         mostrando 0 líneas añadidas bajo [project.dependencies]
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0, R61)
```

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | La condición exacta de "solape" para `BreachKind.NEWS` (R27) no está tan cerrada como `RejectionReason.NEWS_WINDOW`: el spec (§1.3) describe el bracketing de noticias solo para **órdenes pendientes** (pre-trade), no para tenencia de posiciones ya abiertas. | `design.md` podría implementar un criterio de solape distinto al que otro lector esperaría, sin que el spec lo arbitre de forma literal. | R27 fija la semántica mínima verificable (solape de intervalo `[entry_time, exit_time]` con `news_windows`); `design.md` DEBE documentar explícitamente la condición exacta como una decisión de diseño derivada, citando este riesgo. |
| Rg-2 | `FirmProfile` no expone `weekend_holding`; este Change lo resuelve añadiéndolo a `RiskProfile` (R11), duplicando conceptualmente un campo que en el spec (§1.1) vive en `prop_profile.json` junto a `daily_loss_limit`/`max_loss_limit`. | Si un Change futuro de datos extiende `FirmProfile` con `weekend_holding`, quedarían dos fuentes de verdad parciales (una en cada capa). | Documentado explícitamente en R11 como campo *no expuesto por FirmProfile*; si `genesis.data` lo incorpora en el futuro, `RiskProfile` puede dejar de cargarlo por defecto y delegar a `FirmProfile` sin romper compatibilidad (campo opcional). |
| Rg-3 | Umbral de tolerancia de R18 (cobertura de ticks) fijado en "dentro del minuto de la vela" sin margen adicional; si los ticks de MT5 llegan con timestamps ligeramente desalineados del cierre de vela M1, podría subestimarse la cobertura real disponible. | Uso excesivo del fallback conservador en vez de fills por tick real, aunque haya datos disponibles. | `design.md` puede ajustar el margen si la exploración empírica de datos reales (Issue B) muestra desalineación sistemática; R18 es el criterio mínimo verificable de este Change, no un valor cerrado a prueba de ajuste fino. |
| Rg-4 | `SimulationClock` sin ventana deslizante (R8) podría obligar a un rediseño si Issue F (Candidato A, trailing estructural) necesita historia de barras confirmadas. | Retrabajo en F si extender `SimulationClock` de forma aditiva resulta más costoso de lo previsto. | ADR-C3 ya autoriza la extensión aditiva a cualquier consumidor (no exclusiva de G); documentado como decisión explícita de este Change (trade-off 4, §3), no como omisión accidental. |
| Rg-5 | `BacktestConfigError` unifica tres disparadores heterogéneos (config inválida, protocolo faltante, símbolo no soportado) bajo una sola excepción (R3). | Un consumidor de Issue H que necesite distinguir el motivo exacto del fallo tendría que inspeccionar el mensaje en vez de un tipo distinto. | Aceptado como riesgo menor: el mensaje con contexto explícito (R4) permite distinguir el caso; si Issue H necesita tipos distintos, puede subclasificar `BacktestConfigError` sin romper el contrato de esta capa. |
| Rg-6 | Sin `tests/backtest/` previo, no hay patrón de fakes/fixtures ya validado para escenarios de sesión/breach propios de esta capa. | Mayor esfuerzo de diseño de testing desde cero, aunque `tests/strategy/fakes.py` es parcialmente reutilizable. | R51 replica explícitamente el patrón ya validado de `tests/strategy/` (conftest, fakes) extendido con escenarios propios de sesión/breach/gap. |
| Rg-7 | CLI de `backtest` diferida (§1.3, alcance OUT) podría bloquear a Issue H si asumiera una interfaz de línea de comandos ya construida. | Retrabajo si H necesita invocar el simulador vía CLI en vez de API programática. | El spec (§6) no ata la CLI unificada a un issue concreto antes de que exista un candidato real (Issue E); H puede consumir directamente las funciones/clases programáticas de `simulator.py`/`ledger.py`/`metrics.py` sin CLI intermedia. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Nombre exacto del orquestador principal de `simulator.py` (`Simulator` como clase con estado vs.
  `run_backtest(...)` como función) — se resuelve en `design.md` respetando el comportamiento de
  R22.
- Forma exacta de la estructura de posición abierta (`Position`, `OpenTrade`, o similar) que
  `simulator.py`/`ledger.py` comparten — este documento fija el comportamiento observable (R22-R36,
  R44-R46), no la forma exacta de la dataclass intermedia.
- Si `BreachEvent` (R44) y `LedgerEntry` (R45) son la misma estructura con campos opcionales o dos
  estructuras distintas unidas por un tipo suma (`Decision = LedgerEntry | BreachEvent`) — decisión
  de `design.md`, ninguna de las dos formas contradice los requisitos de esta especificación.
- Margen de tolerancia exacto (si alguno, más allá de "dentro del minuto de la vela") para R18 —
  ver Riesgo Rg-3; se puede ajustar en `design.md` si la exploración de datos reales lo justifica,
  sin relajar el requisito de que ambas condiciones (a)/(b) deben cumplirse.
- Si el "gap de apertura" (R33/R34) debe evaluarse también cuando la posición fue abierta en la
  misma vela que se cierra (mismo bar de entrada y salida) o solo entre velas distintas —
  `design.md` debe fijar el caso exacto con un golden test adicional si aplica.

---

## 10. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/6
- `idea.md` / `proposal.md` de este Change (fases explore/propose) — 9 decisiones ya tomadas y 6
  trade-offs resueltos por este documento (§3).
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §1.1 (`prop_profile.json`,
  `weekend_holding`, `max_loss_limit`), §1.3 (base doble del `daily_loss_limit`, `max_loss_limit=
  10%`, `daily_reset_time`), §2.1 (contrato de C, `EntryIntent` mínimo), §2.3 (Candidato B, cierre
  forzado, `SessionBoundaryError`, tabla de sesiones), §3 (arquitectura de 4 capas, "núcleo propio,
  periferia pragmática"), §4/§4.1 (capa de datos, ticks, política de extracción), §5.2 (los 4
  módulos de `python/backtest/`), §6/§6.1 (flujo de validación, consumidores de G), §7.1-§7.3
  (gates G/C/P que `metrics.py` alimenta y que H/J calculan), §8 (manejo de errores, tabla de
  excepciones), §9 (testing: propiedad forward-only + propiedad de equity idéntica), §11 (tabla de
  issues, dependencia G→C, G bloquea H), §11.1 (PA-2 heredada de B), §11.2 (dependencias de
  runtime).
- Spec promovido de Issue C (contrato normativo cerrado): `.pulse/changes/archive/
  4-c-feat-strategy-contrato-plugin-inspector-compartido-componentes/spec.md` — R1-R47, en
  especial R3 (`EntryIntent` exactamente 4 campos), R8/R45 (jerarquía de excepciones sin raíz
  compartida), R10/R11 (`BarClock`), R15 (`RejectionReason` exactamente 3 miembros).
- `proposal.md`/`design.md` de Change C (archivado): ADR-C3 (`BarClock` mínimo, extensión aditiva
  diferida a G), ADR-C4 (jerarquía de excepciones sin raíz compartida), RI-5 (tensión de
  `proposed_rr`/`EntryIntent`, resuelta en el proposal de este Change con `RiskLevelsProvider`).
- Código de la capa de estrategia consumido: `src/genesis/strategy/contract.py` (`EntryIntent:33`,
  `StrategyCandidate:47`, `Direction:25`), `clock.py` (`BarClock:14`), `inspector.py`
  (`inspect:85`, `InspectorVerdict:43`, `RejectionReason:29`, `InspectorFunnelConfig:58`),
  `errors.py` (`GenesisStrategyError:4`, `LookaheadError:12`).
- Código de la capa de datos consumido: `src/genesis/data/store.py` (`AnnotatedBar:28`,
  `iter_bars:68`, `DayBoundaryError:23`), `sessions.py` (`session_window:60`, `SESSIONS:24`),
  `profile.py` (`FirmProfile:32`, `load_firm_profile:64`, `firm_profile_hash:100` — sin
  `max_loss_limit_pct` ni `weekend_holding`), `symbols.py` (`SymbolFigure:12`), `metadata.py`
  (`ArtifactMetadata:52`, `sha256_of:22`, `current_git_commit:30`, `CONFIG_VERSION:18`),
  `calendar.py` (`news_windows:69`, `EconomicEvent:35`), `mt5_export.py` (`RawParquetStore:267`,
  `read_chunk:303`, `has_chunk:299`, `Granularity:64`, `ChunkWindow:72` — API pública confirmada,
  sin modificación).
- Árbol destino de este Change: `src/genesis/backtest/` (hoy solo `__init__.py` vacío, sin
  símbolos).
- Tests de referencia (patrón a replicar): `tests/strategy/{conftest.py, fakes.py,
  test_contract_lookahead_property.py}`, `tests/data/test_integration_export_quality.py` (patrón
  de test de integración pipeline completo).
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `AGENTS.md` (raíz) — invariantes de código citados textualmente del spec.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, comandos, flujo SDD.
- `pyproject.toml` — dependencias de runtime actuales (`metatrader5`, `numpy`, `pandas`,
  `pyarrow`; sin `scipy`/`statsmodels`/`matplotlib`/`quantstats` — confirma R58) y marcadores de
  pytest registrados (`--strict-markers`: `unit`, `integration`, `e2e`, `statistical`, `slow`).

<!-- change:21-fix-backtest-iter-ticks-emite-timestamps-del-reloj-del-servidor -->
# Specification: fix(backtest) — `iter_ticks` reinterpreta el reloj del servidor (`server_tz`) en lectura (Issue #21)

SSoT: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.2.1
(diagnóstico de señal desnuda), §9 (testing), §11 (gobernanza SDD). Este documento formaliza
`idea.md` y `proposal.md` de este Change en requisitos verificables y **continúa** la numeración de
`.pulse/specs/backtest/spec.md` (R1-R61, promovido del Change #6/G) a partir de **R62**, sin
renumerar ni contradecir ningún requisito ya promovido. Los gates G/C/P/T del spec **nunca se
relajan**; este Change no toca ninguno de ellos.

Convención de rutas: todas las rutas de este documento son las reales del repo
(`src/genesis/...`).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Corregir `iter_ticks` (`src/genesis/backtest/ticks.py:58-90`) para que reinterprete el timestamp
crudo del Parquet de ticks como hora local del servidor MT5 (`profile.server_tz`) y lo convierta a
UTC real — el mismo criterio `zoneinfo` sin-offset-fijo que ya usa `_to_utc`
(`src/genesis/data/store.py:41-56`) para barras M1 — aplicado en **lectura**, nunca en escritura
(R28 de `.pulse/specs/data/spec.md`: el Parquet crudo guarda el reloj del servidor, invariante que
este Change preserva). El fix resuelve dos componentes indisociables: `(1)` la conversión de zona
horaria en sí, y `(2)` el borde de día — los chunks de ticks están físicamente particionados por el
día calendario del **servidor**, así que un día UTC objetivo puede requerir leer 1-2 (raramente 3,
en un borde de DST) chunks de servidor adyacentes vía la API ya pública `has_chunk`/`read_chunk`.

Este Change desbloquea la reanudación de la corrida D (piloto FTMO, `server_tz=Europe/Athens`,
offset +3) y restaura la validez de cualquier veredicto §2.2.1 (archivar/continuar el Candidato A)
derivado de una ficha de firma con `server_tz ≠ UTC`.

### 1.2. Alcance IN

- `src/genesis/backtest/ticks.py`: `iter_ticks`, `has_sufficient_tick_coverage` ganan el parámetro
  `profile: FirmProfile`; nuevas funciones privadas `_to_utc` (copia local) y
  `_candidate_server_dates` (helper compartido de resolución de fechas de servidor candidatas).
- `src/genesis/backtest/simulator.py`: `IntradaySimulator/Simulator._day_ticks_for`/`_process_bar`
  propagan `self.firm_profile` a `iter_ticks`/`has_sufficient_tick_coverage`.
- `src/genesis/validation/signal_diagnostic.py`: `estimate_roundtrip_cost` gana el parámetro
  `profile: FirmProfile`; `run_signal_diagnostic` cierra el hueco de plomería reenviando el
  `profile` que ya recibe.
- `tests/backtest/test_ticks.py`, `tests/backtest/fakes.py::build_tick_chunk`,
  `tests/backtest/test_forward_only_property.py`, `tests/validation/test_signal_diagnostic.py`:
  actualización a la nueva firma + tests nuevos (repro TDD, property `server_tz ≠ UTC`, golden
  multi-chunk, forward-only con `tick_store` poblado).
- Re-ejecución empírica (no pytest) de `genesis-validate diagnose` sobre el piloto US500 de la
  corrida D como evidencia de aceptación del cierre de este Change.

### 1.3. Alcance OUT (YAGNI explícito)

- **No** modifica el formato del Parquet crudo ni ningún archivo de `src/genesis/data/` o
  `src/genesis/strategy/` (extiende R57: `git diff --stat -- src/genesis/data src/genesis/strategy`
  DEBE quedar vacío).
- **No** reexporta ni reescribe ningún chunk ya persistido en `data/raw/`; opera enteramente en
  lectura (R28 de `data/spec.md` preservado).
- **No** relaja ni cambia ningún umbral o criterio de gate (§2.2.1 ARCHIVE/CONTINUE, R118 de
  `strategy/spec.md`; ni los gates G/C/P/T de §7 del spec): el fix restaura el emparejamiento
  evento↔tick correcto, no toca la lógica de veredicto.
- **No** redefine el eje temporal de `trading_day`/`_day_window` más allá de resolver el borde de
  chunk de servidor: `_day_window` sigue construyendo `[00:00, 24:00) UTC` literal de la fecha de
  `trading_day`, sin re-anclarla a `daily_reset_time`/`daily_reset_tz`. La discrepancia preexistente
  entre `_day_window` (UTC literal) y `_trading_day()` de `store.py` (anclada a `daily_reset_tz`)
  queda documentada como riesgo separado (Rg-8, §8), no evidenciada como rota por este Change.
- **No** añade ninguna API pública nueva a `RawParquetStore`/`mt5_export.py` (ni `iter_chunks` ni
  variantes) — consume exclusivamente `has_chunk`/`read_chunk` ya públicos (extiende R15/R57).
- **No** añade ninguna dependencia de runtime nueva.
- **No** modifica el esquema de `SignalDiagnosticReport`/`ArtifactMetadata` (R119 de
  `strategy/spec.md`) — solo corrige el **valor** calculado de `roundtrip_cost`/
  `excluded_events_no_tick_coverage`, no su forma.
- **No** decide el bump de `CONFIG_VERSION = "genesis-validation-d/1"` de `signal_diagnostic.py`:
  queda a discreción de `design.md` (decisión residual #3 del proposal, §9 de este documento).

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **NO DEBE**, numerados continuando la secuencia de
  `.pulse/specs/backtest/spec.md` desde **R62**, cada uno verificable por al menos un test o una
  aserción `rg`/`fd`.
- Nombres de funciones son **normativos** (deben existir exactamente con ese nombre, verificable
  por `rg`); firmas exactas (orden de parámetros posicionales/keyword-only) se resuelven en
  `design.md` respetando el comportamiento aquí descrito.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- Aunque `signal_diagnostic.py` vive físicamente en `src/genesis/validation/`, pertenece
  normativamente al dominio `strategy` (Issue D, R116-R122 de `.pulse/specs/strategy/spec.md`); los
  requisitos de este documento sobre ese archivo (§4.3) son un ajuste de plomería acotado
  (propagación de `profile`) que no reabre ni contradice R116-R122.

---

## 3. Resolución de las decisiones residuales de `proposal.md`

`proposal.md` (§"Decisiones residuales que design.md/specify deben formalizar") dejó 4 puntos
pendientes de esta fase. Esta sección fija la resolución normativa de cada uno.

| # | Decisión residual | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | Nombre y firma exactos de la copia local de `_to_utc` y del helper compartido `_candidate_server_dates` | `_to_utc(raw_timestamp: Any, server_tz: ZoneInfo) -> datetime` (mismo nombre que `store.py::_to_utc`, módulo distinto, sin colisión de namespace) y `_candidate_server_dates(window: ChunkWindow, server_tz: ZoneInfo) -> list[date]`, ambas privadas de `ticks.py`. | R62, R63 |
| 2 | Semántica de existencia parcial de chunks en el borde (OR vs. AND) | **OR**: `has_sufficient_tick_coverage` considera cumplida la condición (a) si **al menos uno** de los chunks candidatos de `_candidate_server_dates` existe — nunca exige que todos existan. | R69 |
| 3 | Si `CONFIG_VERSION` de `signal_diagnostic.py` (`"genesis-validation-d/1"`) debe incrementarse | **Diferido a `design.md`**: ningún requisito de este documento lo exige; no bloquea el cierre de este Change (ver §9, preguntas abiertas). | — |
| 4 | Criterio `DADO/CUANDO/ENTONCES` exacto del property test de R52 con `tick_store` poblado | Formalizado en R82 (§4.4) y en el eval correspondiente de §7. | R82 |

---

## 4. Requisitos por módulo

### 4.1. `src/genesis/backtest/ticks.py` — conversión de zona horaria + borde de día

**Requisitos**:

- **R62** (DEBE). `ticks.py` DEBE definir una función privada `_to_utc(raw_timestamp: Any,
  server_tz: ZoneInfo) -> datetime`, semánticamente idéntica a `genesis.data.store._to_utc`
  (`store.py:41-56`): descarta cualquier `tzinfo` que ya traiga `raw_timestamp`, reinterpreta sus
  componentes de reloj de pared como `server_tz` vía `zoneinfo.ZoneInfo` (**nunca** un offset fijo
  — `timedelta` constante o similar — R28/R40 de `.pulse/specs/data/spec.md`), y convierte a UTC
  real. El docstring de esta copia DEBE declarar explícitamente que es intencional y debe
  mantenerse semánticamente sincronizada con `store.py::_to_utc` si alguna cambia. `ticks.py` NO
  DEBE importar el símbolo privado `_to_utc` de `genesis.data.store` (`rg -n "from genesis\.data\.
  store import.*_to_utc|from genesis\.data import store" src/genesis/backtest/ticks.py` DEBE
  retornar 0 coincidencias).
- **R63** (DEBE). `ticks.py` DEBE definir una función privada compartida
  `_candidate_server_dates(window: ChunkWindow, server_tz: ZoneInfo) -> list[date]` que retorne, en
  orden ascendente y sin duplicados, cada fecha calendario de `server_tz` que intersecta `window`:
  el rango inclusive derivado de `window.start.astimezone(server_tz).date()` hasta
  `(window.end - timedelta(microseconds=1)).astimezone(server_tz).date()`, iterado día a día. NO
  DEBE hardcodear un número fijo de fechas candidatas (p. ej. "siempre 2") ni imponer un límite
  artificial con error explícito — el rango está naturalmente acotado por la duración de `window`
  (típicamente 1-2 fechas; hasta 3 en un borde de transición DST del huso del servidor que alargue
  el día local a ~25h).
- **R64** (DEBE). `iter_ticks` DEBE ganar un parámetro obligatorio `profile: FirmProfile` (cambio de
  firma deliberado que rompe compatibilidad, mismo patrón que `iter_bars(frame, symbol, profile)`
  de `store.py:68-72`). Para `(symbol, trading_day)`, DEBE: `(a)` construir
  `window = _day_window(trading_day)` (sin cambiar su semántica de R35/R38 actual); `(b)` obtener
  `_candidate_server_dates(window, ZoneInfo(profile.server_tz))` (R63); `(c)` por cada fecha
  candidata cuyo chunk exista (`store.has_chunk(...)`), leerlo (`store.read_chunk(...)`), validar su
  esquema (`_validate_tick_schema`, sin cambios) y convertir cada timestamp crudo vía `_to_utc`
  (R62), acumulando los `TickRow` resultantes de todos los chunks candidatos leídos.
- **R65** (DEBE). Tras acumular los `TickRow` de todos los chunks candidatos (R64), `iter_ticks`
  DEBE filtrar el conjunto combinado a la ventana UTC objetivo original (`window` de R64(a), semántica
  `[00:00, 24:00)` sin cambios), ordenar el resultado por `timestamp_utc` ascendente (invariante ya
  existente) y emitir los `TickRow` filtrados.
- **R66** (DEBE). Si **ninguno** de los chunks candidatos de R63 existe para `(symbol, trading_day)`,
  `iter_ticks` DEBE seguir retornando una secuencia vacía sin lanzar ninguna excepción — extiende
  R16 al caso multi-chunk (la ausencia de ticks sigue siendo el caso normal, PA-2 de Issue B).
- **R67** (DEBE). Si al menos un chunk candidato de R63 existe pero su esquema es inválido (columnas
  `bid`/`ask`/`last` ausentes o mal tipadas), `iter_ticks` DEBE seguir lanzando
  `BacktestConfigError` con contexto — extiende R17 sin cambios de comportamiento observable.
- **R68** (DEBE). `has_sufficient_tick_coverage` DEBE ganar un parámetro obligatorio `profile:
  FirmProfile` y DEBE reutilizar **literalmente** la misma función `_candidate_server_dates` (R63)
  que `iter_ticks` para resolver los chunks candidatos de `bar.trading_day` — NUNCA reimplementar
  independientemente la misma lógica de resolución de fechas (garantiza que ambas funciones
  comparten el mismo criterio de borde, invariante ya documentado en el docstring del módulo,
  `ticks.py:7-8`).
- **R69** (DEBE). La condición `(a)` de `has_sufficient_tick_coverage` (existencia de chunk
  persistido) DEBE evaluarse como "existe **al menos uno** de los chunks candidatos de
  `_candidate_server_dates`" (OR) — NUNCA "todos los candidatos existen" (AND). Formaliza la
  decisión residual #2 (§3): con offset ≠ 0 y solo un chunk de servidor de los 1-3 candidatos
  persistido (p. ej. el chunk del día siguiente aún no exportado), la vela sigue considerándose con
  cobertura si el chunk existente ya la cubre — extiende R18 sin relajar la condición `(b)`
  (al menos un tick en `(T-60s, T]`), que no cambia.
- **R70** (NO DEBE). Ningún método nuevo se añade a `RawParquetStore`/`mt5_export.py` en este
  Change: `iter_ticks`/`has_sufficient_tick_coverage` consumen exclusivamente `has_chunk`/
  `read_chunk` ya públicos, incluso al resolver múltiples chunks candidatos (extiende R15/R57;
  `rg -n "RawParquetStore" src/genesis/backtest/ticks.py` sigue mostrando solo esos dos métodos).
- **R71** (DEBE). Con `profile.server_tz == "UTC"`, el comportamiento observable de `iter_ticks`/
  `has_sufficient_tick_coverage` (valores emitidos de `TickRow.timestamp_utc`, resultado booleano
  de cobertura) DEBE ser **idéntico** al comportamiento actual (pre-fix): offset 0 implica
  exactamente un chunk candidato por `_candidate_server_dates` (sin spillover de borde de día),
  de modo que los tests existentes de `tests/backtest/test_ticks.py` (adaptados a la nueva firma)
  siguen produciendo los mismos valores esperados — invarianza de regresión.
- **R72** (NO DEBE). `ticks_in_bar_window` NO cambia de firma ni de comportamiento: sigue operando
  exclusivamente sobre `TickRow` ya convertidos a UTC real por `iter_ticks` (R64/R65), sin recibir
  `profile`.

### 4.2. `src/genesis/backtest/simulator.py` — propagación de `FirmProfile`

**Requisitos**:

- **R73** (DEBE). `Simulator._day_ticks_for` (`simulator.py:288-296`) DEBE pasar `self.firm_profile`
  (ya disponible en `__init__`, sin cambios de constructor) a `iter_ticks` (R64).
- **R74** (DEBE). `Simulator._process_bar` (`simulator.py:298-322`) DEBE pasar `self.firm_profile` a
  `has_sufficient_tick_coverage` (R68).
- **R75** (NO DEBE). Ningún otro comportamiento del motor de fills (R32-R36 de
  `.pulse/specs/backtest/spec.md`) cambia: la regla SL-primero, el gap de apertura y la resolución
  de fills por tick real operan igual que hoy, solo con `TickRow.timestamp_utc` ya corregido.

### 4.3. `src/genesis/validation/signal_diagnostic.py` — cierre del hueco de plomería

**Requisitos**:

- **R76** (DEBE). `estimate_roundtrip_cost` (`signal_diagnostic.py:96-129`) DEBE ganar un parámetro
  obligatorio `profile: FirmProfile` y reenviarlo a `iter_ticks`/`has_sufficient_tick_coverage`
  (R64/R68).
- **R77** (DEBE). `run_signal_diagnostic` (`signal_diagnostic.py:147-171`) DEBE reenviar el
  parámetro `profile` que ya recibe (línea 152) a `estimate_roundtrip_cost(store, symbol, events,
  profile)` en la línea 170 — cierra el hueco de plomería identificado en `idea.md` (hoy omite
  `profile` en esa llamada).
- **R78** (NO DEBE). La lógica de exclusión de eventos sin cobertura suficiente (R117 de
  `.pulse/specs/strategy/spec.md`: nunca degradar a un spread promedio sustituto) NO cambia; solo
  cambia el **valor** de `roundtrip_cost`/`excluded_events_no_tick_coverage` calculado, no la forma
  de `SignalDiagnosticReport` (R119 de `strategy/spec.md`, sin cambios de esquema).

### 4.4. Testing (`tests/backtest/`, `tests/validation/`)

**Requisitos**:

- **R79** (DEBE). `tests/backtest/test_ticks.py` DEBE incluir un test de reproducción escrito
  **antes** del fix (TDD): un chunk de ticks construido con el patrón `_server_local_frame` de
  `tests/data/test_store.py:20-32` (timestamps *naive* representando hora local del servidor,
  adaptado a `build_tick_chunk`/`tests/backtest/fakes.py:87-116`) y un `FirmProfile` con
  `server_tz="Europe/Athens"` (offset +3, replicando el piloto de la corrida D), verificando que
  `iter_ticks` emite `TickRow.timestamp_utc` desplazado correctamente (falla contra el código
  anterior al fix, pasa después).
- **R80** (DEBE). `tests/backtest/` DEBE incluir un test de propiedad `hypothesis`
  (`max_examples>=1000`, marcado `pytest.mark.unit`) con un `FirmProfile` de `server_tz ≠ UTC`
  arbitrario que verifique: para un tick generado en un instante real `T` arbitrario, aparece
  exactamente en la ventana `(T-60s, T]` del evento correspondiente. DEBE generar casos que crucen
  el borde de día del servidor (offset empujando la medianoche de servidor a través de la
  medianoche UTC) y ambos cambios de DST del huso del servidor (spring-forward y fall-back),
  análogo en estructura a `tests/backtest/test_forward_only_property.py`.
- **R81** (DEBE). `tests/backtest/` DEBE incluir al menos un test golden/integración que escriba dos
  chunks de servidor adyacentes (fechas `D` y `D+1`) con un offset conocido (`server_tz ≠ UTC`) y
  verifique que `iter_ticks` fusiona y ordena correctamente los ticks de ambos ficheros dentro de la
  ventana UTC objetivo, y que `has_sufficient_tick_coverage` usa el mismo mecanismo de resolución de
  fechas (R68) sin divergir del resultado de `iter_ticks`.
- **R82** (DEBE). `tests/backtest/test_forward_only_property.py` DEBE incluir, además del caso
  existente con `tick_store=None`, un caso equivalente con `tick_store` poblado con chunks
  sintéticos de `server_tz ≠ UTC` (patrón `hypothesis`, `max_examples>=1000`), verificando el
  criterio exacto:
  ```
  DADO   un Simulator con tick_store poblado (chunks de server_tz != UTC) y un prefijo arbitrario
         de AnnotatedBar procesado hasta el instante t
  CUANDO se capturan ledger.entries y account.balance inmediatamente después del prefijo, y LUEGO
         se alimentan dos colas futuras (suffix_a, suffix_b) arbitrarias y distintas de barras/ticks
         con timestamp_utc > t
  ENTONCES ledger.entries y account.balance capturados tras el prefijo son idénticos entre ambas
           ejecuciones, independientemente de qué cola futura se alimente después (R52 extendido a
           tick_store poblado)
  ```
- **R83** (DEBE). Los tests existentes de `tests/backtest/test_ticks.py`,
  `tests/backtest/fakes.py::build_tick_chunk` y cualquier test de `simulator.py`/
  `signal_diagnostic.py` que invoque las firmas cambiadas (R64/R68/R76) DEBEN actualizarse para
  pasar explícitamente un `FirmProfile` (con `server_tz="UTC"` donde el test ya asume timestamps
  ya-en-UTC), verificando que el comportamiento observable (R71) es idéntico al actual.
- **R84** (DEBE). Como evidencia de aceptación de cierre de este Change (no parte de la suite
  pytest versionada), DEBE re-ejecutarse `genesis-validate diagnose --candidate A --firm ftmo
  --symbol US500 ...` sobre el piloto de la corrida D (mismos Parquets de `data/raw/`, ficha
  `out/run_d/ftmo.json` con `server_tz=Europe/Athens`) y documentarse que
  `excluded_events_no_tick_coverage` es marginal (solo bordes reales de sesión, no 317/319 como en
  el reporte pre-fix) y que `roundtrip_cost` se recalcula sobre la ventana correcta.
- **R85** (DEBE). `uv run mise run ci` (ruff+bandit+vulture+deptry+ty+test) DEBE pasar en verde
  sobre `src/genesis/backtest/`, `src/genesis/validation/signal_diagnostic.py` y sus tests.

---

## 5. Invariantes transversales

- **R86** (DEBE). Ningún archivo de `src/genesis/data/` ni de `src/genesis/strategy/` DEBE
  modificarse en este Change (extiende R57: `git diff --stat -- src/genesis/data
  src/genesis/strategy` vacío).
- **R87** (NO DEBE). Este Change NO DEBE reexportar ni reescribir ningún chunk ya persistido en
  `data/raw/` — el fix opera enteramente en lectura (R28 de `data/spec.md` preservado).
- **R88** (NO DEBE). Este Change NO DEBE relajar ni modificar ningún umbral o criterio de gate
  (§2.2.1 ARCHIVE/CONTINUE, R118 de `strategy/spec.md`; gates G/C/P/T de §7 del spec).
- **R89** (NO DEBE). Este Change NO DEBE añadir ninguna dependencia de runtime nueva a
  `pyproject.toml` (`[project.dependencies]`).
- **R90** (NO DEBE). Este Change NO DEBE modificar el esquema (campos) de `SignalDiagnosticReport`
  ni de `ArtifactMetadata` — solo el valor calculado de `roundtrip_cost`/
  `excluded_events_no_tick_coverage` (R119 de `strategy/spec.md`, sin cambios de forma).
- **R91** (DEBE). `uv run mise run ci` DEBE pasar en verde sobre todo el repositorio tras este
  Change (extiende R61).

---

## 6. Manejo de errores (resumen normativo — sin cambios respecto a `.pulse/specs/backtest/spec.md` §6)

Este Change no introduce ninguna excepción de dominio nueva. La tabla de excepciones de
`.pulse/specs/backtest/spec.md` §6 sigue vigente sin modificaciones: `BacktestConfigError` continúa
disparándose exactamente en los mismos tres casos (R3), extendido ahora a cubrir "chunk
presente-pero-inválido" también en el caso multi-chunk (R67).

| Excepción | Módulo | Disparador (tras este Change) | Efecto |
|---|---|---|---|
| `BacktestConfigError` | `genesis.backtest.errors` | Al menos un chunk candidato de `_candidate_server_dates` existe pero su esquema es inválido (R67) | Aborta el run (sin cambios respecto a R17) |
| (sin excepción) | `genesis.backtest.ticks` | Ningún chunk candidato existe (R66) | `iter_ticks` retorna secuencia vacía; `has_sufficient_tick_coverage` retorna `False` (R69) |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "def _to_utc" src/genesis/backtest/ticks.py
       y rg -n "def _candidate_server_dates" src/genesis/backtest/ticks.py
       y rg -n "from genesis\.data\.store import.*_to_utc" src/genesis/backtest/ticks.py
ENTONCES las dos primeras retornan >=1 coincidencia cada una; la tercera retorna 0 coincidencias
         (R62, R63: copia local, nunca import del símbolo privado de store.py)
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "def iter_ticks" src/genesis/backtest/ticks.py
       y rg -n "def has_sufficient_tick_coverage" src/genesis/backtest/ticks.py
ENTONCES ambas firmas incluyen un parámetro profile: FirmProfile (R64, R68)
```

```
DADO   un RawParquetStore con un chunk de ticks del día de servidor D escrito con timestamps
       naive (hora local del servidor, server_tz="Europe/Athens", offset +3) que representa el
       cierre real de sesión ~20:49 UTC
CUANDO se invoca iter_ticks(store, symbol, trading_day, profile) con ese profile
ENTONCES los TickRow.timestamp_utc emitidos reflejan el instante UTC real (~20:49 UTC), no el
         valor crudo etiquetado UTC sin reinterpretar (R64, repro del bug de idea.md)
```

```
DADO   un día UTC objetivo cuya medianoche de servidor (server_tz != UTC) cae fuera de ese día
       calendario UTC, con chunks de servidor persistidos para las fechas D y D+1
CUANDO se invoca iter_ticks(store, symbol, trading_day, profile)
ENTONCES el resultado combina y ordena ascendentemente los ticks de ambos chunks, filtrados a la
         ventana UTC [00:00, 24:00) de trading_day (R64, R65, golden multi-chunk R81)
```

```
DADO   un RawParquetStore sin NINGÚN chunk candidato persistido para (symbol, trading_day, profile)
CUANDO se invoca iter_ticks(store, symbol, trading_day, profile)
ENTONCES retorna una secuencia vacía sin lanzar ninguna excepción (R66, extiende R16)
```

```
DADO   dos chunks candidatos de servidor para un trading_day, de los cuales solo UNO está
       persistido (el otro aún no se exportó) y ese chunk existente ya cubre todas las velas
       reales de sesión de ese trading_day
CUANDO se invoca has_sufficient_tick_coverage(store, symbol, bar, day_ticks, profile) para una
       vela cubierta por el chunk existente
ENTONCES retorna True (condición OR de R69, no AND: no se exige que TODOS los candidatos existan)
```

```
DADO   un FirmProfile con server_tz="UTC"
CUANDO se invoca iter_ticks/has_sufficient_tick_coverage con ese profile sobre los mismos chunks
       de test ya existentes en tests/backtest/test_ticks.py (adaptados a la nueva firma)
ENTONCES los valores emitidos son idénticos a los que producía el código anterior al fix (R71,
         invarianza de regresión)
```

```
DADO   el repositorio tras este Change
CUANDO rg -n "RawParquetStore" src/genesis/backtest/ticks.py
ENTONCES muestra únicamente invocaciones a has_chunk/read_chunk, ningún método nuevo (R70, extiende
         R15/R57)
```

```
DADO   el archivo src/genesis/backtest/simulator.py
CUANDO rg -n "iter_ticks\(self\.tick_store, self\.symbol" src/genesis/backtest/simulator.py
       y rg -n "has_sufficient_tick_coverage\(self\.tick_store, self\.symbol" src/genesis/backtest/simulator.py
ENTONCES ambas líneas incluyen self.firm_profile como argumento adicional (R73, R74)
```

```
DADO   el archivo src/genesis/validation/signal_diagnostic.py
CUANDO rg -n "def estimate_roundtrip_cost" src/genesis/validation/signal_diagnostic.py
       y rg -n "estimate_roundtrip_cost\(store, symbol, events, profile\)" src/genesis/validation/signal_diagnostic.py
ENTONCES la primera incluye profile: FirmProfile en la firma; la segunda retorna >=1 coincidencia
         dentro de run_signal_diagnostic (R76, R77: hueco de plomería cerrado)
```

```
DADO   una secuencia arbitraria de AnnotatedBar/TickRow (tick_store poblado, server_tz != UTC)
       procesada por un Simulator hasta el instante t
CUANDO se mutan (agregan/alteran) barras o ticks con timestamp_utc > t en la secuencia de entrada
ENTONCES el ledger/balance capturado en t no cambia (R82, extiende R52 a tick_store poblado)
```

```
DADO   el repositorio tras completar este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy
ENTONCES no retorna ninguna línea (R86, extiende R57)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/backtest/test_ticks.py tests/backtest/test_forward_only_property.py
       tests/validation/test_signal_diagnostic.py -v
ENTONCES pasa en verde, incluyendo el test de reproducción TDD (R79), el property test con
         server_tz != UTC cubriendo borde de día + ambos DST (R80), el golden multi-chunk (R81), y
         el caso forward-only con tick_store poblado (R82)
```

```
DADO   el piloto empírico de la corrida D (US500, server_tz=Europe/Athens, offset +3)
CUANDO se re-ejecuta genesis-validate diagnose sobre los mismos Parquets de data/raw/ con el
       código corregido
ENTONCES excluded_events_no_tick_coverage es marginal (no 317/319 como en el reporte pre-fix) y
         roundtrip_cost se recalcula sobre la ventana correcta (R84, evidencia de aceptación)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0, R85, R91)
```

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-8 | `_day_window` sigue construyendo `[00:00, 24:00) UTC` literal de `trading_day`, mientras que `_trading_day()` de `store.py` ancla el día de negocio a `daily_reset_time`/`daily_reset_tz` (no necesariamente UTC ni `server_tz`); esta discrepancia preexistente no se corrige en este Change (§1.3). | Si un símbolo futuro tuviera una sesión que cruza la medianoche UTC, el `trading_day` de `_day_window` podría no coincidir con el día de negocio real de `_trading_day()`. | Documentado explícitamente como fuera de alcance (§1.3); las sesiones de los símbolos soportados hoy (US500/NAS100/US30/GER40) no cruzan medianoche UTC, así que no hay evidencia empírica de que esté roto. Un Change futuro que añada un símbolo con sesión cruzando medianoche debe re-evaluar este riesgo explícitamente. |
| Rg-9 | La copia local de `_to_utc` en `ticks.py` (R62) y `store.py::_to_utc` deben permanecer semánticamente idénticas (zoneinfo, nunca offset fijo); un cambio futuro en una sin el equivalente en la otra introduciría divergencia silenciosa. | Bug de reinterpretación de zona horaria reintroducido en una sola capa, sin que ningún test cruzado lo detecte automáticamente. | R62 exige que el docstring de la copia documente explícitamente la obligación de sincronía; `design.md`/`review` deben verificar manualmente ambas funciones en cualquier PR que toque zona horaria en cualquiera de los dos módulos. |
| Rg-10 | El límite de "hasta 3 fechas candidatas" (R63) asume que ningún huso horario documentado en `profiles/*.json` tiene una transición DST que alargue el día local más allá de ~25h; esto no está garantizado por ningún test exhaustivo de todas las zonas IANA. | Un huso horario exótico no cubierto por los profiles actuales (`America/New_York`, `Europe/Athens`) podría, en teoría, generar más de 3 fechas candidatas. | Fuera de alcance verificarlo para husos no usados hoy por ninguna ficha de firma soportada (`profiles/the5ers.json`, `profiles/ftmo.json`); R63 no impone un límite artificial precisamente para no fallar silenciosamente si esto ocurriera, procesando cualquier número de fechas que el cálculo real produzca. |
| Rg-11 | Los artefactos derivados ya escritos con el bug activo (`out/signal_diagnostic/US500_pilot/report.json`, y cualquier otro reporte de diagnóstico previo a este fix) quedan inválidos hasta que se regeneren; no hay un mecanismo automático de invalidación. | Un consumidor podría leer un reporte pre-fix sin saber que es inválido. | Acción operativa explícita en R84: re-ejecutar `genesis-validate diagnose` como evidencia de aceptación del cierre de este Change; el mensaje de cierre del Change debe señalar qué artefactos previos quedan obsoletos. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Si `CONFIG_VERSION = "genesis-validation-d/1"` de `signal_diagnostic.py` debe incrementarse dado
  que los **valores** calculados cambian (aunque el esquema no) — decisión residual #3 del
  proposal (§3 de este documento); ningún requisito actual lo exige, queda a discreción de
  `design.md` por trazabilidad entre runs pre/post-fix.
- Forma exacta (nombre de parámetro, posicional vs. keyword-only) de `profile` en las firmas
  cambiadas de R64/R68/R76 — este documento fija el comportamiento observable, no la forma
  sintáctica exacta de la firma; `design.md` la resuelve respetando el patrón ya usado por
  `iter_bars(frame, symbol, profile)`.
- Si el riesgo Rg-8 (discrepancia `_day_window` vs. `_trading_day()`) debe convertirse en un Change
  futuro explícito o simplemente permanecer documentado indefinidamente — no es responsabilidad de
  este Change decidirlo.

---

## 10. Referencias

- Issue GitHub #21 — bbenja11/genesis (https://github.com/bbenja11/genesis/issues/21).
- `idea.md`/`proposal.md` de este Change (fases explore/propose) — problema, contexto, 7 preguntas
  abiertas y sus respuestas, diseño propuesto por módulo, alcance de testing, decisiones residuales.
- `.pulse/specs/backtest/spec.md` (Change #6/G, promovido): R15-R19 (contrato original de
  `iter_ticks`/cobertura de ticks, extendido por este documento), R57 (capas cerradas), §6 (tabla
  de manejo de errores, sin cambios).
- `src/genesis/backtest/ticks.py:1-132` — módulo completo a modificar (`_day_window`, `iter_ticks`,
  `_tick_in_bar_window`, `has_sufficient_tick_coverage`, `ticks_in_bar_window`).
- `src/genesis/data/store.py:41-56` (`_to_utc`, patrón de referencia, privado), `68-115`
  (`iter_bars`, patrón de firma `profile: FirmProfile`).
- `src/genesis/data/mt5_export.py:64-77` (`Granularity`, `ChunkWindow`), `253-256`
  (`_chunk_filename`), `267-354` (`RawParquetStore`: `has_chunk:299`, `read_chunk:303`, sin
  `iter_chunks`).
- `src/genesis/data/profile.py:32-49` (`FirmProfile`, campo `server_tz: str`).
- `src/genesis/backtest/simulator.py:213-322` (`Simulator.__init__`, `_day_ticks_for:288-296`,
  `_process_bar:298-322`).
- `src/genesis/validation/signal_diagnostic.py:96-129` (`estimate_roundtrip_cost`), `147-171`
  (`run_signal_diagnostic`).
- `.pulse/specs/strategy/spec.md:1672-1699` (R116-R122: contrato de `signal_diagnostic.py` con
  `ticks.py`, no reabierto por este Change).
- `.pulse/specs/data/spec.md:298-345` (R28-R41: `store.py`, `zoneinfo`, criterio sin-offset-fijo).
- `tests/backtest/test_ticks.py` (completo, hoy solo UTC); `tests/backtest/fakes.py:87-116`
  (`build_tick_chunk`); `tests/data/test_store.py:20-32` (`_server_local_frame`, patrón reutilizable
  para el repro); `tests/backtest/test_forward_only_property.py:1-109` (`tick_store=None` hoy);
  `tests/validation/test_signal_diagnostic.py` (tests de `estimate_roundtrip_cost`/
  `run_signal_diagnostic`).
- `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` §2.2.1 (diagnóstico de señal desnuda),
  §9 (testing), §11 (gobernanza SDD).
- `out/run_d/ftmo.json`, `out/signal_diagnostic/US500_pilot/report.json` — evidencia empírica del
  piloto (server_tz=Europe/Athens, offset +3, 317/319 eventos mal emparejados) y objetivo de la
  re-corrida de aceptación (R84).
- `data/raw/US500.cash/tick/2026/2026-06-26.parquet` — chunk citado como evidencia directa del
  timestamp máximo desplazado.
- `.agents/rules/architecture-conventions.md`, `.agents/rules/eval-tdd-conventions.md`,
  `.agents/rules/tooling-conventions.md` — convenciones de proceso.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, flujo SDD, convenciones de commits/testing.

<!-- change:24-perf-backtest-iter-ticks-itera-con-iterrows-tz-por-fila-47x-medi -->
# Specification: perf(backtest) — vectorizar `iter_ticks` e indexar con `bisect` las ventanas por evento (Issue #24)

SSoT: `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.2.1
(diagnóstico de señal desnuda), §9 (testing EDD/TDD), §11 (gobernanza SDD). Este documento formaliza
`idea.md` y `proposal.md` de este Change en requisitos verificables y **continúa** la numeración de
`.pulse/specs/backtest/spec.md` (R1-R61 promovido de Change #6/G, R62-R91 promovido de Change #21) a
partir de **R92**, sin renumerar ni contradecir ningún requisito ya promovido. Los gates G/C/P/T del
spec **nunca se relajan**; este Change no toca ninguno de ellos.

Convención de rutas: todas las rutas de este documento son las reales del repo (`src/genesis/...`).

Este Change es la secuela directa de Change #21 (`fix(backtest): iter_ticks reinterpreta
server_tz`, cerrado 2026-07-18, mismo archivo `ticks.py`): #21 corrigió la **correctitud** de la
reinterpretación de `server_tz`; #24 corrige el **rendimiento** del mismo código que #21 acaba de
tocar, sin reabrir ninguna de sus decisiones (R62-R91 permanecen intactos).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Optimizar el rendimiento de `iter_ticks`, `has_sufficient_tick_coverage` y `ticks_in_bar_window`
(`src/genesis/backtest/ticks.py`, post Change #21) sin alterar su contrato público ni su semántica
observable:

1. **Vectorizar `iter_ticks`**: sustituir el bucle `for _, row in frame.iterrows(): timestamp_utc =
   _to_utc(row["timestamp"], server_tz)` (`ticks.py:133-143`, 112 µs/fila medido, ~29 s/día de 256k
   ticks) por un mecanismo **híbrido** por chunk: detectar si hay una transición DST dentro del
   chunk muestreando el offset de `server_tz` en sus dos extremos; si no la hay (caso común), aplicar
   una resta vectorizada de `Timedelta` constante (0,61 s/día medido, ~47x); si la hay (raro, ~2
   días/año por huso), reutilizar sin modificar el bucle escalar `_to_utc` existente, acotado a ese
   chunk — bit-identidad garantizada por construcción, nunca por disambiguación de pandas.
2. **Indexar con `bisect` las ventanas por evento**: sustituir el escaneo lineal `any(...)` (
   `has_sufficient_tick_coverage`) y la list-comprehension + `sorted()` redundante (
   `ticks_in_bar_window`) por dos índices `bisect_right` sobre `day_ticks` (ya ordenado ascendente,
   invariante existente) derivados de un único helper privado compartido.

Restaura la viabilidad de tiempo de ejecución de `genesis-validate diagnose` (1h46min medido en la
corrida D, US500, 173 sesiones) y evita que las fases G/C/P/T (WFA, purged K-fold, Monte Carlo,
`prop_sim`) hereden el mismo coste multiplicado ×10-100 antes de arrancar (Issue H en adelante).

### 1.2. Alcance IN

- `src/genesis/backtest/ticks.py`: reescritura **interna** de `iter_ticks` (mecanismo híbrido
  vectorizado/escalar-por-chunk); dos funciones privadas nuevas, `_has_dst_transition` y
  `_bisect_window_bounds`; reescritura interna de `has_sufficient_tick_coverage`/
  `ticks_in_bar_window` sobre `_bisect_window_bounds`. **Ninguna firma pública cambia** (a
  diferencia de #21, que sí rompió firmas deliberadamente).
- `scripts/bench_iter_ticks.py`: script nuevo de benchmark ad-hoc, no-pytest, sin dependencia dev
  nueva (directorio `scripts/` ya existe en la raíz, vacío).
- `tests/backtest/test_ticks_vectorization_differential.py`: archivo de test nuevo (property test
  `hypothesis` de equivalencia escalar↔vectorizado + `@example` DST pinneados).
- `tests/backtest/` (archivo existente o nuevo, a discreción de `design.md`): test de equivalencia
  `_bisect_window_bounds` vs. filtrado lineal de referencia.
- Re-ejecución empírica (no pytest) de `genesis-validate diagnose` sobre el dataset completo de la
  corrida D (US500) como evidencia de aceptación del cierre de este Change.

### 1.3. Alcance OUT (YAGNI explícito)

- **No** cambia ninguna firma pública de `ticks.py` (`iter_ticks`, `has_sufficient_tick_coverage`,
  `ticks_in_bar_window` conservan parámetros y tipos de retorno actuales, R119) ni el `__all__`
  curado de `genesis.backtest` (`tests/backtest/test_public_api.py` sin modificar).
- **No** modifica `TickRow` (mismo dataclass, mismos 4 campos, R120).
- **No** modifica `src/genesis/backtest/simulator.py`, `src/genesis/backtest/costs.py` ni
  `src/genesis/validation/signal_diagnostic.py` (R109-R111): se benefician de la aceleración sin
  ningún cambio de código ni de firma.
- **No** cambia el esquema de `SignalDiagnosticReport`/`ArtifactMetadata` ni el `CONFIG_VERSION` de
  `signal_diagnostic.py` (permanece `"genesis-validation-d/2"`, R125): los valores calculados no
  cambian, solo el tiempo de cómputo — a diferencia de #21, que sí incrementó `CONFIG_VERSION`
  porque los valores calculados cambiaban.
- **No** toca `src/genesis/data/` ni `src/genesis/strategy/` (capas cerradas, R57/R86 heredados,
  R121 de este documento).
- **No** añade ningún método nuevo a `RawParquetStore`/`mt5_export.py` (R70 heredado, R122 de este
  documento): `iter_ticks` sigue consumiendo exclusivamente `has_chunk`/`read_chunk` ya públicos.
- **No** modifica `_to_utc` (copia local sincronizada con `store.py::_to_utc`, Rg-9) ni
  `_candidate_server_dates` (R63) — se reutilizan tal cual.
- **No** relaja ni cambia ningún criterio o umbral de gate (§2.2.1 ARCHIVE/CONTINUE, gates G/C/P/T
  de §7 del spec, R88 heredado, R124 de este documento): es un fix de rendimiento puro.
- **No** resuelve Rg-8 (discrepancia `_day_window` UTC-literal vs. `_trading_day()`) ni Rg-10 (límite
  de fechas candidatas para husos DST no verificados exhaustivamente) — riesgos heredados de #21,
  fuera de alcance de un Change de rendimiento.
- **No** implementa paralelización a nivel de proceso/hilo (mitigación operacional externa ya
  existente, complementaria, fuera de `src/`).
- **No** añade `pytest-benchmark` ni ninguna dependencia de runtime o dev nueva (`bisect` es stdlib,
  R123).
- **No** vectoriza más allá de la conversión de zona horaria y la construcción de `TickRow`: si medir
  la materialización de `TickRow` como cuello de botella aparte del benchmark de R115 amerita un
  experimento aislado, queda diferido a un Change futuro (§9, no bloquea este Change).
- **No** decide si `_tick_in_bar_window` se conserva como referencia documental o se elimina tras
  dejar de tener llamadores en el camino caliente — diferido a `design.md` (R107), no afecta ningún
  comportamiento observable.

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **NO DEBE**, numerados continuando la secuencia de
  `.pulse/specs/backtest/spec.md` desde **R92**, cada uno verificable por al menos un test o una
  aserción `rg`/`fd`.
- Nombres de las dos funciones privadas nuevas (`_has_dst_transition`, `_bisect_window_bounds`) son
  **normativos** (deben existir exactamente con ese nombre, verificable por `rg`); el orden exacto
  de sus parámetros (posicionales vs. keyword-only) se resuelve en `design.md` respetando el
  comportamiento aquí descrito (mismo patrón que fijó `.pulse/specs/backtest/spec.md` §2 para
  `_to_utc`/`_candidate_server_dates` en Change #21).
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- `bisect.bisect_right(seq, valor, key=...)` (soportado nativamente desde Python 3.10, disponible en
  `requires-python=">=3.14"`) es la **primera introducción** de este patrón en `genesis.backtest`
  (`rg -n "bisect" src/ tests/` retorna 0 coincidencias antes de este Change).
- "Bit-idéntico"/"comportamiento observable idéntico" en este documento significa: mismos valores de
  `TickRow.timestamp_utc`/`bid`/`ask`/`last` emitidos, en el mismo orden, para la misma entrada —
  nunca una aproximación o tolerancia numérica.

---

## 3. Resolución de las decisiones residuales de `proposal.md`

`proposal.md` (§"Decisiones residuales que specify/design.md deben formalizar") dejó 6 puntos
pendientes de esta fase. Esta sección fija la resolución normativa de cada uno.

| # | Decisión residual | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | Nombre y firma exactos del helper de detección de transición DST y del helper `bisect` compartido | `_has_dst_transition(naive_min: datetime, naive_max: datetime, server_tz: ZoneInfo) -> bool` y `_bisect_window_bounds(day_ticks: Sequence[TickRow], bar_timestamp: datetime) -> tuple[int, int]`, ambas privadas de `ticks.py`. Orden exacto de argumentos (posicional/keyword-only) diferido a `design.md`. | R94, R103 |
| 2 | Condición de activación exacta del fallback per-chunk | **Únicamente** detección de transición DST (`_has_dst_transition`); NUNCA combinada con, ni sustituida por, un umbral de tamaño mínimo de frame — un chunk pequeño sin transición no tiene riesgo de correctitud y debe vectorizarse igual; uno grande con transición sí lo tiene y debe usar el fallback igual. | R108 |
| 3 | Ubicación/formato exacto de `scripts/bench_iter_ticks.py` | Ubicación fija: `scripts/bench_iter_ticks.py`, invocable vía `uv run python scripts/bench_iter_ticks.py`, mide el escenario de referencia del issue (día de ~256k ticks + símbolo completo) y reporta tiempo antes/después + factor de mejora, de forma reproducible (misma entrada, mismo resultado relativo). Formato exacto de salida (texto/JSON) y argumentos CLI diferidos a `design.md`. | R115 |
| 4 | Si medir la materialización de `TickRow` en el mismo benchmark basta, o si amerita un experimento aislado | **Diferido, no bloqueante**: se mide como parte del mismo benchmark de R115; si resulta cuello de botella dominante, queda documentado como oportunidad de un Change futuro (§9). No es criterio de éxito de este Change. | — |
| 5 | Nombre exacto del archivo de test diferencial + qué días DST concretos se usan como fixtures del caso multi-chunk con spillover | `tests/backtest/test_ticks_vectorization_differential.py`. Matriz fija de fixtures: día sin transición `2024-01-02` (mismo valor que `tests/backtest/test_ticks.py`); spring-forward `2024-03-31` (Europe/Athens) / `2024-03-10` (America/New_York); fall-back `2024-10-27` (Europe/Athens) / `2024-11-03` (America/New_York) — mismas fechas que los `@example` ya pinneados de `test_ticks_server_tz_property.py`; multi-chunk spillover `2026-06-26`→`2026-06-27` (Europe/Athens) — mismas fechas del golden R81 de Change #21. | R113 |
| 6 | Si el `sort()` final de `iter_ticks` puede demostrarse no-op | **Diferido a `design.md`**: se conserva incondicionalmente como red de seguridad (R101) salvo que `design.md` demuestre analítica y empíricamente que es no-op sin impacto medible en el benchmark — no bloquea este Change en ningún sentido observable (la bit-identidad se mantiene con o sin el `sort()`). | R101 (conserva), diferido |

---

## 4. Requisitos por módulo

### 4.1. `src/genesis/backtest/ticks.py` — vectorización híbrida de `iter_ticks`

**Requisitos**:

- **R92** (DEBE). `iter_ticks` DEBE reemplazar el bucle `for _, row in frame.iterrows():
  timestamp_utc = _to_utc(row["timestamp"], server_tz)` (`ticks.py:133-143`) por un mecanismo
  híbrido por chunk candidato (R94-R98), preservando exactamente el comportamiento observable
  (mismos `TickRow` emitidos, mismo orden, mismo filtrado a la ventana UTC objetivo) que el bucle
  escalar actual.
- **R93** (NO DEBE). `_validate_tick_schema` NO DEBE cambiar de comportamiento: sigue ejecutándose
  sobre el frame crudo devuelto por `read_chunk`, inmediatamente después de la lectura y **antes**
  de cualquier conversión de zona horaria (vectorizada o escalar) — extiende R67 sin cambios de
  comportamiento fail-fast (responde la Pregunta 6 de `idea.md`).
- **R94** (DEBE). `ticks.py` DEBE definir una función privada `_has_dst_transition(naive_min:
  datetime, naive_max: datetime, server_tz: ZoneInfo) -> bool` que retorna `True` si y solo si
  `naive_min.replace(tzinfo=server_tz).utcoffset() != naive_max.replace(tzinfo=server_tz)
  .utcoffset()`. Por cada chunk candidato leído, `iter_ticks` DEBE invocarla con `naive_min`/
  `naive_max` derivados de la primera y última fila de `frame["timestamp"]` tras retirar la etiqueta
  UTC incorrecta (`.dt.tz_localize(None)`) — acceso en O(1) porque el frame ya llega ordenado
  ascendentemente por `timestamp` (invariante de `_normalize_frame`, `mt5_export.py:264`), sin
  calcular `.min()`/`.max()` sobre toda la columna. Si el frame leído no tiene ninguna fila (chunk
  vacío), `iter_ticks` NO DEBE invocar `_has_dst_transition` sobre un frame vacío — se trata como
  cero ticks aportados, equivalente a que el bucle escalar tampoco iteraría ninguna fila.
- **R95** (DEBE). Si `_has_dst_transition` (R94) retorna `False` para un chunk (caso normal, sin
  transición DST — la mayoría de días del año), `iter_ticks` DEBE convertir `frame["timestamp"]` a
  UTC real mediante una operación vectorizada equivalente a: (a) retirar la etiqueta UTC incorrecta;
  (b) restar el `Timedelta` igual al offset único muestreado en R94 (resta constante, sin invocar
  `.dt.tz_localize(server_tz, ambiguous=..., nonexistent=...)` para la disambiguación); (c) adjuntar
  `tzinfo=UTC` al resultado. El valor de cada `TickRow.timestamp_utc` producido DEBE ser bit-idéntico
  (mismo instante, mismo tzinfo `UTC`) al que produce `_to_utc(raw_timestamp, server_tz)` fila a fila
  sobre el mismo valor crudo — bit-identidad garantizada analíticamente (resta de offset constante),
  porque sin transición dentro del chunk no hay ambigüedad ni hueco horario que resolver.
- **R96** (DEBE). Si `_has_dst_transition` (R94) retorna `True` para un chunk (transición DST
  detectada dentro de ese chunk — raro, ~2 días/año por huso soportado), `iter_ticks` DEBE resolver
  la conversión de zona horaria de **ese** chunk reutilizando literalmente la función `_to_utc`
  (R99, sin modificarla) aplicada fila a fila, acotada exclusivamente a ese chunk — garantiza
  bit-identidad por construcción con el bucle escalar actual (es literalmente la misma función que
  ya pasa los 8 `@example` DST pinneados de `test_ticks_server_tz_property.py`), no por
  razonamiento nuevo sobre offsets. El coste O(n) del fallback se paga solo en el chunk con
  transición, preservando la aceleración ~47x en el resto de chunks del año.
- **R97** (NO DEBE). Ningún camino de conversión de `iter_ticks` (ni el vectorizado de R95 ni el
  fallback de R96) DEBE usar `DataFrame.iterrows()` — el patrón que motiva el issue desaparece por
  completo del módulo (`rg -n "iterrows" src/genesis/backtest/ticks.py` DEBE retornar 0
  coincidencias). La iteración fila a fila del fallback de R96 DEBE usar un mecanismo alternativo
  (p. ej. `itertuples()`, `zip` sobre columnas ya extraídas) que siga invocando `_to_utc` por cada
  valor crudo; la forma exacta de esa iteración queda a `design.md`.
- **R98** (NO DEBE). Ningún camino de conversión de `iter_ticks` DEBE invocar
  `pandas.Series.dt.tz_localize` con los parámetros `ambiguous=` o `nonexistent=` distintos de sus
  defaults fail-fast (`"raise"`) para resolver disambiguación de horas ambiguas/inexistentes — la
  lógica de disambiguación es exclusivamente la de `_to_utc`/`zoneinfo` (`fold=0` implícito, PEP
  495), nunca delegada a las opciones de pandas (ninguna combinación de `ambiguous=`/`nonexistent=`
  reproduce la regla "siempre offset pre-transición, nunca desplaza el wall-clock" que aplica
  `fold=0` de forma uniforme a ambos casos).
- **R99** (NO DEBE). `_to_utc` (copia local, Rg-9) NO se modifica en este Change: se reutiliza tal
  cual como fallback per-chunk (R96) y sigue siendo la única fuente de verdad de la semántica de
  reinterpretación de zona horaria escalar (zoneinfo, nunca offset fijo, R28/R40).
- **R100** (DEBE). La construcción de `TickRow` en el camino vectorizado (R95) DEBE producir, para
  cada fila, los mismos 4 campos (`timestamp_utc`, `bid`, `ask`, `last`) con los mismos valores que
  produciría hoy el bucle escalar sobre el mismo frame — sin cambiar el dataclass `TickRow` (mismos
  4 campos, `frozen=True, slots=True`, R120).
- **R101** (DEBE). Tras procesar todos los chunks candidatos (vectorizados y/o escalares según
  R95/R96), `iter_ticks` DEBE seguir filtrando el conjunto combinado a la ventana UTC objetivo
  `[window.start, window.end)` de `trading_day` (R65, sin cambios) y ordenando por `timestamp_utc`
  ascendente antes de emitir (invariante existente). El `sort()` explícito se conserva
  incondicionalmente como red de seguridad salvo que `design.md` demuestre que es no-op sin impacto
  medible (decisión residual #6, §3).
- **R102** (DEBE). Con `profile.server_tz == "UTC"`, el comportamiento observable de `iter_ticks`
  (valores de `TickRow.timestamp_utc` emitidos) DEBE seguir siendo idéntico al actual (extiende
  R71): con offset 0 en ambos extremos, `_has_dst_transition` (R94) siempre retorna `False` —
  la ruta vectorizada (R95) se toma siempre, nunca se activa el fallback (R96) — invarianza de
  regresión también en la ruta acelerada.

### 4.2. `src/genesis/backtest/ticks.py` — indexado con `bisect` de las ventanas por evento

**Requisitos**:

- **R103** (DEBE). `ticks.py` DEBE definir un helper privado compartido `_bisect_window_bounds(
  day_ticks: Sequence[TickRow], bar_timestamp: datetime) -> tuple[int, int]` que retorne
  `(start_idx, end_idx)` tal que `day_ticks[start_idx:end_idx]` sea exactamente el subconjunto de
  `day_ticks` en la ventana semiabierta `(bar_timestamp - 60s, bar_timestamp]`, calculado vía dos
  llamadas a `bisect.bisect_right` sobre `day_ticks` (asumido ya ordenado ascendente por
  `timestamp_utc`, invariante de R65/R101) usando `key=attrgetter("timestamp_utc")` en ambos
  límites. NO DEBE reordenar `day_ticks` ni asumir nada distinto de que ya viene ordenado.
- **R104** (DEBE). `has_sufficient_tick_coverage` DEBE derivar la condición (b) (al menos un tick en
  la ventana de cobertura) evaluando `start_idx < end_idx` sobre el resultado de
  `_bisect_window_bounds(day_ticks, bar.timestamp_utc)` (R103) — NUNCA reimplementar
  independientemente el cálculo de límites ni escanear linealmente `day_ticks` con `any(...)`. La
  condición (a) (existencia de al menos un chunk candidato, R69) no cambia.
- **R105** (DEBE). `ticks_in_bar_window` DEBE retornar `day_ticks[start_idx:end_idx]` derivado de
  `_bisect_window_bounds(day_ticks, bar.timestamp_utc)` (R103) — NUNCA reimplementar
  independientemente el cálculo de límites. NO DEBE aplicar ningún `sorted()` adicional sobre el
  resultado: una slice de una secuencia ya ordenada ascendente está ya ordenada (el `sorted()`
  redundante actual desaparece).
- **R106** (NO DEBE). Ni `has_sufficient_tick_coverage` ni `ticks_in_bar_window` cambian de firma
  pública (mismos parámetros, mismo tipo de retorno) respecto al código actual — extiende R68/R72:
  ningún llamador (`simulator.py`, `signal_diagnostic.py`) requiere ningún cambio de código.
- **R107** (DEBE). El resultado de `has_sufficient_tick_coverage`/`ticks_in_bar_window` tras adoptar
  `_bisect_window_bounds` (R103-R105) DEBE ser bit-idéntico, para cualquier `day_ticks` (ordenado
  ascendente) y `bar.timestamp_utc`, al que produce hoy el escaneo lineal + `_tick_in_bar_window`
  (criterio único de borde `(T-60s, T]`, RI-G5/ADR-G8) — el boundary no puede divergir entre ambas
  funciones ni con el motor de fills de `simulator.py` (que consume `ticks_in_bar_window` sin
  conocer `bisect` internamente, R109). Si `_tick_in_bar_window` deja de tener llamadores en el
  camino caliente de ambas funciones tras este Change, su conservación como referencia documental
  del criterio o su eliminación queda a discreción de `design.md` — no afecta ningún comportamiento
  observable.

### 4.3. Condición de activación del fallback per-chunk

**Requisitos**:

- **R108** (NO DEBE). El fallback per-chunk al bucle escalar (R96) DEBE activarse **únicamente**
  por la detección de transición DST (`_has_dst_transition`, R94) — NO DEBE combinarse con, ni
  sustituirse por, ningún criterio adicional de tamaño mínimo de frame (p. ej. "si el chunk tiene
  menos de N filas, no vectorizar"): un chunk pequeño sin transición DST no tiene riesgo de
  correctitud y DEBE vectorizarse igual que uno grande; un chunk grande con transición SÍ tiene el
  riesgo y DEBE usar el fallback igual que uno pequeño, sin importar su tamaño (formaliza la
  decisión residual #2, §3, y la Alternativa descartada #8 de `proposal.md`).

### 4.4. Consumidores — sin cambios de comportamiento ni de firma

**Requisitos**:

- **R109** (NO DEBE). `src/genesis/backtest/simulator.py` NO DEBE modificarse en este Change:
  `Simulator._day_ticks_for` (`simulator.py:288-296`), `_process_bar` (`298-324`),
  `_manage_open_positions` (`326-332`), `_resolve_fill`/`_resolve_fill_from_ticks`/
  `_resolve_entry_fill` (`128-181`), `_open_position` (`495-543`), `_force_close_all_positions`
  (`450-463`) siguen invocando `iter_ticks`/`has_sufficient_tick_coverage`/`ticks_in_bar_window`
  exactamente igual — extiende R73-R75 (Change #21): se benefician de la aceleración sin ningún
  cambio de código ni de firma en este módulo.
- **R110** (NO DEBE). `src/genesis/validation/signal_diagnostic.py` NO DEBE modificarse en este
  Change: `estimate_roundtrip_cost` (`96-136`)/`run_signal_diagnostic` (`154-209`) siguen invocando
  `iter_ticks`/`has_sufficient_tick_coverage`/`ticks_in_bar_window` exactamente igual;
  `CONFIG_VERSION` (línea 41) permanece `"genesis-validation-d/2"` — NO se incrementa: los valores
  calculados (`roundtrip_cost`, `excluded_events_no_tick_coverage`) no cambian, solo el tiempo de
  cómputo — a diferencia de #21, que sí bumpeó de `-d/1` a `-d/2` porque los valores calculados
  cambiaban.
- **R111** (NO DEBE). `src/genesis/backtest/costs.py::spread_for` (`33-54`) NO DEBE modificarse:
  sigue consumiendo el `Sequence[TickRow] | None` ya filtrado que le pasa su llamador
  (`_open_position`), sin invocar directamente `has_sufficient_tick_coverage`/`ticks_in_bar_window`
  — consumidor indirecto, sin cambios.

### 4.5. Testing (`tests/backtest/`, `scripts/`)

**Requisitos**:

- **R112** (DEBE). `tests/backtest/test_ticks_server_tz_property.py` (property test existente, 1000
  ejemplos + 8 `@example` DST pinneados) DEBE ejecutarse **sin ninguna modificación** contra la
  nueva implementación y pasar en verde — es el oráculo principal de equivalencia bit a bit entre la
  ruta híbrida vectorizada/escalar y la semántica `_to_utc` original.
- **R113** (DEBE). `tests/backtest/test_ticks_vectorization_differential.py` (archivo nuevo) DEBE
  incluir un test de propiedad `hypothesis` (`max_examples>=200`, marcado `pytest.mark.unit`,
  análogo en estructura a `test_ticks_server_tz_property.py`) que, para un chunk de ticks arbitrario
  (múltiples timestamps por chunk, `server_tz` arbitrario entre `{"Europe/Athens",
  "America/New_York"}`), compare la secuencia de `TickRow` que emite `iter_ticks` (ruta híbrida)
  contra la secuencia que produciría invocar `_to_utc` fila a fila (bucle escalar de referencia,
  sin optimizar) sobre el mismo frame, y verifique que son idénticas elemento a elemento (mismo
  orden, mismos 4 campos, mismo `timestamp_utc`). DEBE incluir, como mínimo, los siguientes
  `@example` pinneados (mismas fechas fijadas en la tabla de §3, decisión residual #5):
  - Un día sin transición DST (`_TRADING_DAY = date(2024, 1, 2)`, mismo valor que
    `tests/backtest/test_ticks.py`).
  - El día de spring-forward de cada huso: `2024-03-31` (Europe/Athens), `2024-03-10`
    (America/New_York) — mismas fechas que los `@example` pinneados de
    `test_ticks_server_tz_property.py`.
  - El día de fall-back de cada huso: `2024-10-27` (Europe/Athens), `2024-11-03`
    (America/New_York) — ídem.
  - El caso multi-chunk con spillover D/D+1 (`server_date` `2026-06-26`→`2026-06-27`,
    `server_tz="Europe/Athens"`, mismas fechas del golden R81 de Change #21).
  DEBE reutilizar `build_server_local_tick_chunk` (`tests/backtest/fakes.py`, sin modificarlo).
- **R114** (DEBE). `tests/backtest/` DEBE incluir un test (unitario o de propiedad `hypothesis`,
  `max_examples>=200`) que, para una secuencia arbitraria de `day_ticks` ordenada ascendente y un
  `bar_timestamp` arbitrario, verifique que `_bisect_window_bounds(day_ticks, bar_timestamp)` (R103)
  produce el mismo `(start_idx, end_idx)` — y por tanto el mismo resultado observable de
  `has_sufficient_tick_coverage`/`ticks_in_bar_window` — que el filtrado lineal de referencia
  (`[tick for tick in day_ticks if _tick_in_bar_window(tick.timestamp_utc, bar_timestamp)]`),
  incluyendo explícitamente los casos borde: `day_ticks` vacío, ningún tick en la ventana, todos los
  ticks en la ventana, y ticks exactamente en los bordes `bar_timestamp - 60s` (excluido) y
  `bar_timestamp` (incluido).
- **R115** (DEBE). El benchmark antes/después DEBE materializarse como un script versionado en
  `scripts/bench_iter_ticks.py`, invocable vía `uv run python scripts/bench_iter_ticks.py`, que mida
  de forma reproducible (misma entrada, mismo resultado relativo en repeticiones) el mismo escenario
  de referencia usado como evidencia del issue (un día de ~256k ticks + al menos un símbolo completo
  de la corrida D) y reporte el tiempo antes/después y el factor de mejora. NO forma parte de la
  suite pytest ni depende de `pytest-benchmark` (sin dependencia dev nueva, R123). El formato exacto
  de salida (texto/JSON) y los argumentos CLI quedan a discreción de `design.md`.
- **R116** (DEBE). Como evidencia de aceptación de cierre de este Change (no parte de la suite
  pytest versionada), DEBE re-ejecutarse `genesis-validate diagnose --candidate A --firm ftmo
  --symbol US500 ...` sobre el dataset completo de la corrida D y diferenciarse el `report.json`
  resultante contra `out/signal_diagnostic/US500/report.json` (oráculo, 173 sesiones,
  `config_version=genesis-validation-d/2`, ya post-fix de #21), confirmando igualdad byte a byte
  salvo el campo `git_commit`.
- **R117** (DEBE). Los 6 archivos de test de regresión existentes (`tests/backtest/test_ticks.py`,
  `tests/backtest/test_ticks_server_tz_property.py`, `tests/backtest/test_forward_only_property.py`,
  `tests/backtest/test_simulator_fills.py`, `tests/backtest/test_public_api.py`,
  `tests/validation/test_signal_diagnostic.py`) NO DEBEN modificarse (`git diff --stat` vacío sobre
  los 6, a diferencia de #21 que sí los adaptó a la nueva firma) y DEBEN seguir en verde contra la
  nueva implementación.
- **R118** (DEBE). `uv run mise run ci` (ruff+bandit+vulture+deptry+ty+test) DEBE pasar en verde
  sobre `src/genesis/backtest/ticks.py`, `scripts/bench_iter_ticks.py` y todos los tests afectados
  (existentes y nuevos).

---

## 5. Invariantes transversales

- **R119** (NO DEBE). Ninguna firma pública de `ticks.py` cambia en este Change:
  `iter_ticks(store, symbol, trading_day, profile) -> Iterator[TickRow]`,
  `has_sufficient_tick_coverage(store, symbol, bar, day_ticks, profile) -> bool`,
  `ticks_in_bar_window(bar, day_ticks) -> list[TickRow]` conservan exactamente sus parámetros y
  tipos de retorno actuales (extiende R64/R68/R72 sin reabrirlos; verificable por diff de línea, no
  solo de nombre).
- **R120** (NO DEBE). `TickRow` no se modifica: mismo dataclass `frozen=True, slots=True`, mismos 4
  campos (`timestamp_utc`, `bid`, `ask`, `last`).
- **R121** (NO DEBE). Ningún archivo de `src/genesis/data/` ni de `src/genesis/strategy/` DEBE
  modificarse en este Change (extiende R57/R86: `git diff --stat -- src/genesis/data
  src/genesis/strategy` vacío).
- **R122** (NO DEBE). Este Change NO DEBE añadir ningún método nuevo a `RawParquetStore`/
  `mt5_export.py` (extiende R70): `iter_ticks` sigue consumiendo exclusivamente `has_chunk`/
  `read_chunk` ya públicos.
- **R123** (NO DEBE). Este Change NO DEBE añadir ninguna dependencia de runtime ni de dev nueva a
  `pyproject.toml` (`[project.dependencies]`/grupos dev) — `bisect` es stdlib; sin
  `pytest-benchmark` (extiende R89).
- **R124** (NO DEBE). Este Change NO DEBE relajar ni modificar ningún umbral o criterio de gate
  (§2.2.1 ARCHIVE/CONTINUE, gates G/C/P/T de §7 del spec) — extiende R88: es un fix de rendimiento
  puro, el veredicto mecánico no cambia para ningún dataset ya evaluado (R116 lo verifica
  empíricamente).
- **R125** (NO DEBE). Este Change NO DEBE modificar el esquema (campos) de `SignalDiagnosticReport`
  ni de `ArtifactMetadata` (extiende R90) ni el `CONFIG_VERSION` de `signal_diagnostic.py`
  (permanece `"genesis-validation-d/2"`, R110).
- **R126** (DEBE). `uv run mise run ci` DEBE pasar en verde sobre todo el repositorio tras este
  Change (extiende R85/R91/R118).

---

## 6. Manejo de errores (resumen normativo — sin cambios respecto a `.pulse/specs/backtest/spec.md` §6)

Este Change no introduce ninguna excepción de dominio nueva. La tabla de excepciones de
`.pulse/specs/backtest/spec.md` §6 sigue vigente sin modificaciones:

| Excepción | Módulo | Disparador (tras este Change) | Efecto |
|---|---|---|---|
| `BacktestConfigError` | `genesis.backtest.errors` | Al menos un chunk candidato de `_candidate_server_dates` existe pero su esquema es inválido (R93, extiende R67 sin cambios) | Aborta el run (sin cambios) |
| (sin excepción) | `genesis.backtest.ticks` | Ningún chunk candidato existe (R66, sin cambios) | `iter_ticks` retorna secuencia vacía; `has_sufficient_tick_coverage` retorna `False` (R69, sin cambios) |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "def _has_dst_transition" src/genesis/backtest/ticks.py
       y rg -n "def _bisect_window_bounds" src/genesis/backtest/ticks.py
ENTONCES ambas retornan >=1 coincidencia (R94, R103: los dos helpers nuevos existen con el nombre
         normativo fijado)
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "iterrows" src/genesis/backtest/ticks.py
ENTONCES retorna 0 coincidencias (R97: el patrón que motiva el issue desaparece del módulo, incluso
         en el camino de fallback)
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "tz_localize\([^)]*ambiguous" src/genesis/backtest/ticks.py
       y rg -n "tz_localize\([^)]*nonexistent" src/genesis/backtest/ticks.py
ENTONCES ambas retornan 0 coincidencias (R98: ningún camino delega la disambiguación DST a pandas)
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "bisect" src/genesis/backtest/ticks.py
ENTONCES retorna >=1 coincidencia (import + uso; adopción confirmada del mecanismo elegido, R103)
```

```
DADO   el archivo src/genesis/backtest/ticks.py
CUANDO rg -n "def iter_ticks" src/genesis/backtest/ticks.py
       y rg -n "def has_sufficient_tick_coverage" src/genesis/backtest/ticks.py
       y rg -n "def ticks_in_bar_window" src/genesis/backtest/ticks.py
       y rg -n "class TickRow" -A 6 src/genesis/backtest/ticks.py
ENTONCES las 3 firmas son idénticas (línea a línea) a las actuales, y TickRow muestra los mismos 4
         campos (R119, R120)
```

```
DADO   un chunk sintético de un día calendario de servidor sin transición DST (offsets iguales en
       ambos extremos del frame)
CUANDO se invoca iter_ticks(store, symbol, trading_day, profile) con ese chunk
ENTONCES emite exactamente la misma secuencia de TickRow.timestamp_utc que invocar _to_utc fila a
         fila sobre el mismo frame (R95, R100 — caso normal, ruta vectorizada)
```

```
DADO   un chunk sintético que cruza el spring-forward de Europe/Athens (2024-03-31) o
       America/New_York (2024-03-10)
CUANDO se invoca iter_ticks sobre ese chunk
ENTONCES _has_dst_transition detecta la transición, se activa el fallback escalar (R96), y la
         secuencia de TickRow.timestamp_utc emitida es idéntica a invocar _to_utc fila a fila
         (R113, test diferencial)
```

```
DADO   un chunk sintético que cruza el fall-back de Europe/Athens (2024-10-27) o America/New_York
       (2024-11-03)
CUANDO se invoca iter_ticks sobre ese chunk
ENTONCES _has_dst_transition detecta la transición, se activa el fallback escalar (R96), y la
         secuencia de TickRow.timestamp_utc emitida coincide con _to_utc fila a fila, incluyendo el
         mismo tratamiento fold=0 de la hora ambigua que ya acepta test_ticks_server_tz_property.py
         (R113)
```

```
DADO   dos chunks de servidor adyacentes 2026-06-26/2026-06-27 (Europe/Athens, mismo patrón que el
       golden R81 de Change #21)
CUANDO se invoca iter_ticks sobre trading_day=2026-06-26
ENTONCES el resultado fusionado y ordenado es idéntico al que produce _to_utc fila a fila sobre
         ambos chunks (R113, caso multi-chunk con spillover)
```

```
DADO   una secuencia arbitraria day_ticks (ordenada ascendente) y un bar_timestamp arbitrario,
       incluyendo los casos borde day_ticks vacío y ticks exactamente en T-60s/T
CUANDO se comparan _bisect_window_bounds(day_ticks, bar_timestamp) contra el filtrado lineal de
       referencia (_tick_in_bar_window aplicado elemento a elemento)
ENTONCES ambos producen el mismo subconjunto/booleano observable (R107, R114)
```

```
DADO   el property test existente tests/backtest/test_ticks_server_tz_property.py (sin modificar)
CUANDO uv run pytest tests/backtest/test_ticks_server_tz_property.py -v
ENTONCES pasa en verde con los 1000 ejemplos y los 8 @example DST pinneados contra la nueva
         implementación (R112, oráculo principal de equivalencia)
```

```
DADO   los 6 archivos de test de regresión (test_ticks.py, test_ticks_server_tz_property.py,
       test_forward_only_property.py, test_simulator_fills.py, test_public_api.py,
       test_signal_diagnostic.py)
CUANDO git diff --stat -- tests/backtest/test_ticks.py tests/backtest/test_ticks_server_tz_property.py
       tests/backtest/test_forward_only_property.py tests/backtest/test_simulator_fills.py
       tests/backtest/test_public_api.py tests/validation/test_signal_diagnostic.py
       y uv run pytest <esos 6 archivos> -v
ENTONCES el diff está vacío (ninguno de los 6 se modifica) y la suite pasa en verde (R117)
```

```
DADO   el dataset completo de la corrida D (US500, 173 sesiones)
CUANDO se re-ejecuta genesis-validate diagnose --candidate A --firm ftmo --symbol US500 ... y se
       diferencia el report.json resultante contra out/signal_diagnostic/US500/report.json
       (jq 'del(.data_metadata.git_commit)' <ambos> | diff)
ENTONCES no hay diferencias (R116, criterio de éxito (a) del proposal)
```

```
DADO   el script scripts/bench_iter_ticks.py
CUANDO uv run python scripts/bench_iter_ticks.py sobre el escenario de referencia (día de ~256k
       ticks + símbolo completo de la corrida D)
ENTONCES reporta una mejora de ~30-50x documentada, reproducible en repeticiones (R115, criterio de
         éxito (c) del proposal)
```

```
DADO   el archivo src/genesis/validation/signal_diagnostic.py
CUANDO rg -n "CONFIG_VERSION" src/genesis/validation/signal_diagnostic.py
ENTONCES sigue mostrando "genesis-validation-d/2" (R110, R125: sin bump, los valores calculados no
         cambian)
```

```
DADO   el repositorio tras completar este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy pyproject.toml uv.lock
       y git diff --stat -- src/genesis/backtest/simulator.py src/genesis/backtest/costs.py
ENTONCES todos vacíos (R121, R123, R109, R111: capas cerradas y consumidores intactos, sin
         dependencias nuevas)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0, R118, R126)
```

---

## 8. Riesgos

Riesgos heredados de Change #21 (Rg-8, Rg-9, Rg-10, Rg-11 de `.pulse/specs/backtest/spec.md`, no
reabiertos por este documento): Rg-8 (discrepancia `_day_window` UTC-literal vs. `_trading_day()`)
y Rg-10 (límite de fechas candidatas para husos DST no verificados exhaustivamente) permanecen fuera
de alcance sin cambios; Rg-9 (sincronía obligatoria `ticks.py::_to_utc` ↔ `store.py::_to_utc`) se
vuelve **más relevante** en este Change porque `_to_utc` pasa a ejecutarse condicionalmente (solo en
el chunk con transición, R96) en vez de siempre — un futuro cambio que rompa la sincronía sería
detectado igual por el property test (R112), pero solo si ese test ejercita chunks con transición
(ya lo hace, 8 `@example` pinneados); Rg-11 (artefactos derivados con el bug de #21 activo) ya fue
mitigado por el cierre de #21 y no aplica a este Change.

Riesgos nuevos de este Change:

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-12 | El mecanismo de `_has_dst_transition` (R94) asume que, dentro de un chunk (~24-25h, un día calendario de servidor), a lo sumo hay **una** transición DST — verdadero para todos los husos IANA reales, pero no verificado exhaustivamente contra la base de datos completa `tz`. | Un huso exótico no soportado hoy con 2 transiciones DST en <25h (no existe en la práctica) haría que el muestreo de solo los 2 extremos del chunk no detecte una transición intermedia. | Acotado a los husos reales usados por los perfiles y tests (`Europe/Athens`, `America/New_York`, `Australia/Sydney`); ninguno tiene 2 transiciones en un lapso de 25h. Documentado como supuesto explícito no verificado para husos no soportados hoy — mismo patrón que Rg-10 heredado de #21. |
| Rg-13 | El benchmark de R115 es sensible al hardware/carga del entorno de ejecución (no determinista bit a bit como los tests); el factor "~30-50x" es una guía de orden de magnitud, no un umbral exacto que bloquee CI. | Una máquina más lenta/rápida o con carga concurrente podría reportar un factor distinto al medido en el issue, sin que eso indique una regresión real. | Documentado explícitamente como evidencia no-pytest (no bloquea `mise run ci`, R118/R126) — mismo patrón que R84 de #21 (re-corrida empírica documentada, no un test versionado con umbral duro). |
| Rg-14 | Si el chunk que activa el fallback per-chunk (R96, transición DST detectada) coincide con un día de alto volumen de ticks (p. ej. ~256k ticks el mismo día que una transición DST), el coste O(n) del fallback se paga igual ese día puntual, sin la aceleración ~47x. | Un día concreto del año (el de la transición) no se beneficia de la vectorización, aunque sea un día de alto volumen. | Comportamiento esperado y aceptado explícitamente: es el trade-off de activar el fallback por transición detectada en vez de por tamaño de frame (R108, Alternativa descartada #8 de `proposal.md`) — ~2 días/año por huso, no un defecto. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Si medir la materialización de `TickRow` como experimento aislado (además del benchmark de R115)
  amerita un Change futuro, en caso de que el benchmark muestre que instanciar N dataclasses es
  ahora el cuello de botella dominante tras vectorizar la conversión de zona horaria (decisión
  residual #4, §3; Pregunta 5 de `idea.md`).
- Si el `sort()` final de `iter_ticks` (R101) puede demostrarse no-op cuando la construcción en
  bloque preserva el orden de `_normalize_frame` (decisión residual #6, §3) — diferido a
  `design.md`; no bloquea el criterio de éxito de este Change en ningún sentido observable.
- Orden exacto de los parámetros (posicional vs. keyword-only) de `_has_dst_transition`/
  `_bisect_window_bounds` (R94/R103) — este documento fija el comportamiento observable y los
  nombres, no la sintaxis exacta de la firma; `design.md` la resuelve respetando el patrón ya usado
  por `_candidate_server_dates(window, server_tz)` (Change #21).
- Formato exacto de salida (texto/JSON) y argumentos CLI de `scripts/bench_iter_ticks.py` (R115) —
  diferido a `design.md`.
- Si `_tick_in_bar_window` se conserva en el módulo como referencia documental del criterio de borde
  o se elimina tras dejar de tener llamadores en el camino caliente de `has_sufficient_tick_coverage`/
  `ticks_in_bar_window` (R107) — diferido a `design.md`; no afecta ningún comportamiento observable.
- Si Rg-8/Rg-10 (heredados de #21) ameritan convertirse en un Change futuro explícito, o permanecer
  documentados indefinidamente — no es responsabilidad de este Change decidirlo.

---

## 10. Referencias

- Issue GitHub #24 — bbenja11/genesis (https://github.com/bbenja11/genesis/issues/24).
- `idea.md`/`proposal.md` de este Change (fases explore/propose) — problema medido, contexto
  observado, mecanismo híbrido DST, hipótesis A/B, 8 alternativas descartadas, 6 decisiones
  residuales y sus respuestas, diseño propuesto por módulo, alcance de testing.
- `.pulse/specs/backtest/spec.md` — R1-R61 (Change #6/G, contrato original de `iter_ticks`/
  cobertura), R62-R91 (Change #21: `_to_utc`/`_candidate_server_dates`/multi-chunk/condición OR/
  propagación `FirmProfile`), R57/R86 (capas cerradas), §6 (tabla de manejo de errores, sin
  cambios), Rg-8/Rg-9/Rg-10/Rg-11 (riesgos heredados).
- `src/genesis/backtest/ticks.py:1-198` — módulo completo a modificar internamente (`iter_ticks:
  97-146`, bucle `iterrows`:133-143, `_tick_in_bar_window:149-156`,
  `has_sufficient_tick_coverage:159-186`, `ticks_in_bar_window:189-198`, `_to_utc:44-60`,
  `_candidate_server_dates:63-77`, sin cambios en estas dos últimas).
- `src/genesis/backtest/simulator.py:288-296` (`_day_ticks_for`), `298-324` (`_process_bar`),
  `326-332` (`_manage_open_positions`), `128-181` (`_resolve_fill_from_ticks`/`_resolve_fill`/
  `_resolve_entry_fill`), `495-543` (`_open_position`), `450-463` (`_force_close_all_positions`) —
  consumidores confirmados, sin cambios (R109).
- `src/genesis/validation/signal_diagnostic.py:41` (`CONFIG_VERSION`), `96-136`
  (`estimate_roundtrip_cost`), `154-209` (`run_signal_diagnostic`) — consumidor confirmado, sin
  cambios (R110).
- `src/genesis/backtest/costs.py:33-54` (`spread_for`) — consumidor indirecto de `TickRow`, sin
  cambios (R111).
- `src/genesis/data/store.py:41-56` (`_to_utc`, patrón normativo con el que la copia de `ticks.py`
  debe permanecer sincronizada, Rg-9), `88` (`iter_bars`, mismo patrón `iterrows()` en capa 1,
  fuera de alcance de este Change — R121).
- `src/genesis/data/mt5_export.py:259-264` (`_normalize_frame`, confirma orden ascendente por
  `timestamp` al escribir — base de la O(1) de R94), `303-308` (`read_chunk`), `310-340`
  (`write_chunk`, confirma `timestamp` ya tz-aware UTC-mal-etiquetado tras roundtrip Parquet).
- `src/genesis/data/profile.py:31-49` (`FirmProfile`, campo `server_tz: str`), `64-94`
  (`load_firm_profile`, default `profiles/the5ers.json`, `server_tz="America/New_York"`).
- `tests/backtest/test_ticks.py` (7 tests, sin modificar), `tests/backtest/test_ticks_server_tz_property.py`
  (property test, 1000 ejemplos, 8 `@example` DST pinneados: `Europe/Athens` spring-forward
  2024-03-31/fall-back 2024-10-27, `America/New_York` spring-forward 2024-03-10/fall-back
  2024-11-03, `Australia/Sydney` spring-forward 2024-10-05/fall-back 2024-04-06, sin modificar),
  `tests/backtest/test_forward_only_property.py` (2 property tests, sin modificar),
  `tests/backtest/test_simulator_fills.py` (8 casos golden, sin modificar),
  `tests/backtest/test_public_api.py` (`__all__` curado, sin modificar),
  `tests/validation/test_signal_diagnostic.py` (3 tests, sin modificar),
  `tests/backtest/fakes.py` (`build_tick_chunk`, `build_server_local_tick_chunk`, sin modificar).
- `.pulse/changes/archive/6-g-feat-backtest-simulador-equity-intrad-a-fills-por-ticks-cierre/design.md`
  — ADR-G6 (`iter_ticks` propio), ADR-G8 (ventana `(T-60s,T]`), RI-G5 (criterio compartido).
- `.pulse/changes/archive/21-fix-backtest-iter-ticks-emite-timestamps-del-reloj-del-servidor/` —
  `idea.md`/`proposal.md`/`spec.md`/`design.md`/`tasks.md` completos (Change inmediatamente
  anterior sobre el mismo archivo; ADR-21-1 copia local de `_to_utc`, ADR-21-7 patrón
  `build_server_local_tick_chunk`, Rg-9 sincronía, R79-R85 patrón de testing DST).
- `pyproject.toml` — `requires-python=">=3.14"` (soporte nativo de `key=` en
  `bisect.bisect_right`), `pandas>=3.0.3`, sin `pytest-benchmark`; `[tool.pytest.ini_options]`
  marcador `slow` ya definido; `mise.toml` `[tasks.ci]` (lint+ty+test).
- `out/run_d/issue_draft_perf_iter_ticks.md` — cuerpo íntegro del issue #24.
- `out/signal_diagnostic/US500/report.json` — oráculo de bit-identidad (corrida D completa, 173
  sesiones, `config_version=genesis-validation-d/2`, ya post-fix de #21).
- Documentación pandas 3.0.4 (`tz_localize`, opciones `ambiguous`/`nonexistent`, defaults `"raise"`
  y semántica de `shift_forward`/`shift_backward`/`infer` — consultada vía Context7 en la fase
  propose para fundamentar R98).
- `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md` §2.2.1 (diagnóstico de señal desnuda),
  §9 (testing EDD/TDD), §11 (gobernanza SDD).
- `.agents/rules/architecture-conventions.md`, `.agents/rules/eval-tdd-conventions.md`,
  `.agents/rules/tooling-conventions.md` — convenciones de proceso SDD.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, flujo SDD, convenciones de commits/testing.

<!-- change:97-salida-por-trailing-estructural-chandelier-en-la-capa-3 -->
# Specification — el Chandelier como política de capa 3, con ancla desde la apertura

Change #97 (Issue #97). Dominio `backtest`. Contrato de entrada: `idea.md` + `proposal.md` de este
Change. Este documento fija los requisitos normativos (R) y los criterios de aceptación
ejecutables (A). Las decisiones de variante de implementación son de `design.md`.

## Objetivo

Que la capa 3 pueda representar la salida exigida por el método (Chandelier `(N = 22, k = 3,0)`
monótono), de modo que una corrida de validación evalúe la estrategia del operador tal como está
declarada. La **regla** del trailing es de capa 3 e igual para todos los candidatos; lo único que la
intención comunica es si su setup tiene objetivo fijo o no.

## Alcance

### IN

- La regla del trailing en la capa 3: una sola, obligatoria, no parametrizable por el candidato.
- Estado del máximo (o mínimo) por **posición**, con la ventana anclada en la apertura.
- Actualización del stop efectivo dentro del bucle de barra, antes de resolver el fill.
- Registro de los movimientos del stop en el `Ledger`.
- Un motor de ATR y un motor de máximo rodante compartidos en `strategy/common/`.
- Tests de propiedad, golden e integración.

### OUT (YAGNI explícito)

- Cierres parciales y objetivos fijos de cualquier tipo.
- Tenencia interdiaria: el cierre forzado de sesión sigue vigente y sin cambios.
- Calibrar `(N, k)`, o exponerlos como eje de grilla.
- Trailing por régimen (el Playbook ceñido a `2,0 × ATR` para shock precautorio queda para otro
  Change; acá `k` es una constante).
- Corregir el gate de fricción inerte (`spread` nunca emitido) ni el conteo literal de ensayos
  (`_N_TRIALS_*`). Ambos anotados en `idea.md` y ajenos a este Change.

## Requisitos funcionales

**R1 · La política es de capa 3 y sus constantes viven en el perfil de riesgo.** Ningún candidato
declara, parametriza ni puede sustituir la salida. Las dos constantes del Chandelier viajan juntas
como par: fijar solo el múltiplo deja el nivel indeterminado.

**R2 · La fórmula.** Para una posición larga, con `H` el conjunto de máximos de las **velas H1
cerradas desde la apertura** de la posición, acotado a las últimas `N`:

`nivel = max(H) - k * ATR_14`

Para una posición corta, con `L` los mínimos análogos: `nivel = min(L) + k * ATR_14`.

**R2bis · La geometría es horaria y la ejecución es de minuto.** El simulador itera velas **M1**
(`strategy/contract.py:8-10`), y el par `(N, k)` está calibrado sobre **H1**. El ATR y el extremo
rodante se alimentan **solo cuando se cierra una vela H1 agregada**; el nivel se aplica y el fill se
resuelve con resolución M1. Alimentar el estado con la barra M1 suelta daría un ATR de 14 minutos y
una ventana de 22 minutos: no es el Chandelier del método, y ningún criterio de aceptación de una
versión anterior de este documento lo habría detectado.

**R2ter · El agregador se alimenta con TODAS las barras M1, no solo las de sesión.** Es la
convención que ya rige para el ATR por temporalidad agregada: el motor del candidato A empuja cada
barra al agregador sin filtrar (`candidate_a/smc/engine.py:169`), y el ATR se actualiza desde la
vela agregada.

**Filtrar por sesión rompería el agregador.** `BarAggregator.push` emite una vela H1 cuando
`minute % 60 == 59` y **no resetea el acumulador en ningún otro caso**
(`candidate_a/smc/timeframe.py:109-125`). Si se le entregan solo barras en sesión, un cierre de
sesión que no cae en el minuto 59 deja un acumulador abierto que la sesión siguiente **extiende**,
produciendo una vela H1 que cruza la noche y cuyo rango verdadero incluye el salto de apertura. O
sea: filtrar por sesión no evita la contaminación por saltos, la concentra en una sola vela
monstruosa.

Ojo con la comparación que motivó una versión anterior de este requisito: `candidate_b` sí filtra
con `if bar.in_session` (`candidate_b/candidate.py:108-109`), y está bien **para él**, porque su ATR
es M1 y se actualiza barra por barra sin agregación. El ATR del trailing es H1 agregado, así que le
corresponde la convención del candidato A. Y `IncrementalAtr` declara ser «continuo cross-día
(NUNCA reseteado)» (`candidate_a/smc/atr.py:12`), que es coherente con alimentarlo sin filtrar.

**R3 · Monotonía (`ratchet`), en las dos direcciones.** En largos el stop efectivo es
`max(stop_previo, nivel)`; en cortos, `min(stop_previo, nivel)`. El stop **nunca** se mueve en
contra de la posición.

**R4 · El stop inicial es el piso.** El stop efectivo nunca queda peor que el stop inicial que
entregó `risk_levels`. Se deriva de R3 y se declara aparte porque es la ley de riesgo: el
dimensionamiento del lote se calculó con esa distancia, y aflojarla invalidaría el 1 % declarado.

**R5 · Ancla desde la apertura.** La ventana **nunca** incorpora barras anteriores a la apertura de
la posición. Mientras la posición tiene menos de `N` barras cerradas de vida, la ventana es más
corta. Medido sobre 367 señales reales, sin este requisito el `ratchet` adoptaría un nivel derivado
de barras no vividas en el **47 %** de los casos, y en el **4 %** ese nivel caería del lado ganador
de la entrada, produciendo una salida inmediata con una ganancia que nunca ocurrió.

**R6 · Solo barras cerradas hasta `t-1`.** El máximo, el mínimo y el ATR que determinan el stop
aplicable a la barra `t` se calculan **exclusivamente** con barras cerradas hasta `t-1`. El `high`
o el `low` de la barra en curso **no** pueden participar del nivel con el que se resuelve el fill
de esa misma barra.

**R7 · Orden dentro del bucle de barra.** La actualización del stop ocurre en el paso de gestión de
posiciones abiertas, **antes** de resolver el fill de la barra en curso. El cierre forzado de
sesión, el proceso de entradas nuevas y la evaluación de breaches conservan su posición relativa.

**R8 · La posición sigue siendo inmutable.** `OpenPosition` conserva `frozen=True, slots=True`. La
actualización se materializa construyendo una posición nueva y reemplazándola en su lugar dentro
del estado de la cuenta. Ningún consumidor debe poder observar una posición con el stop
desactualizado después de la actualización de la barra.

**R9 · Cada movimiento del stop queda registrado.** El `Ledger` incorpora un tipo de entrada que
identifica la posición, la barra, el stop anterior y el nuevo. Todo fill resuelto contra un stop
movido tiene que ser explicable por el registro.

**R10 · Un solo motor de ATR.** La política consume el motor de ATR compartido; no se agrega una
tercera implementación. El motor promovido conserva su semántica actual (Wilder, continuo, nunca
reseteado) y su contrato de calentamiento.

**R11 · Sin calentamiento no hay trailing, y no hay excepción.** Si el ATR aún no está calentado, el
stop efectivo permanece en el stop inicial. La ausencia de trailing en esa ventana **no** es un
error: es el estado correcto. Levantar una excepción cerraría la corrida por un estado legítimo.

**R12 · Determinismo.** Dos corridas con la misma configuración, el mismo dataset y las mismas
semillas producen exactamente la misma secuencia de movimientos de stop.

**R13 · La política es obligatoria.** Un candidato sin la salida no es evaluable. Hoy el único
ejecutable es B.

**R14 · La identidad de posición es única entre ventanas.** Cada ventana del WFA corre su propia
instancia de `Simulator` (`validation/wfa.py:251`) y los ledgers se cosen después en
`_stitch_oos_ledgers` (`validation/wfa.py:401-426`). Un
contador local a la instancia produciría identificadores duplicados en el ledger cosido, así que la
identidad incorpora la procedencia de la corrida y la ventana.

**R15 · Los parámetros del trailing entran en el hash del perfil de riesgo.** Si `trailing_lookback`
y `trailing_atr_mult` no participan de `risk_profile_hash()` (`backtest/risk_profile.py:73`), dos
perfiles distintos comparten identidad, contaminando la `RunProvenance` (`backtest/ledger.py:83`) y
el `trial_id` del ledger de ensayos, que la consume (`validation/trial_ledger.py:41`).

Ojo con **cómo** hay que hacerlo: `risk_profile_hash()` no serializa el `dataclass`, arma un
diccionario canónico **campo por campo a mano** (`backtest/risk_profile.py:80-88`). Sumar un campo
al perfil y olvidarlo ahí no rompe nada visible, que es justo el modo de fallo que este requisito
existe para impedir. Lo verifica A23.

**R16 · La actualización no puede corromper la lista de posiciones.** El paso de gestión no escribe
por índice en una lista que `_close_position` acorta en la misma pasada (`simulator.py:619`).

**R17 · La remoción de una posición cerrada es del llamador, no de la liquidación.** Liquidar
(costos, dinero, `Ledger`) y remover de `AccountState.open_positions` son responsabilidades
separadas. Pasarle a la liquidación la posición **actualizada** mientras la lista todavía contiene
la anterior hace fallar `remove` por igualdad de valor: `OpenPosition` es un `dataclass` congelado
y el stop movido lo vuelve un objeto distinto.

**R18 · El agregador de temporalidad se descarta en el cierre de sesión.** `BarAggregator` emite
solo cuando `minute % 60 == 59` y no resetea en ningún otro caso
(`candidate_a/smc/timeframe.py:109-125`). En un símbolo cuya sesión no termina en el minuto 59
—GER40 cierra 17:30 de Berlín, `data/sessions.py:64-69`— el acumulador quedaría abierto y la sesión
siguiente lo extendería, emitiendo una vela «H1» que cruza la noche y cuyo rango verdadero contiene
el salto de apertura. La hora parcial final **no emite vela**.

**R19 · El extremo rodante de una posición solo consume velas cuyo `open_time` sea igual o
posterior a su apertura.** Se deriva de R5 y se declara aparte porque **la agregación lo viola por
construcción**: una posición abierta a las 14:35 recibiría la vela de 14:00-14:59, cuyo máximo
puede ser anterior a su apertura. La hora de entrada se saltea entera.

**R20 · La vela agregada se despacha a TODAS las posiciones vivas del símbolo.** Un `IncrementalAtr`
y un `BarAggregator` por símbolo, un extremo rodante por posición: relación 1:N. Alimentar solo a
una posición cuando hay dos abiertas del mismo símbolo es un error silencioso.

**R21 · `position_id` es el primer campo de `OpenPosition` y no tiene valor por defecto.** Un campo
con default no puede preceder a campos sin default (`TypeError` de `dataclass`), y ponerlo al final
con un centinela permite que el centinela colisione como clave de estado y se filtre al artefacto.
Las tres fábricas de test que construyen por posición se actualizan.

**R22 · El embudo autoriza una intención sin objetivo fijo.** `inspect()` DEBE autorizarla cuando no
cae en ventana de noticias y su lotaje es válido, y DEBE seguir vetando por `INSUFFICIENT_RR` cuando
el cociente existe y queda bajo el umbral. `proposed_rr` es `float | None` y `_compute_rr` devuelve
`None` si y solo si `take_profit is None`.

Estaba redactado como «R17bis» **dentro de la sección de preguntas abiertas**, junto a la
resolución de Q-D. Un requisito normativo archivado bajo una pregunta es un requisito que se pierde:
vive acá, con los demás, y Q-D lo referencia.

## Criterios de aceptación (evals ejecutables)

**A1 · Monotonía en largos.** Sobre una serie sintética arbitraria, la secuencia de stops efectivos
de una posición larga es no decreciente.

**A2 · Monotonía en cortos.** La secuencia es no creciente. Se exige aparte de A1 porque un signo
invertido es un error que *mejora* el resultado y no rompe nada visible.

**A3 · El piso del stop inicial.** Con una serie que solo se mueve en contra, el stop efectivo es
en todo momento igual al stop inicial: el trailing no lo afloja nunca.

**A4 · Anti-anticipación del stop.** Extensión de la propiedad central del spec §9 al stop: mutar
cualquier barra posterior a `t` **no cambia** el stop efectivo aplicado en `t`. Es property test con
`hypothesis`, no un caso puntual.

**A5 · La barra en curso no participa.** Caso construido donde el `high` de la barra `t` es el
máximo de toda la serie: el stop aplicado en `t` es el que se derivó al cierre de `t-1`, y el fill
de `t` se resuelve contra ese. Si el `high` de `t` participara, el stop sería más alto y el fill
distinto: el test distingue las dos versiones.

**A6 · El ancla no mira antes de la apertura.** Serie con un máximo pronunciado `N-1` barras antes
de la entrada: el nivel de las primeras barras de vida **ignora** ese máximo. Contra-caso: con el
ancla sin anclar, el mismo escenario produce un stop del lado ganador de la entrada y una salida
inmediata; el test verifica que eso **no** ocurre.

**A7 · Golden test de fill con stop movido.** Mini-dataset donde el precio avanza, el stop sube, y
después retrocede hasta tocarlo: el fill se resuelve al stop movido y no al inicial, con el precio
exacto esperado.

**A8 · El registro explica el fill.** Para el escenario de A7, el `Ledger` contiene la secuencia de
movimientos, y el precio del fill coincide con el último stop registrado.

**A9 · Sin calentamiento, sin trailing.** Con menos barras que el período del ATR, el stop efectivo
es el inicial y **no** se levanta ninguna excepción.

**A10 · Determinismo.** Dos corridas idénticas producen secuencias de movimientos byte a byte
iguales.

**A11 · Ningún consumidor ve el stop viejo.** Después de la actualización de una barra, toda lectura
del estado de la cuenta devuelve la posición con el stop nuevo.

**A12 · El cierre forzado de sesión sigue intacto.** La batería existente de cierre por sesión pasa
sin cambios: ninguna posición sobrevive el borde de sesión por efecto del trailing.

**A13 · Regresión del torneo.** La suite completa pasa, y los tests del candidato B que hoy dependen
de niveles congelados siguen siendo válidos o se actualizan con su motivo escrito.

**A14 · Un salto de ATR no afloja el stop.** Sobre una posición ganadora, se inyecta una expansión
brusca de volatilidad: el nivel recalculado se aleja del precio y el stop efectivo **no retrocede**.
Verifica que el `ratchet` se aplica **después** del recálculo y no antes; el orden inverso pasa los
casos puntuales y falla acá.

**A15 · La geometría es horaria.** El nivel no cambia entre dos barras M1 pertenecientes a la misma
vela H1, y sí cambia al cerrarse la hora. Distingue una implementación alimentada con M1 de una
alimentada con H1, que es la que corresponde.

**A16 · La lista de posiciones no se corrompe.** Con tres posiciones abiertas y la primera cerrando
su fill en la misma pasada, las otras dos conservan su identidad y quedan con el stop actualizado.
Contra-caso: la escritura por índice produce `IndexError` con dos posiciones y sobrescribe la tercera
con tres. Segundo contra-caso: liquidar pasando la posición actualizada mientras la
liquidación remueve por valor levanta `ValueError`.

**A17 · El embudo autoriza sin objetivo.** Una intención con `take_profit = None`, fuera de ventana
de noticias y con lotaje válido, se autoriza. Contra-caso: con el veto sin condicionar, la misma
intención se rechaza por `INSUFFICIENT_RR` y la corrida termina en cero operaciones.

**A18 · Ninguna vela agregada cruza sesiones.** Sobre un símbolo cuyo cierre no cae en el minuto 59,
ninguna vela H1 emitida tiene su `open_time` y su `close_time` en días de sesión distintos.
Contra-caso: sin descartar el agregador en el cierre, aparece una vela que abarca la tarde de un día
y la mañana del siguiente.

**A19 · La hora de entrada no contamina el extremo.** Posición abierta a mitad de hora, con un
máximo pronunciado en esa misma hora **anterior** a la apertura: el extremo rodante no lo incorpora
y el stop efectivo no queda del lado ganador de la entrada.

**A20 · Dos posiciones del mismo símbolo reciben la misma vela.** Con dos posiciones vivas del mismo
símbolo y aperturas distintas, las dos actualizan su extremo al cerrar la vela H1, cada una
respetando su propio filtro de `open_time`.

**A21 · Liquidar sin remover no deja una posición fantasma.** Tras el cierre forzado de fin de
sesión, `AccountState.open_positions` queda **vacía**, y el criterio lo afirma directamente.

**Y el guardia no sirve de mecanismo, aunque parezca el natural.** `SessionBoundaryError`
(`simulator.py:456-466`) exige `bar.timestamp_utc > close_utc` **y** que el día ya figure en
`_session_closed_days`. El cierre forzado corre en esa misma barra, así que en la barra de cierre
ordinaria el guardia es **inerte**: no se evalúa hasta la barra siguiente del mismo día de sesión,
que en el último tramo de la jornada puede no existir. Un criterio que esperara la excepción ahí
pasaría en verde por la razón equivocada. Ejercitar el guardia exige inyectar una barra sintética
posterior a `close_utc` del mismo día, y es un caso aparte.

**A22 · `position_id` no se repite en el ledger cosido.** Sobre una corrida de walk-forward con al
menos dos ventanas que abran posiciones, los identificadores del ledger que produce
`_stitch_oos_ledgers` (`validation/wfa.py:401-426`) no tienen repetidos. Contra-caso: un
identificador que solo numere dentro de la ventana colisiona al coser. **Verifica R14, que no tenía
criterio.**

**A23 · El hash del perfil distingue los parámetros del trailing.** Dos `RiskProfile` que difieran
solo en `trailing_lookback`, o solo en `trailing_atr_mult`, producen `risk_profile_hash()` distinto.
Contra-caso: con el diccionario canónico sin los campos nuevos el hash coincide, y dos
configuraciones distintas comparten `trial_id`. **Verifica R15, que no tenía criterio.**

## Riesgos

1. **Anticipación por geometría.** `LookaheadError` protege el reloj, no la geometría; ninguna
   excepción existente caza este error. Cubierto por A4 y A5, y es el motivo de que sean dos
   criterios y no uno.
2. **La propiedad central del spec §9 no cubría el stop.** Se extiende explícitamente en A4.
3. **Formato de artefacto.** El tipo de entrada nuevo del `Ledger` rompe la comparación directa con
   artefactos de corridas anteriores.
4. **Referencias a la posición vieja.** El reemplazo posicional exige barrer los consumidores del
   estado de la cuenta. Cubierto por A11.
5. **El signo en cortos.** Cubierto por A2, y se declara como riesgo aparte porque su falla es
   silenciosa y favorable.
6. **Interacción con el drawdown trailing de la firma.** Son dos cosas distintas con el mismo
   nombre; el trailing de la firma se ancla en el pico de equity y no se toca. Riesgo de confusión
   en la lectura de resultados, no de implementación.

## Preguntas abiertas

- **Q-A · Dónde vive el estado por posición.** Una estructura auxiliar del simulador indexada por
  identidad de posición, o un objeto de gestión por posición. Es decisión de `design.md`.
- **Q-B · Qué hace la política cuando el ATR cambia entre barras.** El nivel se recalcula con el
  ATR corriente, así que un ATR que baja **acerca** el stop y uno que sube lo alejaría, pero R3 lo
  impide. Hay que dejar escrito que la monotonía gana sobre el recálculo.
- **Q-C · El re-export del módulo promovido.** Si `candidate_a` conserva un alias o se actualizan
  sus importadores. Decisión de `design.md`.
- **Q-D · RESUELTA el 2026-09-07: el veto por R:R no aplica sin objetivo fijo.** El requisito que
  esto impone es **R22**, y su criterio es A17. `proposed_rr` pasa
  a `float | None` y el veto solo se evalúa cuando hay cociente. **No es aflojar un gate
  normativo**: los gates go/no-go (G1-G9, C1-C2, P1-P3,
  `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md:546-569`) no contienen ningún criterio de
  riesgo/beneficio, y el `min_rr = 2,0` es un **default de embudo** que aparece como valor de un
  ejemplo de configuración (`.pulse/specs/strategy/spec.md:919`, R19 exige «valores default
  explícitos»). Los gates de resultado que sí deciden un GO (G3, G7, P3) quedan intactos. Decisión
  delegada por el director; fundamento completo, la alternativa descartada y lo que se pierde, en
  `design.md` §12 H6.

## Referencias

- `idea.md` y `proposal.md` de este Change.
- Pre-registro y decisión de doctrina: PR #95, Refs #88.
- `docs/SPEC_GENESIS_v1.4_PropTrading_TorneoCandidatos.md:459` (el spec ya lo promete) y §9
  (propiedad central de anti-anticipación).
- LeBeau & Lucas (1992), origen del par `(N = 22, k = 3,0)`.

<!-- change:135-b-4a-comision-por-instrumento-en-la-ficha-cierra-pa-106-c -->
# Specification: B.4a — costos por instrumento (comisión, spread y deslizamiento); cierra PA-106-C

Change #135 (Issue #135). Dominio `backtest` (toca además `validation`, por la enmienda E2, y
`scripts/run_pipeline.py`, por la misma razón). Fase `specify`. Formaliza `idea.md` y `proposal.md`
**con sus enmiendas E1, E2 y E3** (que mandan sobre el texto anterior de la propuesta cuando chocan);
no reabre ninguna de sus decisiones y deja marcadas las que siguen siendo de un humano o de `design`.
Contra: `b0f2950` (HEAD de `main` al iniciar esta fase). Todo `archivo:línea` de `src/` fue
verificado contra ese commit; las diferencias con lo que citan `idea.md`/`proposal.md` (escritos
contra `94aba5a`) están en la §9.

## 0. Resumen para el dueño (lenguaje llano)

Hoy el motor cobra **$7 de comisión al abrir y otros $7 al cerrar, en cualquier contrato**, más 1,5
puntos de spread y 0,2 de deslizamiento al abrir. Un MNQ de un contrato queda en **≈$17,40 de costo
contra $1,90 de comisión publicada por MFFU**. En M6E el mismo spread de 1,5 puntos serían $18.750.

Este change reemplaza esos tres números globales por **una tabla con una fila por contrato**:

- La **comisión** es la que MFFU publica «ida y vuelta»; se cobra **la mitad al abrir y la mitad al
  cerrar**. Una operación de un MNQ suma exactamente $1,90; una de MGC, $2,20.
- El **spread** y el **deslizamiento** pasan a medirse en **ticks** (el tick de cada contrato), con un
  piso provisional de 1 tick cada uno **hasta B.4b**. El deslizamiento se cobra **también al salir**
  (un stop desliza); el spread se cobra una sola vez, al entrar.
- Si el contrato **no tiene fila, el simulador no arranca** (ni cae a un número de respaldo).
- Los costos pasan a ser **parte de la identidad del ensayo**: si cambia una cifra, es otro ensayo y
  queda registrado como tal.
- **Antes de aplicar, usted firma las cinco cifras** (§R23). Ningún agente las da por buenas.

Con 1+1 ticks, el costo total ida y vuelta de un contrato queda entre $3,40 (MNQ) y $5,20 (MGC),
todos plausibles (tabla T1). Es un piso, no una medición: B.4b lo reemplaza.

## 1. Objetivo

Que el motor de capa 3 cobre, para cada instrumento, los costos de ese instrumento y de esa firma, y
que lo haga de forma verificable: cada cifra con su fuente y su fecha de lectura exigidas por el
cargador, ningún valor de respaldo, la falla ocurriendo antes de la primera barra, y los costos
visibles en la procedencia de cada corrida y en la identidad de cada ensayo del ledger.

Esto cierra **PA-106-C** (`SPEC_GENESIS_v1.5...md`, §11.1): las comisiones por contrato entran al
motor, y G3 (PF con costos completos), G9 (PF con estrés ×1,5) y los gates P dejan de correr sobre
un número heredado de los CFDs. **No** significa que corran sobre costos completamente verificados:
la **comisión** queda verificada; el **spread y el deslizamiento** siguen provisionales hasta B.4b, y
el texto de cierre de PA-106-C lo dice (R22).

## 2. Alcance IN / OUT

### IN

1. Tabla de costos por instrumento en `src/genesis/backtest/costs_config.json` con cinco filas de
   futuros CME (T1), cada una con `round_trip_usd`, `spread_ticks`, `slippage_ticks`,
   `friction_status`, `source_url` y `read_on`, y su validación de carga y de construcción (R1-R4).
2. `commission_for`, `spread_for` y `slippage_for` con símbolo, por pata, en ticks, y con falla con
   contexto cuando falta la fila (R5-R9).
3. Cobro por pata en `Simulator`: comisión en las dos patas (mitad cada una), deslizamiento en las dos
   patas, spread una vez en la entrada (R10).
4. Validación de la fila del símbolo en `Simulator.__init__`, con orden determinista respecto de la
   sesión (R11).
5. `CostsConfig` inmutable, hasheable y comparable por valor (R12).
6. `costs_hash` por símbolo en `RunProvenance`, en `compute_trial_id`, en `TrialIdentityContext`/
   `TrialRecord`/`ledger/trials.jsonl` y en el manifiesto del veredicto (R13-R17); cambio mínimo en
   `scripts/run_pipeline.py` para propagarlo (R18).
7. Adaptación de los tests existentes (R19), reescritura del test A7 (R20) y goldens (R21).
8. Docs: roadmap, spec v1.5 (PA-106-C), memorias de Serena, `ledger/README.md` (R22).
9. Precondición de `apply`: firma humana de las cinco cifras y de la cita (R23).

### OUT (YAGNI explícito)

- **B.4b**: leer el `bbo-1m`, su loader y su almacenamiento. La rama de ticks reales de `spread_for`
  se conserva con su valor actual.
- **B.2 / B.3**: fichas de contrato CME, exportador, clave contrato → raíz (`MNQZ6` → `MNQ`) y
  **`SESSIONS`** (`data/sessions.py:45-74`): MNQ y los demás no se agregan. Un MNQ sigue sin poder
  simularse por el `Simulator` (lo rechaza la tabla de sesiones); por eso los goldens son a nivel de
  función (R21).
- **`SymbolFigure`, sidecars (#114), `ArtifactMetadata`, `FirmProfile`, `firm_profile_hash`**: no se
  tocan (`git diff --stat -- src/genesis/data` vacío).
- **`swap_for`**: sin cambios, aunque los futuros no tengan swap. El simulador lo cobra con
  `days_held >= 1` (`simulator.py:720`); es un tema del modelo de tenencia nocturna.
- **Distinguir el tipo de salida** (stop, objetivo, cierre de sesión, trailing) para el deslizamiento:
  se cobra en toda salida (R10). Distinguirlas es modelo de fill, no de esta casilla.
- **Cobro de spread en la salida**: el spread completo de la entrada ya equivale a dos medios spreads.
- **Validar `figure.symbol == symbol`**: hoy los tests usan una misma ficha con símbolos distintos;
  agregar la guarda los rompería y no es objeto de B.4a.
- **Medir spread o deslizamiento**: las cifras de 1 tick son un piso provisional sin fuente de mercado
  (E1), no una calibración.
- **`scripts/bench_simulator.py`**: sin diff. Corre sobre `data/raw/` (solo CFDs/forex/BTCUSDT), así
  que tras el cambio falla con el error claro de R11; es coherente con el pivote a CME.
- **Reparar el desfase de las specs vivas** con `risk_profile_hash` (R98, R100, R2, R4, R45; ver §3 y
  §9): el delta agrega lo suyo y no reescribe lo ajeno. Las specs vivas (`.pulse/specs/**`) las
  actualiza el engine al cerrar; nadie las edita a mano.

## 3. Delta sobre las specs vivas

Las specs vivas acumulan los requisitos de cada change con numeración propia (`R1` existe en varios
changes). Aquí se cita como `R<n> (#<change>)`. Los `R1..R24` de este documento son locales a este
change.

### MODIFICA

| Spec viva | Requisito | Qué cambia | Local |
|---|---|---|---|
| backtest | **R37 (#6)** | `spread_for`/`commission_for`/`slippage_for` reciben el símbolo y lo **usan**; `commission_for` devuelve **una pata**; las tres fallan con contexto si el símbolo no tiene fila. `swap_for` sin cambios. | R5-R7, R9 |
| backtest | **R38 (#6)** | `stress` sigue siendo factor final de primera clase; se precisa que multiplica el costo de **cada pata** y el spread de entrada. Sin cambio de semántica. | R8 |
| backtest | **R39 (#6)** | `load_costs_config` ya no carga «defaults» globales sino una **tabla por instrumento con fuente obligatoria**, con rechazo explícito de cada caso inválido. | R1-R4 |
| backtest | **R40 (#6)** | «Sin costos válidos no hay reporte» incluye «**sin fila de costos para el símbolo**», verificado en `Simulator.__init__` con orden fijo. | R11 |
| backtest | **R45 (#6)** | `RunProvenance` gana `costs_hash`. (La enumeración literal de R45 está desfasada desde #109; el delta solo agrega esta huella.) | R13, R14 |
| backtest | **R111 (#24)** | Se **conserva su sustancia** (`spread_for` consume la ventana de ticks ya filtrada y no invoca `has_sufficient_tick_coverage`/`ticks_in_bar_window`) y se **retira su prohibición de modificar el archivo**, que era una restricción de alcance del change #24 (R109 de ese mismo change lo declara «en este Change»). | R6 |
| backtest | **`BacktestConfigError`** (R3 y tabla de decisiones, #6) | Gana el disparador (d): «símbolo sin fila en la tabla de costos». | R11 |
| validation | **R2 (#53)** | `TrialRecord` gana `costs_hash_by_symbol`. (La enumeración literal está desfasada desde #109.) | R16 |
| validation | **R4 (#53)** | `compute_trial_id` gana el parámetro `costs_hash_by_symbol`. | R15 |
| validation | **R15 (#53)** | Su cláusula «las mismas claves de identidad que recibe `verdict_result_to_manifest_json`» obliga a que el manifiesto reciba también la huella de costos. | R17 |
| validation | **R98 y R100 (#14)** | El manifiesto y `write_verdict_artifacts` reciben y serializan `costs_hash_by_symbol`; `verdict_schema_version` pasa a `/4`. | R17 |

### AGREGA

- Tabla `T1` y su validación (R1-R4); cobro por pata (R10); inmutabilidad de `CostsConfig` (R12);
  `costs_hash` y su serialización canónica (R13); guarda de coherencia de claves en
  `TrialIdentityContext` (R16); propagación en el runner (R18); fixture de test y reescritura de A7
  (R19, R20); goldens (R21); documentación (R22); precondición de firma (R23); invariantes de lo que
  no cambia (R24).

### ELIMINA

No se elimina ningún requisito vivo completo. Se eliminan **campos y comportamientos**:

- Los tres globales `default_spread_points`, `commission_per_lot`, `slippage_points`, tanto de
  `CostsConfig` como de `costs_config.json` (`costs.py:24-30`, `costs_config.json:2-4`).
- El **fallback global conservador** de `spread_for` (`costs.py:52-53`, `:45`), sustituido por
  `spread_ticks` de la fila.
- El **doble cobro**: la comisión por lote completa en cada pata (`simulator.py:666` y `:717`).
- La **asimetría «deslizamiento solo en la entrada»**: la salida deja de pagar solo comisión y swap
  (`simulator.py:717-731`).
- La prohibición de modificar `costs.py::spread_for` (R111 de #24), según arriba.

## 4. Requisitos funcionales

Convención: **DEBE / NO DEBE** normativo. Cada requisito lleva sus escenarios en formato
`DADO / CUANDO / ENTONCES` (evals ejecutables, `.agents/rules/eval-tdd-conventions.md`). Los nombres
de test son orientativos: `apply` puede ajustarlos conservando la semántica. `==` significa
igualdad exacta (no `approx`).

### Tabla T1 — fuente única de las cinco filas

Fuente: <https://help.myfundedfutures.com/en/articles/9735811>, «Futures Instrument List», columna
«Total Cost Round Trip», fechada por la página 24-ago-2026, leída el **2026-10-02**. Las columnas
marcadas «derivado» no se leen de la fuente.

| Símbolo | `round_trip_usd` | Por pata (= ÷2) | Tick | Valor del tick | $/punto (derivado) | Fricción de 1 tick en USD (derivado) | Total ida y vuelta con 1+1 ticks (derivado) |
|---|---|---|---|---|---|---|---|
| MNQ | 1,90 | 0,95 | 0,25 | $0,50 | 2,00 | 0,50 | **3,40** |
| MGC | 2,20 | 1,10 | 0,10 | $1,00 | 10,00 | 1,00 | **5,20** |
| MCL | 1,16 | 0,58 | 0,01 | $1,00 | 100,00 | 1,00 | **4,16** |
| M6E | 1,44 | 0,72 | 0,0001 | $1,25 | 12.500 | 1,25 | **5,19** |
| MBT | 3,50 | 1,75 | 5,00 | $0,50 | 0,10 | 0,50 | **5,00** |

«Total con 1+1 ticks» = comisión + 1 tick de spread (una vez) + 1 tick de deslizamiento por pata
(dos veces) = `round_trip_usd + 3 × valor del tick`, por contrato, con `stress = 1`.

**H1 resuelta por el orquestador (2026-10-02; se aprueba en el gate de design): cinco filas, sin MES
ni MYM.** El roadmap rechazó comprar esos datos (`ROADMAP_ARQUITECTO.md`, B.7 y §7.1e) y el DoD de
B.4a pide la comisión de «cada instrumento **del universo**». Dos filas que ningún flujo usa serían
configuración muerta y dos cifras más para firmar. Agregarlas después cuesta una fila y una firma.
MFFU publica $1,90 para ambas, y esa lectura queda registrada en §9.

### Tabla de costos y carga

**R1 — Estructura de la tabla.** *(Modifica R39 (#6); mapea proposal «What Changes» 1-2.)*
`CostsConfig` DEBE representar **una fila por símbolo** y cada fila DEBE tener exactamente estos
campos:

| Campo | Tipo y rango | Significado |
|---|---|---|
| `round_trip_usd` | número finito, `> 0` | USD por contrato, ida y vuelta: **literalmente** la columna «Total Cost Round Trip» de la lista de MFFU |
| `spread_ticks` | número finito, `>= 0` | spread de entrada, en ticks (múltiplos de `SymbolFigure.tick_size`) |
| `slippage_ticks` | número finito, `>= 0` | deslizamiento **por pata**, en ticks |
| `friction_status` | cadena, valor ∈ {`provisional_hasta_b4b`} | marca de procedencia de `spread_ticks` y `slippage_ticks` |
| `source_url` | cadena, `https://` con host | fuente primaria de `round_trip_usd` |
| `read_on` | cadena `YYYY-MM-DD` | fecha de la lectura de la fuente |

`CostsConfig` NO DEBE conservar `default_spread_points`, `commission_per_lot` ni
`slippage_points`, ni ningún valor global equivalente. La **clave** de cada fila es el `symbol`
convencional tal como llega a `Simulator`/`run_wfa` (p. ej. `MNQ`; en `run_pipeline.py` es
`args.symbol`, no `resolved_symbol`), con **comparación exacta**, sin normalizar mayúsculas ni
sufijos. Ni el nombre del terminal (`US500.cash`) ni el código de contrato (`MNQZ6`) son claves: el
mapeo contrato → raíz es de B.3. El conjunto cerrado de `friction_status` se amplía solo cuando B.4b
defina un valor «medido».

- E1.1 DADO el árbol tras `apply` CUANDO `rg -n "commission_per_lot|default_spread_points" src scripts`
  y `rg -n "config\.slippage_points|\"slippage_points\"" src` ENTONCES 0 coincidencias.
  *(No usar `slippage_points` pelado: sobrevive como variable local en `simulator.py:665-667`.)*
- E1.2 DADO el JSON empaquetado cargado CUANDO se pide la fila de `"mnq"` (minúsculas) ENTONCES
  `BacktestConfigError` (no hay normalización). Test: `test_clave_de_simbolo_es_exacta`.

**R2 — El JSON empaquetado trae exactamente T1.** *(Modifica R39 (#6); mapea criterios 1 y 2 de la
propuesta.)* `costs_config.json` DEBE contener **exactamente las cinco filas de T1** y ninguna otra:
ni de CFD, ni de test, ni de respaldo. Cada fila DEBE llevar
`source_url = "https://help.myfundedfutures.com/en/articles/9735811"`,
`read_on = "2026-10-02"` (o la fecha de la relectura del dueño si es posterior, R23),
`spread_ticks = 1`, `slippage_ticks = 1` y `friction_status = "provisional_hasta_b4b"`. El archivo
PUEDE llevar claves de comentario en la raíz que empiecen con `_` (convención de
`profiles/mffu_rapid_eod_50k.json`); DEBE llevar `_nota` con lo que el dueño declare sobre el alcance
de «Total Cost Round Trip» (R23).

- E2.1 DADO `load_costs_config()` CUANDO se leen sus símbolos y filas ENTONCES los símbolos son
  `M6E, MBT, MCL, MGC, MNQ` y, para cada uno, `round_trip_usd == ` el valor de T1,
  `spread_ticks == 1.0`, `slippage_ticks == 1.0`, `friction_status`, `source_url` exacta y `read_on`
  con la fecha firmada. Test:
  `test_load_costs_config_empaquetado_trae_exactamente_las_cinco_filas`.
- E2.2 DADO `src/genesis/backtest/costs_config.json` CUANDO `rg -c '"round_trip_usd"'` ENTONCES `5`, y
  `rg -n "US500|NAS100|US30|GER40|XAUUSD|EURUSD|GBPUSD|USDJPY|BTCUSDT|SYM_|TEST" <archivo>` ENTONCES
  0 coincidencias.

**R3 — Validación de carga y de construcción.** *(Modifica R39 (#6); mapea criterio 6.)* Todo camino
que produzca una fila o un `CostsConfig` —el cargador **o la construcción directa**— DEBE rechazar
con `BacktestConfigError` cada caso de la lista siguiente. El mensaje DEBE citar la fuente (ruta o
recurso), el símbolo, el campo y el valor recibido. Los campos numéricos aceptan `int` y `float`
(se normalizan a `float`) y rechazan `bool`, cadenas, `null`, listas y objetos. La validación NO DEBE
tocar la red ni el reloj: `source_url` no se resuelve y `read_on` no se compara con «hoy».

| Caso | Se rechaza cuando |
|---|---|
| T-a | el JSON no se puede parsear |
| T-b | la raíz no es un objeto |
| T-c | falta `instruments`, o no es un objeto |
| T-d | `instruments` está vacío |
| T-e | hay una clave desconocida en la raíz que no empieza con `_`, **incluidas las del formato viejo** (`commission_per_lot`, `default_spread_points`, `slippage_points`) |
| T-f | un símbolo aparece **duplicado** en el objeto JSON (el parser lo resolvería en silencio con el último) |
| T-g | un símbolo es vacío o tiene espacios en los extremos |
| F-a | una fila no es un objeto |
| F-b | falta cualquiera de los seis campos de R1 |
| F-c | una fila trae una clave desconocida |
| F-d | `round_trip_usd` es `<= 0`, `NaN`, `±Infinity`, o de tipo no numérico (incluido `true`) |
| F-e | `spread_ticks` o `slippage_ticks` es `< 0`, `NaN`, `±Infinity`, o de tipo no numérico |
| F-f | `friction_status` está fuera del conjunto cerrado de R1 |
| F-g | `source_url` es vacía, solo espacios, no empieza con `https://` o no tiene host |
| F-h | `read_on` no cumple `^\d{4}-\d{2}-\d{2}$` o no es una fecha del calendario (p. ej. `2026-02-30`) |

`spread_ticks = 0` y `slippage_ticks = 0` **son válidos**: el cargador no distingue producción de
test. El guardián de producción es E2.1 (el empaquetado debe traer 1 y 1).

- E3.1 DADO el JSON empaquetado y una mutación por caso de la tabla (una por letra, y una por
  variante de tipo/valor dentro de F-d, F-e y F-g) CUANDO `load_costs_config(path)` ENTONCES
  `BacktestConfigError` cuyo texto nombra el símbolo (si aplica) y el campo. Test parametrizado:
  `test_load_costs_config_rechaza[<caso>]`, un id por caso.
- E3.2 DADO una construcción directa de una fila con `round_trip_usd=-1.0` (y una por cada caso F)
  CUANDO se construye ENTONCES `BacktestConfigError` (la validación vive en la fila, no solo en el
  cargador). Test: `test_fila_invalida_no_se_puede_construir`.
- E3.3 DADO `{"default_spread_points": 1.5, "commission_per_lot": 7.0, "slippage_points": 0.2}`
  (el formato viejo) CUANDO `load_costs_config(path)` ENTONCES `BacktestConfigError` y el mensaje
  menciona el formato anterior. Test: `test_formato_viejo_se_rechaza_con_mensaje_claro`.
- E3.4 DADO `read_on = "20261002"` o `"2026-W40-5"` (que `date.fromisoformat` acepta en Python 3.14)
  CUANDO se carga ENTONCES `BacktestConfigError`. *(Por eso F-h exige la expresión regular además de
  la fecha válida.)*

**R4 — Sin valor de respaldo.** *(Mapea criterio 4 y punto 2 del DoD del roadmap.)* `src/` NO DEBE
contener constante, fila implícita ni rama «si no hay fila, usar X» que devuelva un costo para un
símbolo sin fila. Se verifica por comportamiento (E5.6, E6.4, E7.3, E9.1) y por E1.1.

### Funciones de costo

**R5 — `commission_for` cobra una pata.** *(Modifica R37 (#6); mapea punto 2 del encargo.)*
Firma: `commission_for(symbol, sizing_hint, config, *, stress=1.0) -> float`. DEBE devolver
`(round_trip_usd / 2) * sizing_hint * stress`, **evaluado en ese orden de izquierda a derecha** y sin
redondeo (ni a centavos: el redondeo por pata rompería la igualdad `pata + pata == ida y vuelta` y la
linealidad del `stress`). El ida y vuelta es la suma de la llamada de apertura y la de cierre. Un
símbolo sin fila DEBE fallar según R9.

- E5.1 (golden MNQ) DADO la configuración empaquetada CUANDO `commission_for("MNQ", 1.0, cfg)` se
  invoca para la apertura y para el cierre ENTONCES cada pata `== 0.95` y la suma `== 1.90`.
  Test: `test_commission_for_mnq_ida_y_vuelta_es_1_90`.
- E5.2 (golden MGC) ídem: pata `== 1.10`, suma `== 2.20`. Test:
  `test_commission_for_mgc_ida_y_vuelta_es_2_20`.
- E5.3 DADO cada símbolo de T1 CUANDO se suman dos patas ENTONCES `== round_trip_usd` de T1.
  Test parametrizado: `test_commission_for_tabla_completa_pata_mas_pata`.
- E5.4 DADO `sizing_hint = 3.0` CUANDO se compara con `1.0` ENTONCES `approx(3 * leg)` (lineal en
  contratos).
- E5.5 DADO `stress = 2.0` ENTONCES `approx(2 * commission_for(..., stress=1.0))`.
- E5.6 DADO un símbolo sin fila ENTONCES `BacktestConfigError` y ningún valor devuelto (R9).

**R6 — `spread_for` por instrumento.** *(Modifica R37 (#6) y R111 (#24).)* La firma **no cambia**:
`spread_for(symbol, timestamp, figure, ticks_window, config, *, stress=1.0)`. DEBE resolver primero la
fila del símbolo, **con o sin ventana de ticks**, de modo que la falla por símbolo sin fila no dependa
de la cobertura de ticks de ese día (una falla que aparece solo en las barras sin ticks es
indeterminista de cara al usuario). Con ventana no vacía DEBE devolver
`mediana(ask - bid) * stress` (valor y semántica actuales, `costs.py:50-51`). Sin ventana, o con
ventana vacía, DEBE devolver `spread_ticks * figure.tick_size * stress`, en **puntos de precio**, de
modo que el simulador sigue multiplicando por `value_per_point`. NO DEBE invocar
`has_sufficient_tick_coverage` ni `ticks_in_bar_window`.

- E6.1 (rama de ticks, mismo valor) DADO ventana `[bid 100.0 / ask 100.2, bid 100.0 / ask 100.4]` y
  una fila para `US500` en la configuración de test CUANDO `spread_for("US500", ...)` ENTONCES
  `approx(0.3)`. *(Es el test existente `test_spread_for_con_ticks_usa_mediana_de_ask_menos_bid`, con
  el mismo valor esperado.)*
- E6.2 (golden MNQ) DADO una ficha construida a mano `tick_value=0.5, tick_size=0.25` y la
  configuración empaquetada CUANDO `spread_for("MNQ", ts, fig, None, cfg)` ENTONCES `== 0.25`, y
  `0.25 * 1.0 * fig.value_per_point == 0.50`. Test: `test_golden_mnq_spread_un_tick`.
- E6.3 DADO `stress = 2.0` ENTONCES `approx(2 * spread_for(..., stress=1.0))` en las dos ramas.
- E6.4 DADO un símbolo sin fila y una ventana de ticks **no vacía** ENTONCES `BacktestConfigError`
  (la falla no depende de la cobertura). Test: `test_spread_for_simbolo_sin_fila_falla_con_ticks`.

**R7 — `slippage_for` por instrumento.** *(Modifica R37 (#6).)* Firma nueva:
`slippage_for(symbol, figure, config, *, stress=1.0) -> float` (el símbolo pasa a ser el primer
parámetro, igual que en `spread_for`; hoy es `slippage_for(figure, config, *, stress)`,
`costs.py:62`). DEBE devolver `slippage_ticks * figure.tick_size * stress`, en puntos de precio **por
pata**. Un símbolo sin fila DEBE fallar según R9.

- E7.1 (golden MNQ) DADO la ficha de E6.2 y la configuración empaquetada CUANDO `slippage_for("MNQ",
  fig, cfg)` ENTONCES `== 0.25`, y `0.25 * 1.0 * fig.value_per_point == 0.50`. Test:
  `test_golden_mnq_deslizamiento_un_tick`.
- E7.2 DADO `stress = 2.0` ENTONCES `approx(2 * slippage_for(..., stress=1.0))`.
- E7.3 DADO un símbolo sin fila ENTONCES `BacktestConfigError` (R9).

**R8 — `stress` de primera clase.** *(Modifica R38 (#6).)* Las tres funciones DEBEN seguir aceptando
`stress: float = 1.0` solo por nombre y aplicarlo como **factor final**: para cualquier entrada válida,
`f(stress=2.0)` es `approx(2 * f(stress=1.0))`. `swap_for` queda sin cambios (firma incluida).

- E8.1 DADO cada una de `commission_for`, `spread_for` (sin ticks y con ticks) y `slippage_for`
  CUANDO se invoca con `stress=2.0` ENTONCES `approx(2 *` el valor con `stress=1.0)`. Tests: los
  `test_*_stress_duplica_el_costo` existentes, adaptados.
- E8.2 DADO `swap_for` CUANDO se invoca como hoy ENTONCES el test
  `test_swap_for_stress_duplica_el_costo` pasa **sin modificación**.

**R9 — Falla con contexto.** *(Modifica R37/R40 (#6); mapea criterio 4.)* Para `commission_for`,
`spread_for`, `slippage_for`, `costs_hash` (R13) y `Simulator.__init__` (R11), un símbolo sin fila
DEBE lanzar `BacktestConfigError` cuyo mensaje contenga `repr(symbol)`, la **lista ordenada** de los
símbolos que sí tienen fila, y la indicación de que no existe un valor de respaldo. NO DEBE devolver
ningún valor. La redacción exacta es de `design`; el contenido es el de este requisito.

- E9.1 DADO `config` con filas `{"MNQ", "MGC"}` y el símbolo `"NOPE"` CUANDO se invoca cada una de las
  cinco funciones ENTONCES `pytest.raises(BacktestConfigError)` y `str(exc)` contiene `'NOPE'`,
  `MGC` y `MNQ` en ese orden relativo (alfabético) y la indicación de falta de respaldo. Test
  parametrizado: `test_simbolo_sin_fila_falla_con_contexto[<funcion>]`.

### Simulador

**R10 — Cobro por pata.** *(Agrega; incorpora la enmienda E1; mapea punto 3 del encargo.)* Con `q =
sizing_hint`, `v = figure.value_per_point`, `s = stress`, `c = round_trip_usd` de la fila, el
`Simulator` DEBE cobrar:

- **Entrada** (`cost_applied` del `FillRecord` con `is_exit=False`):
  `(c/2)·q·s  +  (spread_pts + slip_pts)·q·v`, con `spread_pts = spread_for(...)` y
  `slip_pts = slippage_for(...)`, ambos en puntos y ya con `s`.
- **Salida** (`cost_applied` del `FillRecord` con `is_exit=True`):
  `(c/2)·q·s  +  slip_pts·q·v  +  swap_money`, con `swap_money` como hoy (`simulator.py:720-728`).
- **El spread NO se cobra en la salida.**
- El deslizamiento de la salida se cobra **en toda salida** (stop, objetivo, trailing, cierre forzado
  de sesión y caso de vela única): las tres rutas pasan por `_close_position`
  (`simulator.py:433, 611, 707`), que es donde se cobra.
- El balance DEBE seguir descontando exactamente lo que se registra en `cost_applied`: tras una
  operación, `balance_final - balance_inicial == pnl_bruto - (cost_entrada + cost_salida)`.

Sin swap, el ida y vuelta es `c·q·s + (spread_pts + 2·slip_pts)·q·v`. Como `v = tick_value /
tick_size`, el costo de fricción en dinero es `ticks · tick_value · q · s`: **independiente de
`tick_size`**. El valor `1+1 ticks` de T1 no es «conservador» (E1): es un **piso provisional**.

- E10.1 DADO una ficha `tick_value=0.5, tick_size=0.25` (como MNQ) y una fila de test
  `round_trip_usd=1.90, spread_ticks=1, slippage_ticks=1`, `sizing_hint=1.0`, `stress=1.0`, sin
  ticks CUANDO se abre y se cierra el mismo día ENTONCES `entrada.cost_applied == approx(1.95)`,
  `salida.cost_applied == approx(1.45)` y su suma `== approx(3.40)`. Test:
  `test_simulator_cobra_comision_mitad_por_pata_y_deslizamiento_en_ambas`.
- E10.2 DADO la misma configuración con `spread_ticks=0, slippage_ticks=0` ENTONCES la suma de los dos
  `cost_applied` `== approx(1.90)` (exactamente el ida y vuelta de la fila). *(`approx` porque pasa
  por el balance; la igualdad exacta se fija a nivel de función, R5.)*
- E10.3 DADO `stress=2.0` ENTONCES entrada `approx(3.90)` y salida `approx(2.90)`.
- E10.4 DADO una salida por cierre forzado de sesión y otra por stop ENTONCES las dos cobran el mismo
  deslizamiento (no se distingue el tipo de salida). Test:
  `test_deslizamiento_de_salida_se_cobra_en_toda_salida`.
- E10.5 DADO esa operación CUANDO se compara el balance final ENTONCES
  `approx(inicial + pnl_bruto - (entrada + salida))`. *(Lo cubren también las propiedades de
  reconstrucción de equity existentes, que NO se modifican.)*

**R11 — Validación en `Simulator.__init__`, con orden determinista.** *(Modifica R40 (#6); mapea
criterio 5 y punto 4 del encargo.)* `Simulator.__init__` DEBE comprobar, **en este orden y
deteniéndose en el primer incumplimiento**:

1. el candidato implementa `RiskLevelsProvider` (`simulator.py:271-277`, sin cambio);
2. `costs_config` es una instancia de `CostsConfig` (`simulator.py:279-284`, sin cambio);
3. el símbolo está en la tabla de sesiones (`simulator.py:286-292`, sin cambio de texto);
4. **el símbolo tiene fila de costos (NUEVO, R9)**;
5. la ficha de firma declara `house_rule` (`simulator.py:294-300`, sin cambio).

Razón del orden: el chequeo nuevo solo puede **convertir en error corridas que antes arrancaban**;
ningún error que ya existía cambia de tipo ni de mensaje, y un símbolo ausente de las dos tablas
produce el mismo error de sesión que hoy. La falla sale del constructor, antes de que `run()` procese
la primera barra. El docstring de la clase DEBE reflejar el orden, y el docstring de
`BacktestConfigError` DEBE ganar el disparador (d).

Efectos que este requisito **declara** para que nadie los lea como regresión: con el JSON empaquetado,
todo símbolo de `SESSIONS` (`US500`, `NAS100`, `US30`, `GER40`, `XAUUSD`, `EURUSD`, `GBPUSD`,
`USDJPY`, `BTCUSDT`) falla en `__init__` por falta de fila, y por lo tanto
`scripts/run_pipeline.py` y `scripts/bench_simulator.py` sobre el `data/raw/` actual fallan con este
error claro. Un MNQ pasa el chequeo de costos y falla en el de sesión (B.3 lo resuelve).

- E11.1 DADO una configuración sin fila de `US500` (símbolo sí presente en `SESSIONS`) CUANDO se
  construye `Simulator(..., symbol="US500")` ENTONCES `BacktestConfigError` con `'US500'` y la lista
  de símbolos con fila, **lanzado por el constructor** (el test no llama a `run`). Test:
  `test_simulator_simbolo_sin_fila_falla_en_init`.
- E11.2 (orden) DADO `symbol="NOPE"` (ausente de `SESSIONS` y de la tabla) ENTONCES el mensaje
  menciona la tabla de sesiones y no la fila de costos.
- E11.3 (orden) DADO un símbolo con fila de test pero fuera de `SESSIONS` ENTONCES el error es el de
  sesiones.
- E11.4 DADO `load_costs_config()` (empaquetado) y `symbol="US500"`, y otra vez con `"BTCUSDT"`
  ENTONCES `BacktestConfigError` que lista los cinco símbolos de T1. Test:
  `test_json_empaquetado_no_trae_filas_de_cfd_ni_de_cripto`.
- E11.5 DADO un símbolo con fila y con sesión ENTONCES el constructor termina sin error.
- E11.6 DADO `tests/backtest/test_simulator_contract.py` CUANDO se corre ENTONCES pasa sin
  modificación de sus aserciones (el chequeo (1) y el de `NOPE` se conservan).

### Inmutabilidad

**R12 — `CostsConfig` inmutable y hasheable.** *(Incorpora la enmienda E3; mapea punto 5.)*
`CostsConfig` y cada fila DEBEN ser **inmutables** (asignar un campo falla), **hasheables**
(`hash(config)` funciona) y **comparables por valor** (`==`). Dos configuraciones con las mismas filas
cargadas en distinto orden DEBEN ser iguales y tener el mismo `hash`. NO DEBE existir camino público
de construcción que deje un `CostsConfig` no hasheable, ni operación pública que devuelva una
estructura mutable cuya mutación altere la configuración. Condición para `design`: verificado en
Python 3.14.4 que `hash(MappingProxyType({...}))` **falla** (`unhashable type: 'dict'`), así que un
mapa de solo lectura sobre un `dict` no cumple; la forma por defecto es una **tupla ordenada por
símbolo de filas congeladas** (la elección final de nombres y de cómo se expone la consulta por
símbolo es de `design`).

- E12.1 DADO un `CostsConfig` cargado CUANDO se asigna cualquiera de sus campos o de los de una fila
  ENTONCES se lanza el error de inmutabilidad (`FrozenInstanceError`/`AttributeError`/`TypeError`).
  Test: `test_costs_config_no_se_puede_mutar`.
- E12.2 DADO `load_costs_config()` invocado dos veces ENTONCES `a == b` y `hash(a) == hash(b)`, y
  `{a: 1}[b] == 1`. Test: `test_costs_config_es_hasheable_y_comparable`.
- E12.3 DADO el mismo JSON con las filas en otro orden ENTONCES `a == b` y `hash(a) == hash(b)`.
- E12.4 DADO la lista de símbolos que expone la configuración ENTONCES es una tupla ordenada.

### Identidad de la corrida y del ensayo

**R13 — `costs_hash` por símbolo y su serialización canónica.** *(Incorpora E2; mapea punto 6.)* La
capa 3 DEBE exponer `costs_hash(symbol, config) -> str` (SHA-256 hexadecimal), con símbolo sin fila
según R9. La serialización canónica DEBE ser **exactamente** esta, con la misma llamada que
`exit_geometry_hash` (`strategy/exit_geometry.py:69-77`):

```
json.dumps({"round_trip_usd": float(c), "slippage_ticks": float(sl), "spread_ticks": float(sp)},
           ensure_ascii=False, sort_keys=True)   ->   UTF-8   ->   sha256
```

- **Entran** al hash: `round_trip_usd`, `spread_ticks`, `slippage_ticks`, normalizados con `float()`
  (para que `1` y `1.0` no produzcan huellas distintas: `json.dumps(1)` es `"1"` y `json.dumps(1.0)`
  es `"1.0"`).
- **No entran**: `source_url`, `read_on`, `friction_status` y el propio símbolo.

**Decisión sobre `source_url`/`read_on` (punto 6 del encargo): la cita NO identifica un ensayo.** Un
ensayo es lo que se simuló, y lo que se simuló lo determinan los tres números. Si MFFU mueve su
página, o el dueño la relee el 2026-12-01 y el número sigue siendo $1,90, la simulación es
**mecánicamente idéntica**; contarla como ensayo nuevo inflaría el `n_trials` del DSR (más
deflación, más falsos negativos) y rompería la idempotencia de `append_trial` por una razón que no es
estadística. Es el mismo criterio que ya rige a `exit_geometry_hash` (excluye `source`) y a
`house_rule_hash` (excluye `funded_starting_balance`, DH-4: «dos fichas cuyas simulaciones son
mecánicamente idénticas producirían huellas distintas y sus ensayos dejarían de colapsar»). A la
inversa, si el **número** cambia aunque la cita no, es otro ensayo y la huella cambia. Por la misma
razón `friction_status` no entra: si B.4b confirma que 1 tick era el valor medido, el número no cambió
y el resultado guardado sigue siendo válido. El símbolo no entra porque el mapa de R15 ya está
indexado por símbolo; dos instrumentos con la misma fila numérica comparten huella sin ambigüedad.

- E13.1 (golden) DADO la configuración empaquetada ENTONCES `costs_hash("MNQ", cfg) ==
  "6b5b237b9be9f6488049b7f34240b2cce3107c80e965d51f61cce409f8c81d1b"`, que es el SHA-256 de la cadena
  `{"round_trip_usd": 1.9, "slippage_ticks": 1.0, "spread_ticks": 1.0}`. Test:
  `test_costs_hash_mnq_golden`.
- E13.2 DADO dos configuraciones cuyas filas de `MNQ` difieren **solo** en `source_url` y `read_on`
  ENTONCES `costs_hash("MNQ", a) == costs_hash("MNQ", b)`.
- E13.3 DADO dos configuraciones que difieren en `round_trip_usd`, o en `spread_ticks`, o en
  `slippage_ticks` de `MNQ` (una prueba por campo) ENTONCES los hashes difieren.
- E13.4 DADO dos configuraciones que difieren **solo** en la fila de `MGC` ENTONCES
  `costs_hash("MNQ", a) == costs_hash("MNQ", b)`.
- E13.5 DADO una fila cargada con `"spread_ticks": 1` y otra con `1.0` ENTONCES mismo hash.
- E13.6 DADO una configuración de test con dos símbolos de fila numéricamente idéntica (`SYM_A` y
  `SYM_B`) ENTONCES `costs_hash("SYM_A", cfg) == costs_hash("SYM_B", cfg)`. Documenta que el símbolo no
  entra al hash.
- E13.7 DADO un símbolo sin fila ENTONCES `BacktestConfigError` (R9).

**R14 — `RunProvenance.costs_hash`.** *(Modifica R45 (#6); incorpora E2.)* `RunProvenance`
(`backtest/ledger.py:96-111`) DEBE ganar `costs_hash: str`, **sin valor por defecto** (un default
permitiría olvidarlo en silencio, que es el modo de falla que E2 cierra; mismo criterio que
`exit_geometry_hash`, `house_rule_hash` y `exhaustion_policy`). Lo DEBE poblar `Simulator.__init__`
(`simulator.py:328-336`) con `costs_hash(symbol, costs_config)` y `_stitch_oos_ledgers`
(`validation/wfa.py:433-462`) con el mismo cálculo sobre el `symbol` y el `costs_config` que
`run_wfa` ya recibe, **sin cambiar la firma de `run_wfa`**. `ledger.CONFIG_VERSION`
(`"genesis-backtest/1"`) NO se modifica: es el precedente de #109, que agregó tres campos a
`RunProvenance` sin subirlo, y `tests/backtest/test_ledger.py:47` lo fija.

- E14.1 DADO un `Simulator` de `US500` con la configuración de test CUANDO se lee
  `sim.ledger.provenance.costs_hash` ENTONCES `== costs_hash("US500", cfg)`. Test:
  `test_simulator_provenance_trae_costs_hash`.
- E14.2 DADO el resultado de `run_wfa(...)` sobre un símbolo ENTONCES
  `wfa_result.oos_ledger_cosido.provenance.costs_hash == costs_hash(symbol, cfg)`. Test:
  `test_wfa_provenance_trae_costs_hash`.
- E14.3 DADO dos corridas que difieren solo en `spread_ticks` de la fila ENTONCES sus
  `provenance.costs_hash` difieren.
- E14.4 DADO `RunProvenance(...)` construido sin `costs_hash` ENTONCES `TypeError`.
- E14.5 DADO `python -c "import inspect; from genesis.validation.wfa import run_wfa;
  print(list(inspect.signature(run_wfa).parameters))"` ENTONCES la lista es `['candidate_id',
  'symbol', 'frame', 'firm_profile', 'exit_geometry', 'figure', 'funnel_config', 'costs_config',
  'news_events', 'dataset_store', 'tick_store', 'starting_balance', 'window_config',
  'grid_config', 'candidate_factory', 'seed']` (la actual, sin cambios).

**R15 — `compute_trial_id` incluye los costos.** *(Modifica R4 (#53); incorpora E2.)*
`compute_trial_id` (`validation/trial_ledger.py:115-147`) DEBE ganar el parámetro **obligatorio**
`costs_hash_by_symbol: Mapping[str, str]` y DEBE incluirlo en el diccionario canónico bajo la clave
`"costs_hash_by_symbol"`. `trial_ledger.py` sigue siendo solo `stdlib` más `genesis.validation.errors`
y sin importar de capas 1-3: recibe cadenas, nunca una `CostsConfig`. El mapa DEBE cubrir **los
símbolos evaluados en la corrida** (mismas claves que `dataset_hash_by_symbol`), de modo que cambiar
una fila de un símbolo **no evaluado** no altere ningún `trial_id`. La función `costs_hash` es la
única derivación sancionada de cada valor.

- E15.1 DADO dos llamadas idénticas salvo `costs_hash_by_symbol={"MNQ": h1}` contra `{"MNQ": h2}`
  ENTONCES `trial_id` distintos.
- E15.2 DADO dos llamadas idénticas salvo el orden de inserción del mapa ENTONCES mismo `trial_id`.
- E15.3 DADO dos configuraciones de costos que difieren solo en `source_url`/`read_on` de `MNQ`
  ENTONCES el `trial_id` de una corrida sobre `MNQ` es idéntico (la cita no es otro ensayo).
- E15.4 DADO dos configuraciones que difieren solo en la fila de `MGC` ENTONCES el `trial_id` de una
  corrida solo sobre `MNQ` es idéntico.
- E15.5 DADO `compute_trial_id` sin el parámetro nuevo ENTONCES `TypeError`.
- E15.6 (propiedad, `hypothesis`) DADO cualquier mapa de hashes ENTONCES determinismo y sensibilidad a
  cada valor. Tests en `tests/validation/test_trial_ledger.py`.

**R16 — El ledger de ensayos registra los costos.** *(Modifica R2 (#53); incorpora E2.)*
`TrialIdentityContext` (`trial_ledger.py:300-310`) y `TrialRecord` (`:56-76`) DEBEN ganar
`costs_hash_by_symbol: Mapping[str, str]`, obligatorio; `_REQUIRED_FIELDS` (`:32`) DEBE incluirlo;
`append_trial` DEBE escribirlo en la fila JSONL (claves ordenadas, separadores compactos, R19 de
#53); `TrialLedger.build_record` y `trial_id_for_config` DEBEN usarlo. `TrialIdentityContext` DEBE
rechazar con `TrialLedgerConfigError`, citando los símbolos sobrantes o faltantes, un
`costs_hash_by_symbol` cuyas claves no coincidan con las de `dataset_hash_by_symbol` (si un símbolo
quedara sin costos en la identidad, el ensayo no distinguiría esa fila). Una fila persistida **sin**
`costs_hash_by_symbol` DEBE ser rechazada por `read_trial_summary` con el fail-fast ya existente
(nombrando la clave): **no hay lectura retrocompatible**, para no mezclar ensayos de antes y después
de los costos por instrumento. `trial_ledger.CONFIG_VERSION` DEBE subir de
`"genesis-validation-trial-ledger/1"` a `"genesis-validation-trial-ledger/2"` (la identidad cambió de
definición). `ledger/trials.jsonl` tiene 0 bytes (verificado) y no tiene historia salvo el commit
inicial de #53, así que no hay filas que migrar ni archivar.

- E16.1 DADO un `TrialRecord` con `costs_hash_by_symbol` CUANDO `append_trial` y `read_trial_summary`
  ENTONCES la fila contiene la clave y se lee sin error.
- E16.2 DADO una línea JSONL sin `costs_hash_by_symbol` ENTONCES `TrialLedgerConfigError` que nombra
  la clave.
- E16.3 DADO `dataset_hash_by_symbol={"MNQ": ..., "MGC": ...}` y `costs_hash_by_symbol={"MNQ": ...}`
  CUANDO se construye `TrialIdentityContext` ENTONCES `TrialLedgerConfigError` citando `MGC`.
- E16.4 (el escenario que motiva E2) DADO un ledger con un ensayo del candidato X sobre los datos D
  con `costs_hash_by_symbol={"MNQ": h1}` CUANDO se registra el mismo candidato sobre los mismos datos
  con `{"MNQ": h2}` ENTONCES `read_trial_summary(...).n_trials_total == 2` (antes habría quedado en 1,
  porque `append_trial` descarta en silencio un `trial_id` repetido, `trial_ledger.py:264-277`).
- E16.5 DADO `rg -n "trial-ledger/2" src/genesis/validation/trial_ledger.py` ENTONCES ≥ 1 coincidencia.

**R17 — El manifiesto declara los costos.** *(Modifica R98 y R100 (#14); R15 (#53) lo exige por
paridad.)* `verdict_result_to_manifest_json` (`verdict.py:1335`) y `write_verdict_artifacts`
(`verdict.py:1411`) DEBEN recibir `costs_hash_by_symbol` (obligatorio, justo después de
`house_rule_hash`) y el manifiesto DEBE llevarlo como clave de primer nivel `"costs_hash_by_symbol"`.
`verdict.CONFIG_VERSION` DEBE subir de `"genesis-validation-j/3"` a `"genesis-validation-j/4"`, con la
entrada correspondiente en el docstring de versiones (patrón de #109 y #130). Sin esto un veredicto
publicado no diría con qué costos se corrió, y el repo es público a propósito (lo pre-registrado queda
fechado).

- E17.1 DADO un `VerdictResult` y `costs_hash_by_symbol={"SYM_A": "abc"}` CUANDO se serializa
  ENTONCES el JSON trae `"costs_hash_by_symbol": {"SYM_A": "abc"}` en el primer nivel.
- E17.3 (H4) El manifiesto DEBE llevar además la clave de primer nivel `"friction_status_by_symbol"`
  (mismas claves que `costs_hash_by_symbol`; valor: el `friction_status` de la fila de cada símbolo,
  hoy `provisional_hasta_b4b`). Esta clave **no entra** a `compute_trial_id`: describe la calidad de
  la fuente, no lo que se simuló (mismo criterio que R13). DADO un manifiesto serializado con la
  configuración empaquetada ENTONCES trae `"friction_status_by_symbol": {"MNQ":
  "provisional_hasta_b4b"}`.
- E17.2 DADO `rg -n 'genesis-validation-j/4' src/genesis/validation/verdict.py` ENTONCES ≥ 1 y
  `rg -n 'genesis-validation-j/3' src tests` ENTONCES 0. *(Los dos tests que fijan `/3`,
  `test_verdict.py:1413` y `:1636`, se migran.)*

**R18 — Propagación en `scripts/run_pipeline.py`.** *(Incorpora E2; corrige la propuesta, que daba
los scripts por intactos.)* El runner DEBE leer `provenance.costs_hash` de la `RunProvenance` que
`run_wfa` ya produjo (mismo patrón que `exit_geometry_hash`/`house_rule_hash`,
`run_pipeline.py:397-400`) y construir `costs_hash_by_symbol = {args.symbol: <ese hash>}` con la
**misma clave** que `dataset_hash_by_symbol` (`:485`), pasándolo a `TrialIdentityContext` (`:493`) y a
`write_verdict_artifacts` (`:539`). NO DEBE cambiar ninguna opción de CLI ni la firma de ninguna
función; el cambio es de unas pocas líneas del cuerpo de `main()`. `scripts/bench_simulator.py` NO
cambia.

- E18.1 DADO el runner tras `apply` CUANDO `rg -n "costs_hash_by_symbol" scripts/run_pipeline.py`
  ENTONCES ≥ 2 coincidencias (identidad y manifiesto) y `rg -n "provenance\.costs_hash"
  scripts/run_pipeline.py` ENTONCES ≥ 1.
- E18.2 DADO `git diff --stat -- scripts/bench_simulator.py` ENTONCES vacío; y `rg -n "add_argument"
  scripts/run_pipeline.py` ENTONCES el mismo número de opciones que en `b0f2950`.

### Tests

**R19 — Tests existentes: tabla de costos de test, explícita.** *(Mapea proposal «Plan de tests».)*
Los tests que simulan con símbolos de CFD o sintéticos (conteo de `symbol="..."` en
`tests/backtest`, `tests/validation` y `tests/strategy/candidate_b`: `US500` ×52, `NAS100` ×14,
`SYM_A` ×5, `XAUUSD` ×2, `US30`, `SYM_B`, `SYM_C`, y `NOPE` ×1, que solo ejerce el error de sesión)
DEBEN recibir una **tabla de costos de test explícita**, con
fila para cada símbolo con el que algún test construye un `Simulator`, y con `source_url` de host
reservado (`*.invalid`) que la marque como de test. Esa tabla NO DEBE entrar al paquete ni a ningún
módulo de `src/`. Los dos conftest (`tests/backtest/conftest.py:53-55`,
`tests/validation/conftest.py:66-68`) y los archivos que llaman `load_costs_config()` sin ruta DEBEN
dejar de usar el recurso empaquetado. Los valores de la tabla de test DEBEN elegirse de modo que
ningún test existente cambie de resultado esperado; si alguno lo hace, se re-basa explícitamente y se
lista en el reporte de `apply`. La ubicación de la tabla (JSON de test cargado con
`load_costs_config(path)`, que además ejercita el cargador real, o módulo auxiliar) es de `design`.
Verificado: ningún test de `tests/backtest/` ni de `tests/validation/` simula `BTCUSDT`
(`test_prop_sim.py:679` solo lo usa como clave de un ledger armado a mano).

- E19.1 DADO el árbol tras `apply` CUANDO `rg -ln "load_costs_config\(\)" tests` ENTONCES los únicos
  archivos son los de pruebas del propio cargador y del JSON empaquetado
  (`tests/backtest/test_costs*.py`).
- E19.2 DADO `mise run test` ENTONCES verde, con las únicas diferencias de aserción listadas en
  R20 y en los tests adaptados de `test_costs.py` (`:36`, `:47-49`, `:61-64`, `:67-70`, `:85-95`).
- E19.3 DADO `rg -n "1\.5|7\.0|0\.2" src/genesis/backtest/costs.py
  src/genesis/backtest/costs_config.json` ENTONCES 0 coincidencias (los tres valores heredados de los
  CFDs no sobreviven en ninguna parte del paquete). *(Hoy da 3, todas en el JSON.)*

**R20 — Reescritura del test A7.** *(Mapea proposal «Riesgos» 1; punto 8.)* El test
`test_costo_de_entrada_usa_value_per_point` (`tests/backtest/test_simulator_money_conversion.py:101-136`)
DEBE reescribirse. **No es un test que se debilita; es un test que ya no puede afirmar lo que
afirmaba, y se lo reemplaza por aserciones más estrictas del mismo invariante.**

*Lo que afirmaba.* Que el `cost_applied` de la entrada **difiere** entre una ficha
`(tick_value=1, tick_size=1)` y otra `(1, 0.01)`. Eso era consecuencia de que el spread y el
deslizamiento estaban en **puntos globales** y se multiplicaban por `value_per_point`
(`tick_value / tick_size`), así que cambiar `tick_size` cambiaba el dinero.

*Por qué ya no vale.* Con costos en **ticks**, el dinero es `ticks · tick_size · (tick_value /
tick_size) = ticks · tick_value`, independiente de `tick_size`. Las dos fichas dan el mismo costo y el
`!=` falla **porque el cambio funciona**, no porque algo esté roto.

*Qué sigue cubierto, sin tocar.* El invariante de fondo de #55 («la conversión punto → dinero usa
`value_per_point` y nunca `tick_value` crudo») lo prueban `test_pnl_flotante...` (A6) y
`test_pnl_realizado_usa_la_misma_conversion_que_el_flotante` (H2): el P&L sigue en puntos y esos dos
tests no cambian.

*Qué lo reemplaza (más fuerte que `!=`).*

- E20.1 DADO una fila de test y fichas `(tick_value=1.0, tick_size=1.0)` y `(1.0, 0.01)` CUANDO se
  abre una posición con cada una ENTONCES `entrada.cost_applied` es **igual** (`approx`) en las dos.
- E20.2 DADO fichas `(1.0, 1.0)` y `(2.0, 1.0)` ENTONCES `entrada.cost_applied - comisión_de_pata` de
  la segunda `== approx(2 *` el de la primera) (la fricción escala con `tick_value`).
- E20.3 Cobertura de la regresión original: si alguien volviera a convertir con `tick_value` crudo, la
  ficha `(1.0, 0.01)` daría una fricción 100 veces menor que la `(1.0, 1.0)` y E20.1 fallaría.

El test se renombra `test_costo_de_entrada_escala_con_tick_value_no_con_tick_size`. Verificación:
`git diff -U0 -- tests/backtest/test_simulator_money_conversion.py` solo toca esa función (y, si
hace falta, el helper `_simulator`); las funciones A6 y H2 conservan su cuerpo.

**R21 — Goldens.** *(Mapea criterios 3 y 7; punto 7.)* DEBEN existir, **a nivel de función**
(`MNQ` no está en `SESSIONS`, `sessions.py:45-74`, así que un golden por `Simulator` no es posible):

- comisión de **MNQ `== 1.90`** y de **MGC `== 2.20`** como suma de apertura y cierre (E5.1, E5.2),
  con la configuración empaquetada y aserción `==`. Es exacto: `x/2 + x/2 == x` en coma flotante para
  las cinco cifras de T1 (verificado por cálculo);
- spread de MNQ `== 0.25` puntos `== $0,50` y deslizamiento de MNQ `== 0.25` puntos `== $0,50` por
  pata (E6.2, E7.1);
- **golden compuesto** (E21.1): DADO la ficha de E6.2 y la configuración empaquetada CUANDO se compone
  a mano `commission_for(apertura) + commission_for(cierre) + (spread_for + 2·slippage_for) ·
  value_per_point` ENTONCES `approx(3.40)`. Test: `test_golden_mnq_costo_total_ida_y_vuelta`.

### Documentación

**R22 — Docs dentro del change.** *(Mapea criterio 11; punto 9.)* Las ediciones van en `docs/`,
`.serena/memories/` y `ledger/README.md` (vía rápida, pero dentro de este change). Cada una se
verifica por texto, no por número de línea, porque `ROADMAP_ARQUITECTO.md` y el spec v1.5 ya
cambiaron de líneas desde que se escribió la propuesta (§9).

1. **Roadmap** (`docs/ROADMAP_ARQUITECTO.md`): corregir las **dos** frases que dicen «cuatro veces»
   sobre costos —en B.4 (hoy `:1221-1223`) y en el resumen del carril B (hoy `:192-193`)— porque
   contaban una sola pata. El texto nuevo dice que **la comisión sola es 7,4 veces lo publicado**
   ($14 contra $1,90) y que la fricción total del MNQ era ≈$17,40; registra el **doble cobro** como
   hallazgo; y, si el dueño aprueba la interpretación de «la ficha» (§8 H2), aclara el punto (1) del
   DoD de B.4a como «tabla de costos por instrumento en capa 3».
   - E22.1 `rg -nU "cuatro veces\s+(de más|mayores)" docs/ROADMAP_ARQUITECTO.md` ENTONCES 0.
     *(Con `-U`: una de las dos frases parte el renglón entre «veces» y «mayores». Hoy da 2
     coincidencias, en `:192-193` y `:1223`.)*
   - E22.2 `rg -n "doble cobro" docs/ROADMAP_ARQUITECTO.md` ENTONCES ≥ 1; `rg -n "7,4"` ≥ 1;
     `rg -n "17,40"` ≥ 1.
2. **Spec v1.5** (`docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`): (a) la fila de §11.1
   `PA-106-C` (hoy `:1530`) pasa al formato de cierre que ya usa PA-106-A
   (`~~**PA-106-C — ...**~~ **CERRADA (B.4a, #135, <fecha>)**`), con la fuente, la fecha de lectura
   `2026-10-02`, y la salvedad **«spread y deslizamiento siguen provisionales hasta B.4b»**, más lo que
   el dueño haya declarado sobre el alcance de «Total Cost Round Trip» (R23); (b) la fila
   «Comisiones por contrato: no verificado» de la tabla de la firma (hoy `:316`) deja de decir «no
   verificado» y cita la fuente.
   - E22.3 `rg -n "~~\*\*PA-106-C" docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md` ≥ 1, y esa
     línea contiene `CERRADA`, `provisionales hasta B.4b` y `9735811`.
   - E22.4 `rg -n "Comisiones por contrato.*no verificado" docs/SPEC_GENESIS_v1.5_PropTrading_TorneoCandidatos.md`
     ENTONCES 0.
3. **Memoria de MFFU** (`.serena/memories/mffu-rapid-eod-50k-reglas-confirmadas.md`): reemplazar el
   «no publicadas en el help center» (hoy `:111-112`) y sacar «las comisiones por contrato» de
   «Sigue sin verificar» (hoy `:208-209`); anotar las cinco cifras, la URL y la fecha.
   - E22.5 `rg -n "no publicadas en el help center|las comisiones por contrato" <archivo>` ENTONCES 0;
     `rg -n "9735811" <archivo>` ≥ 1; y por cada fila de T1, `rg -n "<SIM>.*<cifra>" <archivo>` ≥ 1
     (`MNQ`/`1,90`, `MGC`/`2,20`, `MCL`/`1,16`, `M6E`/`1,44`, `MBT`/`3,50`).
4. **Memoria de cripto** (`.serena/memories/cripto-encaje-por-capa.md:27`): la afirmación «`costs.py`
   cobra `commission_per_lot`» queda obsoleta (el campo desaparece) y se reescribe con el modelo nuevo.
   - E22.6 `rg -n "cobra .commission_per_lot" .serena/memories/cripto-encaje-por-capa.md` ENTONCES 0.
5. **`ledger/README.md`**: agregar `costs_hash_by_symbol` a la lista de claves y un párrafo «Corte de
   Change #135» (patrón del «Corte de Change #109»): el ledger estaba vacío al corte, no hay nada que
   archivar y las filas sin la clave son ilegibles.
   - E22.7 `rg -n "costs_hash_by_symbol|Corte de Change #135" ledger/README.md` ENTONCES ≥ 2.
6. **No se editan** `.pulse/specs/**` (las actualiza el engine al cerrar), ni `CLAUDE.md`, ni
   `.pulse/specs/data/spec.md:954` (R146 de BTCUSDT menciona una `commission_per_lot` de perfil que no
   existe en `FirmProfile`; no se toca).

### Precondición de apply

**R23 — Firma humana de las cinco cifras.** *(Mapea la precondición de la propuesta; punto 10.)*
Antes de la **primera tarea que escriba `costs_config.json`** (la que introduce las cinco cifras),
DEBE existir `.pulse/changes/<slug>/firma-cifras.md` con:

- (a) las cinco filas de T1 con su `round_trip_usd`, **idénticas a T1 y al JSON**;
- (b) la URL y la **fecha en que el dueño releyó** la fuente (si es posterior a 2026-10-02, esa es la
  `read_on` del JSON);
- (c) la declaración del dueño sobre lo que cubre «Total Cost Round Trip» (si incluye comisión de la
  firma, tarifa de bolsa/clearing y NFA) y si es **uniforme** entre Tradovate, Rithmic y NinjaTrader
  (`ROADMAP:854-855`), o la frase «no confirmado»; esa declaración se copia a la clave `_nota` del
  JSON y al texto de cierre de PA-106-C (R22);
- (d) la línea `Firmado: <nombre>, <YYYY-MM-DD>, «<cita textual de su confirmación>»`.

El registro lo transcribe el hilo principal a partir de la confirmación explícita del dueño; ningún
agente de fase lo crea por iniciativa propia. **La aprobación del gate `DESIGN → APPLY` no sustituye
esta firma**: el proyecto ya reconoció (`CLAUDE.md`) que los gates se aprobaron sin leer cuando las
decisiones llegaban en un vocabulario ajeno. Por eso la firma es un artefacto aparte, en lenguaje
llano, con las cinco cifras a la vista. Si falta, `apply` se detiene en esa tarea y pregunta.

- E23.1 `fd firma-cifras.md .pulse/changes` ENTONCES existe en el directorio de este change.
- E23.2 `rg -n "^Firmado: .+, [0-9]{4}-[0-9]{2}-[0-9]{2}, «.+»$" <firma-cifras.md>` ENTONCES ≥ 1.
- E23.3 DADO las cinco filas de `firma-cifras.md` y las del JSON empaquetado CUANDO se comparan
  símbolo por símbolo ENTONCES coinciden en `round_trip_usd` y en `read_on`. Comando de `apply`/
  `review` (no de CI, porque el change se archiva y la ruta cambia):
  `rg -o "\| (MNQ|MGC|MCL|M6E|MBT) \| [0-9,]+ \|" <firma-cifras.md>` contra el JSON.

**R24 — Lo que NO cambia.** *(Mapea criterio 9 de la propuesta, corregido.)* Este change NO DEBE:

- modificar `src/genesis/data/**` (`SymbolFigure`, `ArtifactMetadata`, `FirmProfile`,
  `firm_profile_hash`, `SESSIONS`): E24.1 `git diff --stat main -- src/genesis/data` vacío;
- modificar `validation/dsr_pbo.py` ni `validation/sensitivity.py`: E24.2 `git diff --stat main --
  src/genesis/validation/dsr_pbo.py src/genesis/validation/sensitivity.py` vacío;
- cambiar la firma pública de `run_wfa` (E14.5), ni la de `run_dsr_pbo`/`run_sensitivity` (sin diff);
- cambiar `swap_for`, `exit_geometry`, `house_rule`, el embudo del Inspector ni `max_lot`;
- cambiar `genesis.backtest.__all__` salvo que `design` decida exportar `costs_hash` (en cuyo caso se
  actualiza `tests/backtest/test_public_api.py`, que fija ese conjunto);
- agregar `figure.symbol == symbol` ni ninguna otra guarda no pedida.

Y DEBE dejar `mise run ci` (ruff, bandit, vulture, deptry, ty, pytest) en verde: E24.3.

## 5. Modelo de datos

```
costs_config.json (capa 3, recurso empaquetado)           raíz: {"_fuente"?, "_nota", "instruments": {...}}
└── instruments: { "<SIMBOLO>": { round_trip_usd, spread_ticks, slippage_ticks,
                                  friction_status, source_url, read_on }, ... }   <- T1, 7 filas

CostsConfig (capa 3, frozen, hasheable)                   nombres propuestos; forma final = design
└── instruments: tuple[InstrumentCosts, ...]              ordenada por símbolo, única, no vacía
InstrumentCosts (capa 3, frozen)  = {symbol, round_trip_usd, spread_ticks, slippage_ticks,
                                     friction_status, source_url, read_on}   validada en construcción

costs_hash(symbol, config) -> str                         capa 3; sha256 de {c, sl, sp} (R13)
RunProvenance        (+ costs_hash: str)                  capa 3  (backtest/ledger.py)
compute_trial_id     (+ costs_hash_by_symbol)             capa 4  (solo recibe str)
TrialIdentityContext (+ costs_hash_by_symbol)             capa 4  (clave-coherencia con dataset_hash_by_symbol)
TrialRecord / ledger/trials.jsonl (+ costs_hash_by_symbol)
manifest.json        (+ costs_hash_by_symbol, verdict_schema_version "/4")
```

Dependencias (invariantes de capas de `CLAUDE.md`): `costs.py` (capa 3) importa de capa 1
(`symbols`) y solo `stdlib` para hash y validación (`hashlib`, `json`, `math`, `re`, `datetime`); no
importa `scipy`/`statsmodels`/`matplotlib`/`quantstats` (R41 (#6) se conserva).
`validation/trial_ledger.py` (capa 4) sigue siendo `stdlib` + `validation.errors`, sin importar de
capas 1-3: la huella le llega como `str`. `validation/wfa.py` y `verdict.py` ya importan de capa 3
(`CostsConfig`, `RunProvenance`); no se crea ninguna dependencia nueva hacia arriba.

Cobro por pata (R10), por contrato, `stress = 1`:

```
                 comisión        deslizamiento        spread        swap
entrada          c / 2           slip_ticks · tick_value   spread_ticks · tick_value   —
salida           c / 2           slip_ticks · tick_value   —                           como hoy (days_held >= 1)
```

## 6. Trazabilidad: criterios de la propuesta → requisitos → evals

| Criterio de la propuesta | Requisitos | Evals |
|---|---|---|
| 1. JSON con exactamente cinco filas de futuros CME (H1), comisiones de T1, fuente y `read_on`, 1+1 ticks provisionales | R1, R2 | E2.1, E2.2 |
| 2. `commission_per_lot`, `default_spread_points`, `slippage_points` no existen | R1 | E1.1 *(patrón corregido, §9)* |
| 3. Golden `==`: MNQ $1,90 y MGC $2,20 a nivel `commission_for` | R5, R21 | E5.1, E5.2, E5.3 |
| 4. `commission_for` sin fila lanza `BacktestConfigError` con símbolo y lista | R5, R9 | E5.6, E9.1 |
| 5. `Simulator` sin fila falla en `__init__` antes de la primera barra | R11 | E11.1-E11.5 |
| 6. `load_costs_config` rechaza cada caso (un test por caso) | R3 | E3.1-E3.4 |
| 7. `spread_for` conserva la rama de ticks y el fallback en ticks; golden MNQ | R6, R21 | E6.1-E6.4, E7.1 |
| 8. `stress` es multiplicador final de las tres | R8 | E8.1, E8.2 |
| 9. Contratos de `wfa.py`, `dsr_pbo.py`, `sensitivity.py` y scripts no cambian de firma | R14, R18, R24 | E14.5, E18.2, E24.1, E24.2 *(el runner sí cambia de cuerpo, §9)* |
| 10. `mise run ci` en verde | R24 | E24.3 |
| 11. Docs actualizados; cierre de PA-106-C dice «provisionales hasta B.4b» | R22 | E22.1-E22.7 |
| Precondición: firma del dueño | R23 | E23.1-E23.3 |
| **E1** (deslizamiento en las dos patas; sin rótulo «conservador») | R10, R7 | E10.1-E10.5 |
| **E2** (`costs_hash` por símbolo en `trial_id` y `RunProvenance`) | R13-R18 | E13.*, E14.*, E15.*, E16.*, E17.*, E18.* |
| **E3** (`CostsConfig` inmutable y hasheable) | R12 | E12.1-E12.4 |
| Riesgo 1 de la propuesta (A7) | R20 | E20.1-E20.3 |
| Plan de tests (fixture explícito) | R19 | E19.1-E19.3 |

## 7. Riesgos

1. **Rotura masiva de tests por la regla de falla (R19).** 35 archivos mencionan
   `CostsConfig`/`load_costs_config`/`costs_config`; la mayoría llega por los dos conftest. Se rompen
   a la vez, y no porque el cambio esté mal. Mitigación: tabla de test explícita (R19) y migración del
   helper, no parche por test. Aparte, `RunProvenance` se construye a mano en 7 archivos de tests
   (`tests/backtest/test_ledger.py:25`, `test_metrics.py:37`; `tests/validation/test_verdict.py:72`,
   `test_dsr_pbo.py:34`, `test_slow_volume_j.py:46`, `fakes.py:139`, `fixtures/ledgers.py:25`).
   En total, 27 sitios de 10 archivos de tests construyen o invocan alguno de los cuatro
   (`RunProvenance`, `compute_trial_id`, `TrialIdentityContext`, `TrialRecord`), entre ellos
   `tests/validation/test_trial_ledger.py` (13), `tests/strategy/genome/test_compiler.py` (3) y
   `tests/validation/fakes.py` (3). Todos ganan el campo nuevo a propósito, sin default (R14, R15,
   R16). Los dos tests que fijan `genesis-validation-j/3` y los que usan
   `genesis-validation-trial-ledger/1` (`tests/validation/fakes.py:33`) se migran.
2. **Cifras con firma pendiente (R23).** Se leyeron de una página que MFFU edita. Hasta la firma, el
   JSON no se escribe. El alcance de «Total Cost Round Trip» (bolsa/clearing/NFA) y su uniformidad
   entre plataformas son preguntas de un humano, no de esta fase.
3. **Spread y deslizamiento son un piso provisional (E1).** Cerrar PA-106-C verifica la **comisión**,
   no la fricción. Un GO emitido bajo `provisional_hasta_b4b` no dice «provisional» en ningún artefacto
   legible por máquina (ver §8 H4).
4. **El deslizamiento de salida se cobra también en las salidas por objetivo (límite).** En un mercado
   real un objetivo suele ejecutarse al precio o mejor. Cobrar el piso en toda salida es **pesimista
   para esa salida** (empuja hacia falsos negativos, el error barato de este proyecto) y evita decidir
   un modelo de fill que es de B.4b. Ver §8 H3.
5. **La ficha del símbolo no está en la identidad del ensayo.** Con costos en ticks, el dinero depende
   de `figure.tick_value` (`USD = ticks · tick_value`), y la ficha (`SymbolFigure`) no entra a
   `compute_trial_id`, que cubre barras, firma, geometría, regla de la casa y ahora costos. Es un
   hueco **preexistente** (hoy ya dependía de `value_per_point`); en un contrato CME el `tick_value` es
   una constante del contrato, así que el riesgo práctico es bajo. Queda anotado para B.2, que
   construirá las fichas.
6. **La identidad del ensayo es de la corrida, no del símbolo (hallazgo preexistente).**
   `record_trial_completions` llama `build_record(candidate_id, symbol, candidate_config, ...)`
   (`verdict.py:967-975`), pero `trial_id_for_config` ignora `symbol` (`trial_ledger.py:343-351`): un
   bundle multi-símbolo daría un único `trial_id` para todos sus símbolos y `append_trial` descartaría
   los siguientes. El único runner evalúa un símbolo por corrida, así que no se manifiesta hoy. Afecta
   la lectura de E2: «cambiar MGC no cambia el `trial_id` de MNQ» vale **entre corridas de un símbolo**
   (cada mapa cubre solo su símbolo); dentro de una corrida conjunta, el mapa de costos acopla a los
   símbolos igual que ya lo hace `dataset_hash_by_symbol`. No se corrige acá; se anota para B.8/el
   orquestador multi-símbolo.
7. **`bench_simulator.py` y `run_pipeline.py` sobre el store actual fallan** (todo CFD). Es el efecto
   buscado y está declarado en R11; el riesgo es que alguien lo lea como regresión.
8. **Desfase de las specs vivas.** R2/R4 (#53), R98/R100 (#14) y R45 (#6) enumeran `risk_profile_hash`,
   que #109 ya sustituyó. Este delta agrega su campo sin reescribir la enumeración; reparar esas
   líneas es de otro change.
9. **Líneas de docs movidas.** Roadmap y spec v1.5 cambiaron de líneas tras `94aba5a`; por eso R22 se
   verifica por texto.
10. ~~**`MES`/`MYM` en T1 aunque su compra se rechazó.**~~ Resuelto: fuera de T1 (§8 H1).

## 8. Preguntas

### Cerradas a nivel de spec (decisión y porqué)

| # | Pregunta | Decisión | Porqué |
|---|---|---|---|
| C1 | ¿Redondeo a centavos por pata? (propuesta 3; idea 4) | **No.** | Rompería `pata + pata == ida y vuelta` y la linealidad del `stress`; MFFU publica el costo ida y vuelta, no el de cada fill. Cada pata es la mitad exacta. |
| C2 | Formato de `read_on` y marca «provisional» (propuesta 4) | `read_on` = `YYYY-MM-DD` estricto (regex + fecha válida); marca = campo `friction_status` de conjunto cerrado `{provisional_hasta_b4b}`. | `date.fromisoformat` acepta `20261002` y `2026-W40-5` en 3.14.4 (verificado); un conjunto cerrado obliga a que B.4b amplíe el código a conciencia. |
| C3 | Orden de validaciones en `__init__` (propuesta 5) | Proveedor → tipo de config → sesión → **fila de costos** → `house_rule`. | El chequeo nuevo solo agrega errores donde antes se arrancaba; ningún mensaje previo cambia. Detalle en R11. |
| C4 | ¿Se tolera 0 tick de spread/deslizamiento en producción? (propuesta 6) | El cargador acepta `>= 0` sin distinguir producción de test; el **empaquetado** debe traer 1 y 1 (E2.1). | Un cargador no sabe en qué entorno corre; el test del paquete es el guardián. Los tests de «suma exacta = ida y vuelta» necesitan 0. |
| C5 | Clave del símbolo en CME (idea 5) | Coincidencia exacta con el `symbol` convencional que recibe el `Simulator`. El mapeo contrato → raíz es de B.3. | Es lo que ya usan `SESSIONS` y `dataset_hash_by_symbol`. |
| C6 | ¿Entra spread/deslizamiento por instrumento? (idea 6) | Sí, en ticks, con piso provisional; el deslizamiento en ambas patas (E1). | Corregir solo la comisión dejaría M6E en $18.750 de spread. |
| C7 | ¿Costos en la procedencia? (idea 7) | Sí (E2): R13-R18. | El ledger está vacío: es el único momento en que cuesta cero. |
| C8 | `source_url`/`read_on` en el hash (punto 6 del encargo) | **No entran.** | La cita no cambia lo que se simuló; contarla inflaría `n_trials`. Detalle en R13. |
| C9 | ¿`spread_for` falla con ticks y sin fila? | **Sí**, la fila se resuelve siempre. | La falla no debe depender de la cobertura de ticks de cada día. Refina el criterio 7 de la propuesta (mismo valor cuando la fila existe). |
| C10 | `MappingProxyType` vs tupla (E3) | Tupla ordenada de filas congeladas por defecto. | `hash(MappingProxyType({...}))` falla (verificado). La forma exacta queda en `design`. |
| C11 | Scripts: ¿se tocan? (idea 8; propuesta «Alcance OUT») | `bench_simulator.py` no; `run_pipeline.py` **sí**, solo el cuerpo (R18). | E2 obliga a que el runner pase la huella a `TrialIdentityContext` y al manifiesto. |
| C12 | Corrección del roadmap (idea 10) y memorias (idea 9) | Dentro del change (R22). | Vía rápida, pero la zona gris se resuelve a favor del gate. |
| C13 | Versiones | `verdict` `/3 → /4`; `trial_ledger` `/1 → /2`; `genesis-backtest/1` **no** sube. | Cada cambio de manifiesto subió la versión (#109, #130); `RunProvenance` ganó campos sin subirla (#109) y un test la fija. |

### Abiertas

| # | Quién | Pregunta | Recomendación |
|---|---|---|---|
| **H1** | ~~Humano~~ **Resuelta por el orquestador** | ¿Mantener MES y MYM en T1 o recortar a cinco? | **Cinco.** Ver la nota bajo T1. |
| **H2** | **Humano (gate de design)** | ¿La tabla de costos en capa 3 cumple «la ficha» del DoD, o exige `SymbolFigure`? (idea 1; propuesta 1) | **Recomendación: tabla en capa 3.** La comisión es de la firma, no del contrato, y así no se rompen los sidecars. La revisión independiente (agy) coincide. Si el dueño exige `SymbolFigure`, el dominio cambia a `data` y este spec se **reescribe**, no se parcha. Se aprueba con el design. |
| **H3** | ~~Humano~~ **Resuelta por el orquestador** | ¿Se cobra el deslizamiento de salida también en salidas por objetivo? | **Sí**, como piso uniforme hasta B.4b (R10, riesgo 4). Se aprueba con el design. |
| **H4** | ~~Humano / design~~ **Resuelta por el orquestador: entra** | ¿El manifiesto declara `friction_status` por símbolo? | **Sí.** Un veredicto tiene que decir por sí mismo que corrió con fricción provisional, sin que haya que abrir el JSON de costos: es el propósito del proyecto («dejar de creer que se sabe algo que no está validado»). Cuesta una clave más en el manifiesto, bajo el mismo `/4` (R17, E17.3). Se aprueba con el design. |
| **H5** | **Humano** | Alcance de «Total Cost Round Trip» (bolsa/clearing/NFA) y uniformidad entre plataformas (idea 2). | No la cierra ningún agente: va en la firma (R23 (c)). «No confirmado» es una respuesta válida. |
| D1 | Design | Nombres y forma de `InstrumentCosts`/`CostsConfig`; cómo se expone la consulta por símbolo y la lista de símbolos. | R12 fija solo el comportamiento. |
| D2 | Design | Ubicación de la tabla de test (JSON de test con `load_costs_config(path)` vs módulo auxiliar). | El JSON ejercita el cargador real. |
| D3 | Design | Redacción exacta de los mensajes de R9; si `costs_hash` se exporta en `genesis.backtest.__all__`. | Exportarlo sigue el precedente de `exit_geometry_hash`; obliga a tocar `test_public_api.py`. |
| D4 | Design | Dónde vive la guarda de coherencia de claves de R16 (`__post_init__` de `TrialIdentityContext`). | Ahí. |

## 9. Nota de verificación

**Líneas de `src/`**: todas las que citan `idea.md` y `proposal.md` coinciden con `b0f2950`:
`costs.py:24-30, 33-54 (:49 del; :50-51 ticks; :52-53 fallback), 57-59, 62-65, 68-85, 88-111`;
`costs_config.json:2-4`; `simulator.py:26 (import), 241-249 (docstring), 251-267 (firma), 271-277
(proveedor), 279-284 (tipo de config), 286-292 (sesión), 294-300 (house_rule), 328-336
(RunProvenance), 646-669 (apertura: spread :657, slippage :665, comisión :666, costo :668-669),
711-741 (cierre: comisión :717, swap :720-728, total :730)`; `ledger.py:96-111`;
`errors.py:27-34`; `trial_ledger.py:32, 56-76, 115-147, 264-277, 300-310, 343-351`;
`verdict.py:53, 949-977, 1335, 1411`; `wfa.py:433-462`; `symbols.py:35-47`.
Los llamadores de las tres funciones son solo `Simulator` (`simulator.py:657, 665, 666, 717`).

**Diferencias con la propuesta/idea (escritas contra `94aba5a`)**:

1. **Docs movidas por los PR #134/#136.** Roadmap: B.4 está hoy en `:1207-1259` (propuesta
   `:1202-1254`); «cuatro veces de más» en `:1221-1223` (propuesta `:1216-1218`); DoD de B.4a en
   `:1255-1259` (propuesta `:1250-1254`); hay **una segunda** frase sobre «cuatro veces mayores» en
   `:192-193` que la propuesta no listaba. Spec v1.5: PA-106-C en `:1530` (propuesta `:1491`); la fila
   de comisiones en `:316` sigue igual.
2. **Criterio 2 de la propuesta, mal formulado.** `rg` sobre `src/` por `slippage_points` encuentra la
   variable local `slippage_points` de `simulator.py:665-667`; el patrón correcto está en E1.1.
3. **`scripts/run_pipeline.py` sí se modifica** (E2 lo exige: el runner arma `TrialIdentityContext` en
   `:493` y llama `write_verdict_artifacts` en `:539`). La propuesta daba los scripts por intactos y
   su criterio 9 hablaba de «firmas»; las firmas se conservan, el cuerpo de `main()` cambia (R18).
4. **MES/MYM.** El roadmap rechazó comprar sus datos el 2026-10-02 (`:1379-1383`), después de que
   `idea.md` los incluyera «porque no cuestan nada». Va a H1.
5. **R109/R111 de #24** prohíben modificar `simulator.py`/`costs.py::spread_for`; son restricciones de
   alcance de ese change y se aclaran en §3.
6. **Specs vivas desfasadas** (`risk_profile_hash` en R2, R4 de #53; R98, R100 de #14; R45 de #6).
7. **Identidad de ensayo de la corrida y no del símbolo** (riesgo 6): matiza la motivación de E2.
8. **Comportamientos de la biblioteca estándar verificados en Python 3.14.4** y que condicionan las
   reglas de R3 y R12: `json.loads` acepta `NaN`/`Infinity` y resuelve claves duplicadas con el
   último; `date.fromisoformat` acepta `20261002` y `2026-W40-5`; `float(True) == 1.0`; el hash de
   `MappingProxyType` sobre un `dict` falla.

**Lectura independiente de la fuente primaria.** El 2026-10-02 se descargó
`https://help.myfundedfutures.com/en/articles/9735811` (solo lectura, sin guardar copia) y se
extrajo la tabla de la página: título «Futures Instrument List», fecha de actualización «August 24,
2026», columnas `Tick Size`, `Tick Value`, `Total Cost Round Trip`. Las siete cifras y los ticks de
T1 coinciden con `idea.md` (MNQ $1,90; MGC $2,20; MCL $1,16; M6E $1,44; MBT $3,50; MES $1,90; MYM
$1,90; NQ de referencia $4,68). **Esto es una segunda lectura de un agente; no sustituye la firma
del dueño (R23).**

**Aritmética verificada por cálculo**: `x/2 + x/2 == x` exacto para las siete cifras y para
`sizing_hint ∈ {1, 2, 3, 7, 10}`; `0.25 * 1.0 * (0.5 / 0.25) == 0.5` exacto; el hash de referencia de
E13.1 es el SHA-256 de la cadena canónica citada, calculado con la biblioteca estándar.

**Sin contradicciones de fondo** entre `proposal.md` (con E1-E3) y el código verificado, salvo las
diferencias 2, 3 y 7 de arriba.
