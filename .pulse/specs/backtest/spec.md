
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
