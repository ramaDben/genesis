
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
