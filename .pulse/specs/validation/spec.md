
<!-- change:10-h-feat-validation-wfa-grid-is-dsr-is-wfe-monte-carlo-s-mbolo-y-p -->
<!-- change:10-h-feat-validation-wfa-grid-is-dsr-is-wfe-monte-carlo-s-mbolo-y-p -->
# Specification: WFA (grid IS, DSR-IS, WFE) + Monte Carlo (símbolo y portafolio) (Issue #10 / H)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §6, §6.1,
§6.2, §7.1, §7.6, §8, §9, §11, §11.1 (PA-5), §11.2. Este documento formaliza `idea.md` y
`proposal.md` de este Change en requisitos verificables. Los gates G/C/P/T del spec **nunca se
relajan**; ningún requisito de este documento puede contradecirlos. Este Change **no** calcula
ningún gate — produce los insumos mecánicos y reproducibles que Issues I/J consumirán.

Convención de rutas: el spec usa pseudocódigo `python/validation/...` (§6); el repo real usa
`src/genesis/validation/...` (`[project] name = "genesis"` en `pyproject.toml`). Todas las rutas de
este documento son las reales del repo.

Este Change resuelve las 6 tensiones ya identificadas en `proposal.md` (grid exhaustivo, DSR-IS
propio y reutilizable, sin `scipy`, runs reanudables diferidos, persistencia en memoria, loop
secuencial) y fija con criterios ejecutables los 6 riesgos que `proposal.md` dejó explícitamente
pendientes para esta fase (§3 de este documento).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Construir la capa 4 mínima del camino crítico (`src/genesis/validation/`): el walk-forward rolling
con grid IS exhaustivo y selección por DSR-IS (`wfa.py`), el motor de Monte Carlo por símbolo y de
portafolio (`montecarlo.py`), y los módulos de soporte (`errors.py`, `window_config.py`, `_dsr.py`).
Esto consume la API pública ya cerrada de `genesis.data`, `genesis.strategy` y `genesis.backtest`
sin modificar ninguno de los tres árboles, y produce el OOS cosido, el WFE, el conteo mecánico de
trials (9/27) y las distribuciones Monte Carlo que Issue I (`purged_cv.py`, `dsr_pbo.py`,
`sensitivity.py`) e Issue J (`prop_sim.py`, `verdict.py`) necesitan como insumo — sin ellos, el
camino crítico A → B → C → {E, G} → H → I → J se detiene en H (spec §11).

### 1.2. Alcance IN

- `src/genesis/validation/errors.py`: `GenesisValidationError` (raíz propia), `WfaConfigError`,
  `MonteCarloConfigError`.
- `src/genesis/validation/window_config.py`: `WfaWindowConfig`, `GridConfig`, constantes del grid
  (§6.2 del spec), `window_identity_hash`.
- `src/genesis/validation/_dsr.py`: `deflated_sharpe_ratio` (módulo interno, sin exportar en
  `__init__.__all__`), `_standard_normal_cdf`, `_standard_normal_ppf`.
- `src/genesis/validation/wfa.py`: `run_wfa`, `WfaResult`, `WindowResult`.
- `src/genesis/validation/montecarlo.py`: `monte_carlo_symbol`, `monte_carlo_portfolio`,
  `McPathsResult`, `McSymbolResult`, `McPortfolioResult`.
- `src/genesis/validation/__init__.py`: `__all__` mínimo y curado (patrón
  `src/genesis/backtest/__init__.py`).
- `tests/validation/`: `conftest.py`, `fixtures/`, tests planos, replicando el patrón de
  `tests/backtest/`.
- Test de propiedad de determinismo total (misma semilla + dataset + config ⇒ resultado
  bit-idéntico), test de propiedad de techo de 27/9 trials, test de propiedad anti-lookahead a
  nivel de ventana WFA (spec §9).

### 1.3. Alcance OUT (YAGNI explícito)

- Gates G/C/P/T (`verdict.py`, evaluación de umbrales) — Issue J. Este Change produce los números
  (WFE, curva OOS cosida, distribuciones MC); no compara contra ningún umbral del spec §7.
- DSR/PBO completo vía CSCV (`dsr_pbo.py`), deflación de torneo (T1), Purged K-Fold con embargo
  (`purged_cv.py`), sensibilidad (`sensitivity.py`) — Issue I. `_dsr.deflated_sharpe_ratio` de este
  Change es un módulo interno usado exclusivamente para seleccionar dentro del grid IS; no es la
  implementación normativa del gate G4/T1.
- `prop_sim.py`, `verdict.py`, tearsheet, manifest reproducible con un comando — Issue J.
- Modificación de cualquier archivo bajo `src/genesis/data/`, `src/genesis/strategy/` o
  `src/genesis/backtest/`: `git diff --stat -- src/genesis/data src/genesis/strategy
  src/genesis/backtest` DEBE quedar vacío (R61, patrón heredado de Issue G).
- Dependencias de runtime nuevas (`scipy`, `statsmodels`, `matplotlib`, `quantstats`): el término
  de corrección del DSR-IS (`Φ⁻¹`) se implementa con `math.erf` + `numpy` puro (Decisión 3 del
  proposal); quedan explícitamente diferidas a Issue I (PBO vía CSCV).
- Runs reanudables por hash de insumos (caché en disco de ventanas WFA, spec §8): este Change
  produce un `window_identity_hash` determinista por ventana (insumo para una extensión futura),
  pero **no** implementa la capa de caché/resume — sin especificación normativa de formato,
  ubicación ni política de invalidación (mismo criterio que aplicó Issue G para diferir la CLI
  unificada).
- Serialización a disco de los artefactos de WFA/MC (`WfaResult`, `McSymbolResult`,
  `McPortfolioResult`): en memoria, dataclasses puras, consumibles en el mismo proceso por I/J. El
  manifest reproducible con un comando es responsabilidad explícita de `verdict.py` (Issue J).
- Paralelismo (`multiprocessing`/`concurrent.futures`): loop secuencial en este Change; los tests
  de volumen realista se marcan `pytest.mark.slow`.
- CLI (`wfa`, `mc` de la tabla de CLI del spec §6): este Change entrega funciones puras/programables
  (`run_wfa`, `monte_carlo_symbol`, `monte_carlo_portfolio`); la superficie de CLI unificada queda
  diferida (mismo criterio que Issue G, sin caso de uso verificable en este Change).
- Orquestación multi-símbolo/multi-candidato en un único comando (bucle que llama `run_wfa` por
  cada símbolo del universo del candidato y agrega los `Ledger` OOS resultantes para
  `monte_carlo_portfolio`): responsabilidad del código consumidor (Issue I/J o un script
  exploratorio), no de `wfa.py` en este Change — `run_wfa` opera sobre un único `(candidate_id,
  symbol)` por invocación (spec §7.1: los gates G se evalúan por símbolo).
- Cualquier candidato distinto de B: el grid IS de 27/9 y las constantes de `window_config.py` son
  específicas del Candidato B (único implementado); un candidato futuro con más parámetros/niveles
  requiere un Change propio que actualice el spec (§6.2: "no se puede superar el presupuesto...
  sin actualizar este spec").

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **NO DEBE**, numerados `R1..Rn`, cada uno verificable por
  al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones/constantes son **normativos** (deben existir exactamente
  con ese nombre, verificable por `rg`); firmas exactas (tipos de parámetros, orden, valores por
  defecto no fijados aquí) se resuelven en `design.md` respetando el comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español (convención del repo).
- "Trades OOS" = deltas de `FillRecord.equity_after` entre `FillRecord`s consecutivos del ledger,
  filtrados a `is_exit=True` (mismo patrón, sin R-número específico, ya documentado en
  `genesis.backtest.metrics`). `wfa.py`/`montecarlo.py` implementan su **propia** función interna
  de extracción (`_extract_exit_returns`) replicando ese patrón, sin importar el símbolo privado
  `genesis.backtest.metrics._exit_deltas` ni modificar ese archivo (R61).
- `RunProvenance` (`genesis.backtest.ledger.RunProvenance`) se **reutiliza** como ficha de
  procedencia de los artefactos de esta capa (`candidate_id, config_version, dataset_hash,
  firm_profile_hash, risk_profile_hash`), en vez de inventar un esquema de metadata paralelo — el
  `config_version` propio de este Change (`"genesis-validation/1"`) se registra aparte, en el
  `WfaResult`/`McSymbolResult`, distinguible del `config_version` de la capa 3 dentro del
  `RunProvenance` embebido.

---

## 3. Resolución de las decisiones abiertas de `proposal.md`

`proposal.md` (§"Riesgos que specify debe acotar") dejó 6 decisiones sin cerrar. Esta sección fija
la resolución normativa de cada una; los requisitos que la formalizan viven en la §4.

| # | Decisión pendiente | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | Ancho de ventana IS/OOS y paso (rolling vs. anclado/expanding) | Esquema único, no expandible, para todos los símbolos del Candidato B: `IS_WINDOW_TRADING_DAYS = 252` (~12 meses bursátiles), `OOS_WINDOW_TRADING_DAYS = 126` (~6 meses), `STEP_TRADING_DAYS = 126` (= ancho OOS ⇒ ventanas OOS contiguas, sin solape ni huecos, cosidas sin ambigüedad). Rolling (la ventana IS se desplaza, no se expande). Alineación a `trading_day`, no a fechas naive. | R6-R13 |
| 2 | Precisión numérica de `Φ⁻¹` sin `scipy` | Algoritmo de Acklam (aproximación racional en tres tramos) + un paso de refinamiento de Halley sobre `math.erf`, verificado con criterio de ida y vuelta (`Φ(Φ⁻¹(p)) ≈ p`) y contra valores de referencia publicados de la normal estándar (sin importar `scipy`, ni en producción ni en tests). Tolerancia fijada en R17-R18. | R14-R18 |
| 3 | Métrica exacta de WFE | `WFE = sharpe_pointwise(oos_cosido) / mean(sharpe_pointwise(ganador_IS) por ventana)`, reutilizando `genesis.backtest.metrics.sharpe_pointwise` (pública, sin duplicar fórmula) sobre el `Ledger` OOS cosido y sobre el `Ledger` IS de la combinación ganadora de cada ventana. | R30-R31 |
| 4 | `block_size` del block bootstrap (símbolo y portafolio) | Símbolo: `block_size = clip(round(n_trades ** (1/3)), 5, 60)` (regla de longitud de bloque estándar de bootstrap por bloques, calibrable vía parámetro explícito que sobrescribe el default). Portafolio: default `block_size = 5` días de trading (una semana bursátil), también sobrescribible. | R42-R43, R47 |
| 5 | Umbral de trades insuficientes por combinación IS | `MIN_TRADES_IS = 10` trades OOS-de-selección (IS) por configuración de señal. Combinaciones con `n < MIN_TRADES_IS` reciben DSR-IS `= -inf` (excluidas de la selección, sin abortar la ventana); si las 9 configuraciones de señal de una ventana quedan todas por debajo del umbral, se lanza `WfaConfigError` (ventana inviable, fail-fast tipificado). | R26-R27 |
| 6 | Extensión futura hacia runs reanudables (hash determinista por ventana) | `window_identity_hash(candidate_id, symbol, dataset_hash_is, dataset_hash_oos, grid_config_hash, config_version) -> str` (sha256 sobre JSON canónico ordenado, patrón `risk_profile_hash`), calculado y expuesto en `WindowResult` pero **no** persistido a disco en este Change. | R12-R13, R29 |

Adicionalmente, `proposal.md` fijó (sin dejarlas abiertas, pero requiriendo formalización aquí):
grid exhaustivo 27/9 (R19-R25), DSR-IS propio en módulo interno (R14-R21), sin nuevas dependencias
de runtime (R63), loop secuencial + marcador `slow` (R32, R56), persistencia en memoria (R28,
R41).

---

## 4. Requisitos por módulo

### 4.1. `errors.py` — jerarquía de excepciones propia de la capa 4

- **R1** (DEBE). `errors.py` DEBE definir `GenesisValidationError(Exception)` como raíz propia de
  la jerarquía de `genesis.validation`. NO DEBE heredar de `GenesisBacktestError`,
  `GenesisStrategyError` ni `GenesisDataError` (sin raíz `GenesisError` compartida entre capas,
  mismo criterio que ADR-C4/ADR-G5).
- **R2** (DEBE). `errors.py` DEBE definir `WfaConfigError(GenesisValidationError)` para: (a)
  historia insuficiente para al menos una ventana completa IS+OOS (`IS_WINDOW_TRADING_DAYS +
  OOS_WINDOW_TRADING_DAYS` días de trading disponibles en el frame); (b) grid/niveles fuera del
  presupuesto de §6.2 (más de 27 combinaciones de ejecución o más de 9 de señal); (c) las 9
  configuraciones de señal de una ventana por debajo de `MIN_TRADES_IS` (decisión 5, §3).
- **R3** (DEBE). `errors.py` DEBE definir `MonteCarloConfigError(GenesisValidationError)` para:
  `n_paths <= 0`, `block_size <= 0`, o un `Ledger`/mapa de ledgers vacío pasado a
  `monte_carlo_symbol`/`monte_carlo_portfolio`.
- **R4** (DEBE). Todo mensaje de excepción nueva de este Change DEBE incluir contexto explícito
  (`candidate_id`, `symbol`, índice de ventana, valor involucrado) — fail-fast con contexto (spec
  §8).
- **R5** (DEBE). `errors.py` NO DEBE definir ninguna excepción que envuelva silenciosamente
  `BacktestConfigError`/`SessionBoundaryError` de la capa 3: estas se propagan sin capturar cuando
  ocurren durante un `Simulator.run` invocado desde `wfa.py` (fail-fast, sin degradar el tipo).

### 4.2. `window_config.py` — geometría de ventanas y presupuesto de grid

- **R6** (DEBE). `window_config.py` DEBE definir las constantes de módulo `IS_WINDOW_TRADING_DAYS
  = 252`, `OOS_WINDOW_TRADING_DAYS = 126`, `STEP_TRADING_DAYS = 126` (decisión 1, §3), usadas como
  default de `WfaWindowConfig` cuando el llamador no las sobrescribe explícitamente.
- **R7** (DEBE). `window_config.py` DEBE definir `WfaWindowConfig` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `is_window_trading_days: int`, `oos_window_trading_days: int`,
  `step_trading_days: int`. DEBE validar en construcción (`__post_init__`) que los tres valores son
  enteros positivos; en caso contrario, lanza `WfaConfigError`.
- **R8** (DEBE). `wfa.py` DEBE calcular la frontera de cada ventana IS/OOS a partir de la lista
  ordenada y sin duplicados de `trading_day` observados en una única pasada de `iter_bars(frame,
  symbol, firm_profile)` sobre el frame completo (lectura de planificación, forward-only, sin
  reposicionar cursor, spec R32 heredado de B) — NUNCA a partir de fechas de calendario naive ni de
  una reimplementación paralela de `_trading_day`.
- **R9** (DEBE). Cada ventana `k` DEBE cubrir, en `trading_day` consecutivos de la lista de R8:
  `[k·STEP : k·STEP + IS_WINDOW]` para el tramo IS y `(k·STEP + IS_WINDOW : k·STEP + IS_WINDOW +
  OOS_WINDOW]` para el tramo OOS contiguo, sin solape entre el tramo IS y el tramo OOS de la misma
  ventana, ni entre el tramo OOS de la ventana `k` y el tramo OOS de la ventana `k+1` (decisión 1,
  §3: `STEP_TRADING_DAYS == OOS_WINDOW_TRADING_DAYS` por default).
- **R10** (DEBE). El tramo IS y el tramo OOS de cada ventana DEBEN construirse troceando el
  `pd.DataFrame` crudo por rango de la columna `timestamp` (usando los límites UTC de los
  `trading_day` de frontera resueltos en R8) **antes** de invocar `iter_bars` para ejecutar
  cualquier combinación del grid o el run OOS — `iter_bars` es forward-only y no admite
  reposicionamiento de cursor (idea.md, contexto de `genesis.data.store`).
- **R11** (NO DEBE). `run_wfa` NO DEBE producir ninguna ventana si el número total de `trading_day`
  distintos de R8 es menor que `IS_WINDOW_TRADING_DAYS + OOS_WINDOW_TRADING_DAYS`: DEBE lanzar
  `WfaConfigError` (historia insuficiente, decisión 1, §3) antes de ejecutar ningún backtest.
- **R12** (DEBE). `window_config.py` DEBE definir `GridConfig` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `n_minutes_levels: tuple[int, ...] = (5, 15, 30)`,
  `atr_stop_frac_levels: tuple[float, ...] = (0.5, 1.0, 1.5)`, `risk_pct_levels: tuple[float, ...]
  = (0.0025, 0.00375, 0.005)` (spec §6.2). DEBE lanzar `WfaConfigError` en construcción si
  `len(n_minutes_levels) * len(atr_stop_frac_levels) * len(risk_pct_levels) > 27` (techo mecánico
  inviolable) o si `len(n_minutes_levels) * len(atr_stop_frac_levels) > 9` (techo de señal).
- **R13** (DEBE). `window_config.py` DEBE definir `window_identity_hash(candidate_id: str, symbol:
  str, dataset_hash_is: str, dataset_hash_oos: str, grid_config_hash: str, config_version: str) ->
  str`, hash `sha256` determinista sobre JSON canónico ordenado (patrón `risk_profile_hash`),
  usado exclusivamente como campo informativo de `WindowResult` (decisión 6, §3) — NO se persiste a
  disco en este Change (R66).

### 4.3. `_dsr.py` — Deflated Sharpe Ratio, módulo interno

- **R14** (DEBE). `_dsr.py` DEBE definir `deflated_sharpe_ratio(returns: Sequence[float],
  n_trials: int) -> float` como función pura, sin estado, usada **exclusivamente** como criterio de
  selección IS dentro de `wfa.py` — no exportada en `src/genesis/validation/__init__.py`. `rg -n
  "deflated_sharpe_ratio" src/genesis/validation/__init__.py` DEBE retornar 0 coincidencias.
- **R15** (DEBE). `deflated_sharpe_ratio` DEBE calcular, sobre `returns` (deltas de equity por
  trade de salida): `SR_hat = mean(returns) / std(returns, ddof=1)`; si `len(returns) < 2` o
  `std(returns, ddof=1) == 0`, DEBE retornar `0.0` sin lanzar excepción (mismo criterio que
  `sharpe_pointwise` de la capa 3).
- **R16** (DEBE). Si `SR_hat != 0.0` y `len(returns) >= 2`, `deflated_sharpe_ratio` DEBE calcular
  la fórmula completa de Bailey & López de Prado (2014, "The Deflated Sharpe Ratio"), con
  skewness/kurtosis empíricos (sin asumir normalidad, sin `scipy`):
  ```
  n      = len(returns)
  γ3     = skewness muestral de returns estandarizados: mean(((x - x̄) / s) ** 3)
  γ4     = kurtosis muestral (no excedente) de returns estandarizados: mean(((x - x̄) / s) ** 4)
  γ_EM   = 0.5772156649015329            # constante de Euler-Mascheroni
  e      = math.e
  Var_SR = (1 - γ3·SR_hat + ((γ4 - 1) / 4)·SR_hat²) / (n - 1)
  SR0    = sqrt(Var_SR) · ((1 - γ_EM)·Φ⁻¹(1 - 1/n_trials) + γ_EM·Φ⁻¹(1 - 1/(n_trials·e)))
  DSR    = Φ( (SR_hat - SR0) · sqrt(n - 1) / sqrt(1 - γ3·SR_hat + ((γ4 - 1)/4)·SR_hat²) )
  ```
  donde `Φ` es `_standard_normal_cdf` (R17) y `Φ⁻¹` es `_standard_normal_ppf` (R18).
- **R17** (DEBE). `_dsr.py` DEBE definir `_standard_normal_cdf(x: float) -> float` implementada
  exactamente como `0.5 * (1 + math.erf(x / math.sqrt(2)))` (stdlib puro, sin `numpy`/`scipy`).
- **R18** (DEBE). `_dsr.py` DEBE definir `_standard_normal_ppf(p: float) -> float` (inversa de
  `_standard_normal_cdf`) mediante el algoritmo de Acklam (aproximación racional en tres tramos) +
  un paso de refinamiento de Halley sobre `_standard_normal_cdf`, sin `scipy`. DEBE cumplir, en
  `tests/validation/`: (a) ida y vuelta — para `p ∈ {0.55, 0.6, ..., 0.75, 0.8, ..., 0.9999}`,
  `abs(_standard_normal_cdf(_standard_normal_ppf(p)) - p) < 1e-9`; (b) ancla de literatura —
  `abs(_standard_normal_ppf(0.975) - 1.9599639845400545) < 1e-6`.
- **R19** (DEBE). `n_trials` de `deflated_sharpe_ratio` DEBE recibirse como argumento explícito del
  llamador (`wfa.py` lo invoca con `n_trials=9`, spec §6.2: "el conteo de trials del DSR... lo
  relevante son las 9 configuraciones de señal") — `_dsr.py` NO DEBE hardcodear el valor 9 ni 27
  internamente.
- **R20** (DEBE). `tests/validation/` DEBE incluir un golden test de `deflated_sharpe_ratio` con
  una secuencia de retornos sintéticos calculados a mano paso a paso siguiendo exactamente la
  fórmula de R16 (spec §9: "escenarios calculados a mano"), no contra el propio código de
  producción como oráculo.
- **R21** (NO DEBE). `_dsr.py` NO DEBE importar `scipy`, `statsmodels`, `matplotlib` ni
  `quantstats`. `rg -n "^import scipy|^import statsmodels|^import matplotlib|^import quantstats"
  src/genesis/validation/` DEBE retornar 0 coincidencias.
- **R22** (DEBE). `tests/validation/` NO DEBE importar `scipy` como oráculo de test (tampoco como
  dependencia de test): el ancla de literatura de R18(b) usa una constante hardcodeada, no un
  cálculo de `scipy.stats.norm.ppf` en tiempo de test.

### 4.4. `wfa.py` — walk-forward rolling, grid IS, selección, congelamiento, OOS cosido, WFE

- **R23** (DEBE). `wfa.py` DEBE definir `run_wfa(candidate_id: str, symbol: str, frame:
  pd.DataFrame, firm_profile: FirmProfile, risk_profile: RiskProfile, figure: SymbolFigure,
  funnel_config: InspectorFunnelConfig, costs_config: CostsConfig, news_events:
  Sequence[EconomicEvent], dataset_store: RawParquetStore, tick_store: RawParquetStore | None,
  starting_balance: float, window_config: WfaWindowConfig, grid_config: GridConfig, seed: int) ->
  WfaResult` (nombres exactos normativos; orden/defaults exactos de parámetros se fijan en
  `design.md`). `dataset_store` (siempre requerido, distinto de `tick_store` que puede ser `None`)
  se usa exclusivamente para `chunk_hash(frame)` — el hash de dataset no puede depender de si hay
  cobertura de ticks disponible.
- **R24** (DEBE). Por cada una de las 27 combinaciones de ejecución del grid IS de una ventana,
  `wfa.py` DEBE instanciar `CandidateB(n_minutes=..., atr_stop_frac=..., risk_pct=..., figure=...,
  reference_balance=starting_balance)` y un `Simulator` **nuevos** (nunca reutilizados entre
  combinaciones, ventanas o símbolos — `CandidateB` es stateful por símbolo/balance de referencia),
  sin pasar por `load_candidate_b_config`. `rg -n "CandidateB\(" src/genesis/validation/wfa.py`
  DEBE retornar ≥1 coincidencia; `rg -n "load_candidate_b_config"
  src/genesis/validation/wfa.py` DEBE retornar 0 coincidencias.
- **R25** (DEBE). Las 27 combinaciones de ejecución DEBEN agruparse en exactamente 9
  configuraciones de señal (`N × atr_stop_frac`, spec §6.2); cada configuración de señal agrupa 3
  combinaciones de ejecución (una por `risk_pct`). `wfa.py` DEBE registrar ambos conteos (9 de
  señal, 27 de ejecución) de forma explícita y mecánica por ventana en `WindowResult` (R29).
- **R26** (DEBE). Para cada configuración de señal, `wfa.py` DEBE extraer los trades OOS-de-
  selección (deltas de `equity_after` de salidas, definición de §2) de las 3 combinaciones de
  ejecución que la componen, calcular `deflated_sharpe_ratio` sobre el conjunto agregado con
  `n_trials=9`, y descartar (asignar `-inf`) cualquier configuración de señal con menos de
  `MIN_TRADES_IS = 10` trades agregados (decisión 5, §3) sin abortar la ventana.
- **R27** (DEBE). Si las 9 configuraciones de señal de una ventana quedan todas con DSR-IS `=
  -inf` (todas por debajo de `MIN_TRADES_IS`), `wfa.py` DEBE lanzar `WfaConfigError` (ventana
  inviable, decisión 5, §3) antes de intentar cualquier congelamiento/OOS de esa ventana.
- **R28** (DEBE). `wfa.py` DEBE seleccionar la configuración de señal ganadora por el mayor
  DSR-IS (R26); dentro de esa configuración de señal, DEBE seleccionar la combinación de ejecución
  ganadora (incluyendo `risk_pct`) por el mayor `sharpe_pointwise` del run IS entre las 3
  combinaciones de esa configuración de señal (criterio de desempate de sizing, sin re-penalizar
  por multiplicidad ya que `risk_pct` no altera la señal, spec §6.2).
- **R29** (DEBE). `wfa.py` DEBE congelar los parámetros ganadores de cada ventana, ejecutar una
  instancia **nueva** de `CandidateB`/`Simulator` sobre el tramo OOS de esa ventana, y registrar en
  `WindowResult` (`@dataclass(frozen=True, slots=True)`), como mínimo: índice de ventana, rango de
  `trading_day` IS y OOS, `dataset_hash_is`/`dataset_hash_oos` (vía `dataset_store.chunk_hash`),
  combinación ganadora, DSR-IS ganador, `Ledger` OOS de la ventana, `n_trials_signal = 9`,
  `n_trials_execution = 27`, y `window_identity_hash` (R13).
- **R30** (DEBE). Al terminar todas las ventanas, `wfa.py` DEBE coser la curva OOS completa
  concatenando temporalmente los `Ledger` OOS de todas las ventanas, en orden, sin solape entre
  ventanas (garantizado por R9) — el `Ledger` cosido comparte una única `RunProvenance` por
  `(candidate_id, symbol)` (patrón `Ledger`/`RunProvenance` de la capa 3).
- **R31** (DEBE). `wfa.py` DEBE calcular `WFE = sharpe_pointwise(oos_cosido) /
  mean(sharpe_pointwise(ledger_is_ganador_de_cada_ventana))` (decisión 3, §3), reutilizando
  `genesis.backtest.metrics.sharpe_pointwise` (pública) sin reimplementar la fórmula de Sharpe. Si
  el denominador (`mean(...)`) es `0.0`, `wfa.py` DEBE retornar `WFE = 0.0` (sentinel documentado,
  evita división por cero; el gate G2 lo evaluará como fallo en Issue J, no aquí).
- **R32** (DEBE). El loop de 27 combinaciones × N ventanas DEBE ejecutarse de forma secuencial (sin
  `multiprocessing`/`concurrent.futures`) en este Change. `rg -n "multiprocessing|concurrent\
  .futures" src/genesis/validation/wfa.py` DEBE retornar 0 coincidencias.
- **R33** (DEBE). `wfa.py` DEBE definir `WfaResult` (`@dataclass(frozen=True, slots=True)`) con,
  como mínimo: `candidate_id`, `symbol`, `config_version = "genesis-validation/1"`, `windows:
  Sequence[WindowResult]`, `oos_ledger_cosido: Ledger`, `wfe: float`, `n_windows: int`,
  `n_trials_signal_total = n_windows * 9`, `n_trials_execution_total = n_windows * 27`, `seed:
  int`.
- **R34** (DEBE). Ninguna excepción de `Simulator`/`RiskLevelsProvider` (`BacktestConfigError`,
  `SessionBoundaryError`) lanzada durante un run IS u OOS de `wfa.py` DEBE ser capturada ni
  envuelta silenciosamente — se propaga sin cambiar de tipo (R5).
- **R35** (NO DEBE). `wfa.py` NO DEBE calcular ningún gate G/C/P/T del spec §7 (ni evaluar
  umbrales contra `WfaResult`): solo produce los números; la evaluación es responsabilidad de
  `verdict.py` (Issue J).

### 4.5. Propiedad anti-lookahead del WFA (transversal a `wfa.py`)

- **R36** (DEBE). La combinación ganadora congelada de la ventana `k` (`WindowResult.
  winning_combo`, si se fija ese nombre en `design.md`) NO DEBE depender de ningún dato con
  `timestamp` posterior al corte IS/OOS de esa ventana `k`: mutar (agregar/alterar) barras del
  tramo OOS de la ventana `k`, o de cualquier ventana `k' > k`, NO DEBE cambiar la combinación
  ganadora ni el DSR-IS ganador de la ventana `k` (extensión, a nivel de WFA, del invariante
  forward-only del spec §9).
- **R37** (DEBE). `tests/validation/` DEBE incluir un test de propiedad (`hypothesis`, marcado
  `pytest.mark.unit`) que verifique R36 sobre datos sintéticos generados con semilla fija.

### 4.6. `montecarlo.py` — Monte Carlo por símbolo y de portafolio

- **R38** (DEBE). `montecarlo.py` DEBE definir `monte_carlo_symbol(oos_ledger: Ledger,
  risk_profile: RiskProfile, n_paths: int, seed: int, block_size: int | None = None) ->
  McSymbolResult` (nombres exactos normativos). DEBE ejecutar **ambos** métodos siempre —
  reshuffle (permutación completa sin reemplazo) y block bootstrap (bloques contiguos con
  reemplazo, spec §6: "por símbolo: reshuffle + block bootstrap", ambos, no una elección
  exclusiva) — y retornarlos como dos campos separados del resultado (R40), no como un parámetro
  `method` que seleccione uno.
- **R39** (DEBE). `monte_carlo_symbol` DEBE extraer los trades OOS del `oos_ledger` con la misma
  función interna de extracción que `wfa.py` (§2), generar `n_paths` trayectorias resampleadas por
  cada método, y calcular por trayectoria: MaxDD (mismo criterio que
  `genesis.backtest.metrics.max_drawdown`, reimplementado internamente sobre la curva de equity
  resampleada) y breach (`True` si el drawdown de la trayectoria supera
  `risk_profile.max_loss_limit_pct` del `starting_balance` implícito en la curva de equity del
  ledger original).
- **R40** (DEBE). `montecarlo.py` DEBE definir `McPathsResult` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `max_drawdown_per_path: np.ndarray`, `breach_per_path:
  np.ndarray`, `max_drawdown_p95: float` (percentil 95, interpolación lineal — default de
  `numpy.percentile`), `breach_probability: float` (fracción de trayectorias con breach), `seed`,
  `n_paths`, `block_size: int | None` (`None` para reshuffle, entero para block bootstrap). DEBE
  definir `McSymbolResult` con, como mínimo: `symbol`, `provenance: RunProvenance` (reutilizado del
  `oos_ledger`, definición de §2), `reshuffle: McPathsResult`, `block_bootstrap: McPathsResult`.
- **R41** (DEBE). Si el llamador no fija `block_size` explícitamente para `monte_carlo_symbol`, el
  default DEBE ser `clip(round(n_trades ** (1/3)), 5, 60)` sobre el número de trades OOS extraídos
  del `oos_ledger` (decisión 4, §3).
- **R42** (DEBE). `montecarlo.py` DEBE definir `monte_carlo_portfolio(oos_ledgers_by_symbol:
  Mapping[str, Ledger], risk_profile: RiskProfile, n_paths: int, seed: int, block_size: int | None
  = None) -> McPortfolioResult` (nombres exactos normativos).
- **R43** (DEBE). `monte_carlo_portfolio` DEBE combinar los `Ledger` OOS por `trading_day` (no por
  índice de trade) antes de resamplear en bloques temporales: para cada `trading_day` presente en
  cualquiera de los ledgers de entrada, DEBE agrupar los trades de salida de todos los símbolos de
  ese día en un único "bloque de canasta" indivisible durante el resampleo, preservando la
  correlación cruzada entre símbolos que ocurren en el mismo día (spec §6/§6.1, requisito
  explícito). `rg -n "trading_day" src/genesis/validation/montecarlo.py` DEBE retornar ≥1
  coincidencia.
- **R44** (DEBE). Si el llamador no fija `block_size` explícitamente para `monte_carlo_portfolio`,
  el default DEBE ser `5` días de trading (decisión 4, §3).
- **R45** (DEBE). `monte_carlo_portfolio` DEBE definir `McPortfolioResult` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `provenance_by_symbol: Mapping[str, RunProvenance]`,
  `block_bootstrap: McPathsResult` (solo block bootstrap por bloques temporales de canasta; el
  reshuffle puro no aplica a portafolio porque destruiría la correlación entre símbolos que este
  método existe para preservar).
- **R46** (DEBE). `tests/validation/` DEBE incluir un golden test que confirme R43: dos símbolos
  sintéticos con trades en los mismos `trading_day` (correlacionados por construcción) DEBEN
  permanecer correlacionados en las trayectorias resampleadas (verificable comparando la
  correlación de retornos diarios de canasta pre/post-resampleo dentro de una tolerancia fijada en
  el propio test).
- **R47** (DEBE). Todo generador aleatorio de `montecarlo.py` DEBE ser una instancia explícita de
  `numpy.random.Generator` construida a partir de `seed` (`numpy.random.default_rng(seed)` o
  equivalente), NUNCA el estado global `numpy.random` — determinismo total (spec §8): misma
  semilla + dataset + config ⇒ resultados bit-idénticos.
- **R48** (DEBE). `seed` DEBE ser un argumento **requerido** (sin default) de
  `monte_carlo_symbol`/`monte_carlo_portfolio` — ninguna llamada puede generar trayectorias sin una
  semilla explícita del llamador.
- **R49** (DEBERÍA). `n_paths` por defecto, cuando el llamador no lo fija explícitamente en el
  punto de invocación de más alto nivel (fuera de `montecarlo.py`, que exige el argumento explícito
  en su firma), DEBERÍA documentarse como `1000` en el docstring del módulo — suficiente resolución
  para los percentiles de los gates G6 (MaxDD p95) y G7 (P(breach) < 5%) que Issue J evaluará.
- **R50** (NO DEBE). `monte_carlo_symbol`/`monte_carlo_portfolio` NO DEBEN evaluar ningún gate G6/
  G7 del spec §7: solo producen `max_drawdown_p95`/`breach_probability` como insumo; la
  comparación contra el umbral es responsabilidad de `verdict.py` (Issue J).
- **R51** (DEBE). `montecarlo.py` DEBE lanzar `MonteCarloConfigError` si `n_paths <= 0`,
  `block_size <= 0` (cuando se fija explícitamente), o si `oos_ledger`/`oos_ledgers_by_symbol` no
  contiene ningún trade OOS extraíble.
- **R52** (DEBE). `tests/validation/` DEBE incluir un test de propiedad de determinismo (misma
  `seed` + mismo `oos_ledger`/`oos_ledgers_by_symbol` + mismo `n_paths`/`block_size` ⇒ arrays
  `max_drawdown_per_path`/`breach_per_path` bit-idénticos entre dos invocaciones independientes),
  marcado `pytest.mark.unit`.

### 4.7. Testing (`tests/validation/`)

- **R53** (DEBE). `tests/validation/conftest.py` y fixtures asociadas DEBEN existir, replicando el
  patrón de `tests/backtest/conftest.py` (reutilizando `load_firm_profile`, `load_risk_profile`,
  `load_costs_config`, `_default_symbol_figure` donde aplique, sin duplicar su construcción).
- **R54** (DEBE). `tests/validation/` DEBE incluir un test de propiedad `hypothesis` (marcado
  `pytest.mark.unit`) que verifique el determinismo total del WFA: mismo `seed` + mismo `frame` +
  misma config ⇒ `WfaResult` bit-idéntico (mismas combinaciones ganadoras, mismo `wfe`, mismo
  `oos_ledger_cosido`) entre dos invocaciones independientes de `run_wfa`.
- **R55** (DEBE). `tests/validation/` DEBE incluir un test de propiedad que verifique el techo
  mecánico de trials: ninguna ventana ejecuta más de 27 combinaciones de ejecución ni más de 9
  configuraciones de señal (verificable contando instancias de `CandidateB`/`Simulator` creadas por
  ventana, o inspeccionando `WindowResult.n_trials_signal`/`n_trials_execution`).
- **R56** (DEBE). `tests/validation/` DEBE incluir el test de propiedad anti-lookahead de R37.
- **R57** (DEBE). `tests/validation/` DEBE incluir el golden test de `deflated_sharpe_ratio` de
  R20 y el golden test de MC de portafolio de R46.
- **R58** (DEBE). `tests/validation/` DEBE incluir al menos un test de integración
  (`pytest.mark.integration`) que ejecute el pipeline completo sobre el fixture sintético existente
  (`sample_m1_frame` de `tests/backtest/`, o un fixture equivalente/ampliado propio de
  `tests/validation/fixtures/`) en segundos: `iter_bars` → `run_wfa` → `monte_carlo_symbol` →
  `monte_carlo_portfolio`, verificando que produce un `WfaResult`/`McSymbolResult`/
  `McPortfolioResult` no vacíos y métricas finitas.
- **R59** (DEBE). `tests/validation/` DEBE incluir al menos un test marcado `pytest.mark.slow` que
  ejerza el WFA completo (27 combinaciones × N ventanas × símbolos) sobre un volumen de datos
  realista, separado de la suite rápida por defecto (`mise run test`/`mise run ci` sin filtro de
  marcadores corre en segundos).
- **R60** (DEBE). `uv run pytest tests/validation/ -v` DEBE pasar en verde (exit code 0).

---

## 5. Invariantes transversales

- **R61** (DEBE). Ningún archivo de `src/genesis/data/`, `src/genesis/strategy/` ni
  `src/genesis/backtest/` DEBE modificarse en este Change (`git diff --stat -- src/genesis/data
  src/genesis/strategy src/genesis/backtest` vacío).
- **R62** (DEBE). Solo trades OOS DEBEN alimentar `monte_carlo_symbol`/`monte_carlo_portfolio` y el
  cálculo de WFE (spec §6.1, "regla sin excepción"); ningún trade IS DEBE aparecer en
  `oos_ledger_cosido` ni en los ledgers pasados a `montecarlo.py`.
- **R63** (NO DEBE). Este Change NO DEBE añadir ninguna dependencia de runtime nueva a
  `pyproject.toml` (`[project.dependencies]`); `wfa.py`, `montecarlo.py` y `_dsr.py` se implementan
  exclusivamente con `numpy` + `pandas` + stdlib. `rg -n "scipy|statsmodels|matplotlib|
  quantstats" pyproject.toml` DEBE no mostrar ninguna de esas dependencias añadida respecto al
  estado previo al Change.
- **R64** (DEBE). Toda excepción de dominio nueva de este Change DEBE heredar de
  `GenesisValidationError` y llevar mensaje con contexto explícito (R4).
- **R65** (DEBE). `src/genesis/validation/__init__.py` DEBE exportar un `__all__` mínimo y curado
  (patrón `src/genesis/backtest/__init__.py`), incluyendo como mínimo `GenesisValidationError`,
  `WfaConfigError`, `MonteCarloConfigError`, `run_wfa`, `WfaResult`, `monte_carlo_symbol`,
  `monte_carlo_portfolio`, `McSymbolResult`, `McPortfolioResult` — NUNCA
  `deflated_sharpe_ratio` (R14).
- **R66** (DEBE). Ningún artefacto de este Change (`WfaResult`, `WindowResult`, `McSymbolResult`,
  `McPortfolioResult`) DEBE serializarse a disco (Parquet/JSON) dentro de `wfa.py`/`montecarlo.py`
  en este Change — estructuras en memoria únicamente (decisión 5 del proposal).
- **R67** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/validation/` y `tests/validation/` nuevos.

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `GenesisValidationError` | `genesis.validation.errors` | Raíz de la jerarquía de la capa 4 | — |
| `WfaConfigError` | `genesis.validation.errors` | Historia insuficiente para una ventana (R11); grid/niveles fuera de presupuesto 27/9 (R12); las 9 configuraciones de señal de una ventana por debajo de `MIN_TRADES_IS` (R27) | Aborta `run_wfa` antes de (o durante) la ventana afectada, fail-fast |
| `MonteCarloConfigError` | `genesis.validation.errors` | `n_paths<=0`, `block_size<=0`, ledger(s) sin trades OOS extraíbles (R51) | Aborta `monte_carlo_symbol`/`monte_carlo_portfolio` antes de generar trayectorias |
| (heredado, propagado sin envolver) `BacktestConfigError` | `genesis.backtest.errors` | Candidato/config inválida durante un run IS/OOS invocado por `wfa.py` | Aborta `run_wfa` (R34) |
| (heredado, propagado sin envolver) `SessionBoundaryError` | `genesis.backtest.errors` | Posición viva tras cierre de sesión durante un run IS/OOS invocado por `wfa.py` | Aborta `run_wfa` (R34) |
| (heredado) `DayBoundaryError` | `genesis.data.errors` | `iter_bars` durante la pasada de planificación (R8) o los runs por ventana | Sin cambios respecto a B |
| (heredado) `LookaheadError` | `genesis.strategy.errors` | `SimulationClock`/`BarClock` durante cualquier run IS/OOS | Sin cambios respecto a C/G |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/validation/errors.py
CUANDO rg -n "class GenesisValidationError" src/genesis/validation/errors.py
       y rg -n "class WfaConfigError" src/genesis/validation/errors.py
       y rg -n "class MonteCarloConfigError" src/genesis/validation/errors.py
ENTONCES las tres retornan >=1 coincidencia; WfaConfigError y MonteCarloConfigError heredan de
         GenesisValidationError; GenesisValidationError no hereda de GenesisBacktestError,
         GenesisStrategyError ni GenesisDataError (R1-R3)
```

```
DADO   un frame crudo con menos trading_day distintos que
       IS_WINDOW_TRADING_DAYS + OOS_WINDOW_TRADING_DAYS
CUANDO se invoca run_wfa(...) sobre ese frame
ENTONCES se lanza WfaConfigError antes de ejecutar ningún backtest (R11)
```

```
DADO   una GridConfig con más de 27 combinaciones de ejecución o más de 9 de señal
CUANDO se construye GridConfig(...)
ENTONCES se lanza WfaConfigError (R12)
```

```
DADO   el archivo src/genesis/validation/wfa.py
CUANDO rg -n "def run_wfa" src/genesis/validation/wfa.py
       y rg -n "CandidateB\(" src/genesis/validation/wfa.py
       y rg -n "load_candidate_b_config" src/genesis/validation/wfa.py
ENTONCES la primera y la segunda retornan >=1 coincidencia; la tercera retorna 0 (R23, R24)
```

```
DADO   una ventana WFA en la que las 9 configuraciones de señal producen menos de
       MIN_TRADES_IS = 10 trades agregados cada una
CUANDO run_wfa procesa esa ventana
ENTONCES se lanza WfaConfigError (R27), sin intentar congelar ni correr OOS de esa ventana
```

```
DADO   un WfaResult producido por run_wfa sobre un frame con N ventanas resolubles
CUANDO se inspecciona cada WindowResult
ENTONCES cada uno reporta n_trials_signal == 9 y n_trials_execution == 27; el WfaResult agregado
         reporta n_trials_signal_total == N*9 y n_trials_execution_total == N*27 (R25, R29, R33)
```

```
DADO   dos invocaciones independientes de run_wfa con el mismo seed, frame y config
CUANDO se comparan los dos WfaResult resultantes
ENTONCES las combinaciones ganadoras por ventana, el wfe y el oos_ledger_cosido son
         bit-idénticos (R54, determinismo total)
```

```
DADO   un frame sintético y una ventana k ya resuelta por run_wfa
CUANDO se mutan (agregan/alteran) barras con timestamp posterior al corte IS/OOS de la ventana k
       (en el propio tramo OOS de k o en cualquier ventana k' > k) y se vuelve a invocar run_wfa
ENTONCES la combinación ganadora y el DSR-IS ganador de la ventana k no cambian (R36, R37)
```

```
DADO   una secuencia de retornos sintéticos calculada a mano según la fórmula de R16
CUANDO se invoca _dsr.deflated_sharpe_ratio(returns, n_trials=9)
ENTONCES el resultado coincide con el valor calculado a mano dentro de una tolerancia numérica
         fijada en el propio test (R20)
```

```
DADO   el módulo src/genesis/validation/_dsr.py
CUANDO se evalúa _standard_normal_cdf(_standard_normal_ppf(p)) para p en {0.55..0.9999}
       y se compara _standard_normal_ppf(0.975) contra 1.9599639845400545
ENTONCES el primer error absoluto es < 1e-9 y el segundo es < 1e-6, sin importar scipy en
         ningún punto (R18, R21, R22)
```

```
DADO   el archivo src/genesis/validation/montecarlo.py
CUANDO rg -n "def monte_carlo_symbol|def monte_carlo_portfolio" src/genesis/validation/montecarlo.py
       y rg -n "trading_day" src/genesis/validation/montecarlo.py
ENTONCES ambas búsquedas retornan >=1 coincidencia (R38, R42, R43)
```

```
DADO   un oos_ledger con trades OOS extraíbles
CUANDO se invoca monte_carlo_symbol(oos_ledger, risk_profile, n_paths=1000, seed=42)
ENTONCES el McSymbolResult retornado incluye tanto reshuffle como block_bootstrap, cada uno con
         max_drawdown_per_path de longitud 1000 y max_drawdown_p95/breach_probability finitos
         (R38-R40)
```

```
DADO   dos símbolos sintéticos con trades correlacionados en los mismos trading_day
CUANDO se invoca monte_carlo_portfolio({sym_a: ledger_a, sym_b: ledger_b}, risk_profile,
       n_paths=..., seed=...)
ENTONCES la correlación de retornos diarios de canasta se preserva en las trayectorias
         resampleadas dentro de la tolerancia fijada en el test (R43, R46)
```

```
DADO   dos invocaciones independientes de monte_carlo_symbol/monte_carlo_portfolio con el mismo
       seed, ledger(s), n_paths y block_size
CUANDO se comparan los arrays max_drawdown_per_path/breach_per_path resultantes
ENTONCES son bit-idénticos entre ambas invocaciones (R47, R48, R52)
```

```
DADO   el archivo pyproject.toml tras completar este Change
CUANDO rg -n "scipy|statsmodels|matplotlib|quantstats" pyproject.toml
ENTONCES no muestra ninguna de esas dependencias añadida a [project.dependencies] respecto al
         estado previo al Change (R63)
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
ENTONCES no retorna ninguna línea (R61)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/validation/ -v
ENTONCES pasa en verde, incluyendo:
         - >=1 test de propiedad de determinismo total del WFA (R54)
         - >=1 test de propiedad de techo mecánico 27/9 (R55)
         - >=1 test de propiedad anti-lookahead a nivel de ventana WFA (R37, R56)
         - >=1 golden test de deflated_sharpe_ratio calculado a mano (R20, R57)
         - >=1 golden test de correlación preservada en MC de portafolio (R46, R57)
         - >=1 test de integración del pipeline completo en segundos (R58)
         - >=1 test marcado pytest.mark.slow de volumen realista (R59)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run mise run ci
ENTONCES lint + ty + test pasan en verde (exit code 0, R67)
```

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | `CandidateB` reinstanciado en frío al inicio de cada ventana/combinación no porta el estado ATR-Wilder-14 acumulado de la ventana anterior (el ATR de `CandidateB` es continuo entre días *dentro* de una instancia, pero cada ventana/combinación crea una instancia nueva, spec `candidate_b/candidate.py`): los primeros `atr_period` (14) días de cada ventana pueden operar con `atr_value=None` y por tanto sin señal utilizable. | Menos trades efectivos en los primeros días de cada ventana IS/OOS; podría sesgar levemente a la baja el conteo de trades de las ventanas más cortas. | Aceptado como comportamiento heredado del Candidato B (Issue E), no defecto de H: `IS_WINDOW_TRADING_DAYS = 252` (R6) da margen amplio (14 días de calentamiento sobre 252) para que el sesgo sea despreciable; documentado explícitamente, no oculto. |
| Rg-2 | La fórmula completa de Bailey & López de Prado (R16) usa skewness/kurtosis empíricos sobre muestras potencialmente pequeñas (`n` cercano a `MIN_TRADES_IS=10`), lo que puede hacer que `DSR` sea numéricamente inestable (varianza alta del estimador de kurtosis con pocas muestras). | Selección IS ruidosa en ventanas con pocos trades por configuración de señal. | `MIN_TRADES_IS=10` (decisión 5, §3) es un piso mínimo documentado, no una garantía de estabilidad estadística completa; Issue I (`dsr_pbo.py`, con PBO vía CSCV) es quien valida robustez estadística completa sobre OOS/torneo. Riesgo aceptado y explícito para el uso interno de selección IS de H. |
| Rg-3 | `STEP_TRADING_DAYS == OOS_WINDOW_TRADING_DAYS` (R9) implica que el ancho de la ventana IS nunca crece (rolling puro, no expanding): en historias muy largas, ventanas IS más recientes no se benefician de más historia acumulada que las primeras. | Podría dejar "sobre la mesa" señal disponible en historia antigua para ventanas tardías. | Decisión de diseño explícita (decisión 1, §3): rolling, no expanding, por simplicidad y determinismo del anti-lookahead (R36); revisable en un Change futuro si el volumen real de datos de The5ers (Issue B) sugiere que expanding mejora sustancialmente G1/G4 sin comprometer G2 (WFE). |
| Rg-4 | El golden test de `deflated_sharpe_ratio` (R20) depende de un cálculo manual documentado en el propio test, no de un oráculo externo (`scipy` explícitamente excluido, R22): un error de transcripción en el cálculo manual podría pasar desapercibido. | Un bug silencioso en la fórmula de DSR-IS podría no detectarse por el golden test si el cálculo de referencia comparte el mismo error. | El test de ida y vuelta de `_standard_normal_ppf`/`_standard_normal_cdf` (R18) y el ancla de literatura (`Φ⁻¹(0.975)`) acotan independientemente la corrección del componente más propenso a error (la inversión numérica); el resto de la fórmula (R16) es aritmética directa, de menor riesgo de error silencioso. |
| Rg-5 | `monte_carlo_portfolio` combina por `trading_day` (R43) asumiendo que todos los símbolos comparten el mismo calendario de `trading_day` (mismo `daily_reset_time`/`daily_reset_tz` de `FirmProfile`); si un símbolo futuro tuviera un calendario de sesión radicalmente distinto (huso horario muy alejado), la agrupación por día podría no capturar correlación intradía real. | Menor fidelidad de la correlación preservada para universos de símbolos con calendarios muy heterogéneos. | El universo actual del Candidato B (US500, NAS100, US30, GER40) comparte `FirmProfile.daily_reset_time`/`daily_reset_tz` (una sola ficha de firma activa, spec §1.1); el riesgo es hipotético para el alcance actual, documentado para si un Change futuro introduce un universo con firmas/calendarios mixtos. |
| Rg-6 | Sin `tests/validation/` previo, no hay patrón de fixtures/fakes ya validado propio de esta capa; el fixture sintético de `tests/backtest/` (`sample_m1.csv`) puede ser demasiado corto para producir siquiera una ventana WFA completa (252+126 `trading_day`). | Mayor esfuerzo de diseño de fixtures desde cero; el test de integración (R58) podría necesitar un fixture ampliado o sintético propio. | R58 permite explícitamente "un fixture equivalente/ampliado propio de `tests/validation/fixtures/`"; `design.md`/`apply` deciden si generan un CSV sintético más largo o un generador programático de barras determinista, sin bloquear este Change. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Orden y valores por defecto exactos de los parámetros de `run_wfa`/`monte_carlo_symbol`/
  `monte_carlo_portfolio` — se resuelven en `design.md` respetando el comportamiento normativo de
  esta especificación (R23, R38, R42).
- Forma exacta de la estructura interna que agrupa "trayectoria resampleada" antes de reducirla a
  `max_drawdown_per_path`/`breach_per_path` (curva de equity completa vs. solo el resumen) — este
  documento fija el comportamiento observable (R39-R40), no la estructura intermedia.
- Si `WindowResult` expone el `Ledger` IS de cada una de las 27 combinaciones (para trazabilidad
  completa) o solo el de la combinación ganadora — R29 exige, como mínimo, el `Ledger` OOS de la
  ventana y la combinación ganadora; `design.md` puede decidir retener más detalle si el costo de
  memoria es aceptable dado el alcance en memoria (R66).
- Si un Change futuro de runs reanudables (§8 del spec, diferido explícitamente aquí) reutilizará
  `window_identity_hash` (R13) tal cual, o necesitará campos adicionales (p. ej. versión del código
  de `wfa.py`, no solo de los insumos) — fuera del alcance de decidir en H.
- Si el ancho de ventana rolling (R6) debería variar por símbolo dado el sanity-check §7.6 (que ya
  asume homogeneidad entre los 4 índices del universo B) — se difiere hasta que la historia real de
  The5ers (Issue B) muestre asimetrías significativas entre símbolos.

---

## 10. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/10.
- `idea.md` / `proposal.md` de este Change (fases explore/propose) — hipótesis de solución,
  6 decisiones fijadas por el proposal y 6 riesgos que este documento resuelve (§3).
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §6 (tabla capa 4), §6.1
  (flujo, reglas sin excepción: solo OOS alimenta validación, trials mecánicos, gates P a nivel de
  cuenta), §6.2 (presupuesto de grid 27/9 y DSR-IS, definitivos), §7.1 (gates G, en especial G1/G2/
  G4/G6/G7), §7.6 (sanity-checks de alcanzabilidad G1≥300, G4/T1 DSR≥0.95 con `ln(27)≈3.30`), §8
  (manejo de errores, determinismo total, runs reanudables), §9 (testing: unit+property, golden,
  integración, estadístico — este último de Issue I), §11 (tabla de issues, G bloquea H, H bloquea
  I), §11.1 (PA-5, forma del grid IS asignada a H/I), §11.2 (dependencias de runtime).
- Spec promovido de Issue G (backtest, archivado): `.pulse/specs/backtest/spec.md` — alcance OUT
  explícito de `src/genesis/validation/`, diferimiento de `scipy/statsmodels/matplotlib/
  quantstats` "a Issue H en adelante" (R41/R58 de ese Change), patrón de requisitos `R1..Rn` +
  criterios ejecutables replicado en este documento.
- `src/genesis/backtest/simulator.py` (`Simulator:203`, `run_backtest:612`, `RiskLevelsProvider`)
  — API pública consumida sin modificación.
- `src/genesis/backtest/ledger.py` (`Ledger`, `LedgerEntry`, `RunProvenance`, `FillRecord`,
  `BreachEvent`, `BreachKind`, `reconstruct_equity_series`) — `RunProvenance` reutilizado como
  ficha de procedencia de esta capa (§2); `FillRecord.equity_after` como base de la extracción de
  trades OOS.
- `src/genesis/backtest/metrics.py` (`sharpe_pointwise`, `max_drawdown`, `profit_factor` —
  funciones puras públicas reutilizadas para WFE; `_exit_deltas` privada, NO importada, replicada
  internamente en `genesis.validation`).
- `src/genesis/backtest/risk_profile.py` (`RiskProfile`, `MaxLossLimitKind`, `risk_profile_hash` —
  patrón de hash reutilizado por `window_identity_hash`).
- `src/genesis/backtest/errors.py` (`GenesisBacktestError`, `BacktestConfigError`,
  `SessionBoundaryError` — jerarquía independiente, patrón replicado por
  `genesis.validation.errors`).
- `src/genesis/strategy/candidate_b/candidate.py` (`CandidateB.__init__` con kwargs directos de
  grid; ATR-Wilder-14 continuo entre días *dentro* de una instancia, Rg-1), `config.py`
  (`CandidateBConfig`, `load_candidate_b_config` — NO usado por el WFA).
- `src/genesis/data/store.py` (`iter_bars`, `AnnotatedBar.trading_day`, `_trading_day` privada —
  el pre-pase de planificación de R8 usa `iter_bars` público, no reimplementa `_trading_day`).
- `src/genesis/data/mt5_export.py` (`RawParquetStore.chunk_hash`, `has_chunk`, `Granularity`,
  `ChunkWindow`).
- `src/genesis/data/profile.py` (`FirmProfile.daily_reset_time/daily_reset_tz/server_tz`).
- `pyproject.toml` (`[project.dependencies]`: `metatrader5`, `numpy>=2.5.0`, `pandas>=3.0.3`,
  `pyarrow>=24.0.0`; sin `scipy`/`statsmodels`/`matplotlib`/`quantstats` — confirma R63; marcadores
  pytest ya registrados: `unit`, `integration`, `e2e`, `statistical`, `slow`).
- `tests/backtest/conftest.py`, `tests/backtest/fakes.py`, `tests/backtest/fixtures/sample_m1.csv`
  — patrón de fixtures a replicar y posible base ampliable para `tests/validation/fixtures/`.
- Referencia externa citada por el spec y esta especificación: Bailey, D. H. & López de Prado, M.
  (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and
  Non-Normality" — fórmula exacta de R16.
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, comandos, flujo SDD, cadena de dependencias
  A→B→C→{D/E,G}→H→I→J→K.
