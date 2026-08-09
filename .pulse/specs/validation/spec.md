
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

<!-- change:12-i-feat-validation-purged-k-fold-dsr-pbo-sensibilidad -->
<!-- change:12-i-feat-validation-purged-k-fold-dsr-pbo-sensibilidad -->
# Specification: Purged K-Fold + DSR + PBO + sensibilidad (Issue #12 / I)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §2.5,
§6, §6.1, §6.2, §7.1, §7.4, §7.6, §8, §9, §11, §11.1 (PA-5), §11.2, §3 ("núcleo propio, periferia
pragmática"). Este documento formaliza `idea.md` y `proposal.md` de este Change en requisitos
verificables. Los gates G/C/P/T del spec **nunca se relajan**; ningún requisito de este documento
puede contradecirlos. Este Change calcula el DSR/PBO/sensibilidad **por candidato aislado**
(insumos de los gates G4/G5/G8/G9) — la deflación de torneo T1 es responsabilidad exclusiva de
`verdict.py` (Issue J, §2.5, §7.4).

Convención de rutas: el spec usa pseudocódigo `python/validation/...` (§6); el repo real usa
`src/genesis/validation/...`. Todas las rutas de este documento son las reales del repo.

Este documento corrige dos puntos de `proposal.md` con evidencia técnica nueva encontrada al
verificar el código de H (§3, decisiones 4 y 6 de este documento): (a) la forma de la matriz CSCV
no puede construirse ranqueando una única serie OOS cosida — el PBO exige, por definición, una
matriz de **múltiples trials** comparables sobre los mismos períodos, y `WfaResult`/`WindowResult`
(H, congelado) solo exponen el ledger IS/OOS de la **combinación ganadora** por ventana, nunca el
de las 8 configuraciones de señal descartadas; (b) la necesidad real de `scipy`/`statsmodels` en
este Change es nula una vez verificado el código (`math.comb` de stdlib cubre la combinatoria de
CSCV; `_dsr.py` ya resuelve `Φ`/`Φ⁻¹` sin `scipy`), por lo que se extiende el criterio "núcleo
propio" una tercera vez consecutiva (G, H, I) en vez de introducir la dependencia.

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Cerrar la capa 4 de validación mecánica del torneo con tres módulos nuevos —
`src/genesis/validation/purged_cv.py`, `src/genesis/validation/dsr_pbo.py`,
`src/genesis/validation/sensitivity.py` — que consumen exclusivamente la API pública ya cerrada de
H (`WfaResult`, `WindowResult`, `Ledger`, `_dsr.deflated_sharpe_ratio`) y de las capas 1-3, sin
modificar ningún archivo de `wfa.py`, `montecarlo.py`, `_dsr.py`, `window_config.py` ni de las capas
1-3. Produce los insumos de robustez estadística (DSR de gate, PBO vía CSCV, sensibilidad ±10% y
stress de costos) que Issue J (`verdict.py`) necesita para evaluar G4, G5, G8 y G9 y aplicar
después la deflación de torneo T1 — sin ellos, el camino crítico A → B → C → {E, G} → H → **I** → J
se detiene aquí (spec §11).

### 1.2. Alcance IN

- `src/genesis/validation/errors.py` (extendido, sin tocar las clases existentes de H):
  `PurgedCvConfigError`, `DsrPboConfigError`, `SensitivityConfigError`.
- `src/genesis/validation/_returns.py` (módulo interno nuevo, prefijo `_`, no exportado): extracción
  de trades OOS con horizonte temporal (`entry_timestamp`, `exit_timestamp`, `pnl_delta`),
  compartida por los tres módulos de este Change (ADR-I1, §2).
- `src/genesis/validation/purged_cv.py`: `PurgedCvConfig`, `PurgedFold`, `PurgedCvResult`,
  `run_purged_cv`.
- `src/genesis/validation/dsr_pbo.py`: `deflated_sharpe_ratio_gate`, `build_signal_trial_matrix`,
  `SignalTrialMatrix`, `combinatorial_symmetric_cross_validation`, `CscvResult`, `DsrPboResult`,
  `run_dsr_pbo`.
- `src/genesis/validation/sensitivity.py`: `SensitivityConfig`, `PerturbationOutcome`,
  `CostStressOutcome`, `SensitivityResult`, `run_sensitivity`.
- `src/genesis/validation/__init__.py`: extensión del `__all__` mínimo y curado (patrón R65 de H)
  con la superficie normativa de este Change — sin exportar `_returns.py` ni
  `build_signal_trial_matrix`/funciones auxiliares internas si `design.md` las marca privadas.
- `tests/validation/`: `test_returns.py`, `test_purged_cv.py`, `test_dsr_pbo.py`,
  `test_sensitivity.py`, extensión de `conftest.py`/`fixtures/` según necesidad, con el nivel
  "Estadístico" (marcador `statistical`, spec §9) contra casos publicados de López de Prado.

### 1.3. Alcance OUT (YAGNI explícito)

- **Deflación de torneo T1** (dividir/ajustar el DSR por el número de candidatos del torneo,
  spec §2.5/§7.4): exclusivo de `verdict.py` (Issue J). `dsr_pbo.py` produce el DSR/PBO **por
  candidato aislado**, nunca deflactado por torneo.
- **Perturbación del proxy de volumen** (solo Candidato A, spec §6): diferida — el issue #12 la
  marca explícitamente "no aplica mientras A no pase su diagnóstico" (Issue D).
- `prop_sim.py`, `verdict.py`, tearsheet, manifest reproducible con un comando — Issue J.
- Modificación de cualquier archivo bajo `src/genesis/data/`, `src/genesis/strategy/`,
  `src/genesis/backtest/`, o de `wfa.py`/`montecarlo.py`/`_dsr.py`/`window_config.py` (capa 4 ya
  cerrada por H): `git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
  src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py src/genesis/validation/_dsr.py
  src/genesis/validation/window_config.py` DEBE quedar vacío.
- `statsmodels`: no se introduce en este Change (decisión 6, §3) — permanece declarada en el spec
  §11.2 para el proyecto en su conjunto, diferida hasta que un Issue posterior (J/K, p. ej.
  tearsheet/`quantstats`) identifique una necesidad concreta de código.
- `scipy`: **no se introduce en este Change** (decisión 6, §3) — corrección explícita de
  `proposal.md` (que dejaba la puerta abierta a introducirlo, al menos en `dev`, como oráculo de
  test). Ver justificación completa en §3.
- Persistencia a disco / `ArtifactMetadata` completo (spec §3, patrón institucional de capa 1): los
  tres artefactos de este Change son dataclasses congeladas en memoria, mismo criterio que H
  (decisión 8, `proposal.md`).
- Paralelismo (`multiprocessing`/`concurrent.futures`): loop secuencial; tests de volumen realista
  marcados `pytest.mark.slow` — mismo criterio que H.
- Re-optimización de parámetros dentro de `sensitivity.py`: solo perturba y re-ejecuta con
  parámetros fijados por fuera (nunca vuelve a buscar un óptimo).
- Cualquier candidato distinto de B (ejes de perturbación, grid de señal): mismo alcance cerrado que
  H, específico del Candidato B único implementado.

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **NO DEBE**, numerados `R1..Rn` (numeración propia de este
  Change, no continúa la de H), cada uno verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones/constantes son **normativos**; firmas exactas (orden,
  defaults no fijados aquí) se resuelven en `design.md` respetando el comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español.
- **"Trade OOS"** (definición compartida, §1.2, ADR-I1): a diferencia de H (que solo extraía
  `pnl_delta`, el delta de `equity_after` entre `FillRecord`s de salida consecutivos), este Change
  necesita además el **horizonte temporal** de cada trade para el purgado (§4.2) — se define un
  trade como el par `(entry_fill, exit_fill)` de dos `FillRecord`s consecutivos del mismo
  `candidate_id`/`symbol` en el ledger, con `entry_fill.is_exit=False` seguido (sin otro fill del
  mismo símbolo entre medias) de `exit_fill.is_exit=True` (`genesis.backtest.ledger.FillRecord`,
  campos `timestamp_utc`, `is_exit`, `equity_after`). Válido para el Candidato B (única posición
  abierta por símbolo a la vez, spec §2.3); un candidato futuro con posiciones concurrentes
  requeriría revisar esta definición (riesgo Rg-7, §8).
- `_returns.py` (ADR-I1, corrige/extiende ADR-H5 de H): H documentó la duplicación de la función de
  extracción de retornos entre `wfa.py`/`montecarlo.py` como deliberada ("evita acoplar wfa <->
  montecarlo", ADR-H5, un acoplamiento *entre pares de módulos preexistentes*). Este Change
  introduce **tres módulos nuevos dentro del mismo Change** que necesitarían la idéntica extracción
  (ahora ampliada con horizonte temporal) — duplicarla tres veces dentro de un único Change no tiene
  el beneficio de aislamiento que motivó ADR-H5 (que evitaba dependencia cruzada *entre Changes*).
  Se comparte en `_returns.py` (módulo interno, prefijo `_`, no exportado, mismo patrón que
  `_dsr.py`); `wfa.py`/`montecarlo.py` **no** se modifican para importarlo (siguen con su propia
  `_extract_exit_returns`, decisión de H que no se revierte).

---

## 3. Resolución de las decisiones abiertas de `idea.md`/`proposal.md`

| # | Decisión pendiente | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | PA-5 reformulada: `n_trials` del DSR de G4 (9 de señal vs. 27 de ejecución) | **9** (`WfaResult.n_trials_signal_total`). Confirmado: el spec §6.2 dice "risk_pct no altera la señal ni el conteo de trades... para el conteo de trials del DSR... lo relevante son las 9 configuraciones de señal", una propiedad del candidato/dominio (búsqueda sobre la forma de la señal), no del *propósito* del DSR (selección IS vs. gate normativo). §7.1 (G4) dice solo "trials del propio candidato" sin distinguir; §7.6 usa `ln(27)≈3.30` como referencia del *techo de diseño del grid*, no como el argumento del DSR. Sin base normativa para que el gate penalice más que la selección IS por una dimensión (`risk_pct`) que nunca altera la señal. | R21-R23 |
| 2 | Reutilización vs. duplicación de `_dsr.py` | Reutilización directa de `deflated_sharpe_ratio` (sin variante nueva) para el DSR de G4. El PBO (CSCV) es código propio de `dsr_pbo.py`: no tiene equivalente en `_dsr.py`. | R21, R28-R31 |
| 3 | Geometría del Purged K-Fold | Partición sobre los **trades OOS individuales** del `oos_ledger_cosido` de `WfaResult` (no sobre las ventanas rolling de H, que ya tienen su propia frontera IS/OOS estricta) — K folds contiguos temporalmente por orden de `exit_fill.timestamp_utc`; horizonte de purga = intervalo real `[entry_timestamp, exit_timestamp]` de cada trade (definición de López de Prado, cap. 7); embargo posterior explícito en días de calendario. | R8-R18 |
| 4 | Forma de la matriz CSCV para PBO — **corrige `proposal.md` Decisión 4** | El PBO (Bailey, Borwein, López de Prado & Zhu, 2015) exige por definición una matriz de retornos de **N≥2 trials comparables sobre los mismos T períodos** (para cada partición combinatoria: seleccionar el mejor trial IS, medir su rango OOS). Ranguear una única serie (el `oos_ledger_cosido`, que es el resultado de **un solo** ganador por ventana) no es matemáticamente PBO — no hay selección que medir. `WfaResult`/`WindowResult` (H) exponen solo la combinación ganadora por ventana (`is_ledger_winning`, `oos_ledger`), nunca las 8 configuraciones de señal descartadas. **Resolución**: `dsr_pbo.py` reconstruye independientemente, sin modificar `wfa.py`, la matriz de trials (`build_signal_trial_matrix`, R28-R30): re-ejecuta el grid IS de 9 configuraciones de señal por ventana con la misma geometría (`WfaWindowConfig`/`GridConfig` públicos de H) sobre el mismo `frame`, produciendo el DSR-IS (o Sharpe-IS) de cada una de las 9 configuraciones × N ventanas — trials = 9 configuraciones de señal, períodos = N ventanas WFA. `S` (número de bloques CSCV) = `n_windows` si es par, `n_windows - 1` si es impar (o el valor explícito que fije `design.md`, con mínimo `S ≥ 4`, `WfaConfigError`→`DsrPboConfigError` si `n_windows < 4`). | R24-R35 |
| 5 | Ejes de perturbación ±10% (`sensitivity.py`) | Independientes, eje por eje (`N`, `atr_stop_frac`, `risk_pct`), solo ±10% (sin malla más fina), aplicados **exclusivamente sobre la combinación ganadora de la última ventana WFA** (`WfaResult.windows[-1]`, la más reciente, candidata a incubación en vivo), re-ejecutando el backtest solo sobre el tramo OOS de esa ventana — no sobre todas las ventanas (acota el costo computacional a un múltiplo pequeño y constante, no proporcional a `n_windows`; resuelve el riesgo 5 de `proposal.md`). | R37-R42 |
| 6 | Definición operativa de "acantilado" (G8) | Un "acantilado" es una caída de PF *desproporcionada* respecto a la degradación general que ya cubre G8 (<30%), en un único paso de ±10% (sin malla más fina, decisión 5): DEBE marcarse `is_cliff=True` en cualquiera de estas dos condiciones — (a) `PF_perturbado <= 1.0` (la perturbación cruza a no-rentable) o (b) `(PF_ganador - PF_perturbado) / PF_ganador >= 0.5` (caída relativa ≥ 50%, el doble del umbral de degradación general de G8). Ambos umbrales configurables (`cliff_pf_floor: float = 1.0`, `cliff_relative_drop_threshold: float = 0.5`), nunca relajables por debajo del umbral de G8 (0.30). | R40-R42 |
| 7 | Costo computacional de `sensitivity.py` | Ligado a la decisión 5: 2 perturbaciones × 3 ejes + 2 puntos de stress de costos (×1.5, ×2) = 8 backtests adicionales por `(candidate_id, symbol)`, todos sobre el mismo tramo OOS de la última ventana — volumen acotado y constante, loop secuencial (mismo criterio de H), sin necesidad de marcador `slow` adicional salvo que el test de integración multi-símbolo lo requiera. | R42, R49 |
| 8 | Necesidad real de `scipy`/`statsmodels` — **corrige `proposal.md` Decisión 6** | **Ninguna de las dos se introduce en este Change**, ni en runtime ni en `dev`. Verificado en código: `math.comb` (stdlib, Python ≥3.8) cubre exactamente la combinatoria `C(S, S/2)` de CSCV sin `scipy.special.comb`; `_dsr.py` (H) ya resuelve `Φ`/`Φ⁻¹` sin `scipy`, reutilizable tal cual; el nivel "Estadístico" del spec §9 ("casos publicados de López de Prado") se cubre con valores de literatura hardcodeados en el propio test (mismo patrón que R18(b)/R22 de H — `_standard_normal_ppf(0.975) == 1.9599639845400545` sin invocar `scipy.stats.norm`), no con un oráculo de `scipy` en tiempo de ejecución de test. Esto extiende el criterio "núcleo propio, periferia pragmática" del spec §3 una tercera vez consecutiva (G, H, I): `scipy`/`statsmodels` permanecen declaradas en el spec §11.2 como dependencias del proyecto en su conjunto, pero se introducen solo cuando un Issue con código real las necesite (candidato natural: J, `quantstats`/tearsheet). | R43-R44 |
| 9 | Reutilización vs. duplicación de la extracción de retornos | `_returns.py` compartido dentro de este Change (ADR-I1, §2), sin modificar `wfa.py`/`montecarlo.py`. | R6-R7 |
| 10 | Patrón de artefacto de salida | Dataclasses congeladas en memoria (`@dataclass(frozen=True, slots=True)`), mismo patrón ligero de H — sin `ArtifactMetadata` completo, sin serialización a disco. | R14, R32, R42, R56 |

---

## 4. Requisitos por módulo

### 4.1. `errors.py` — extensión de la jerarquía de excepciones (sin tocar clases existentes)

- **R1** (DEBE). `errors.py` DEBE definir `PurgedCvConfigError(GenesisValidationError)` para: (a)
  `n_folds < 2`; (b) `embargo_days < 0`; (c) cualquier fold de test o de train que quede vacío tras
  purga+embargo; (d) `oos_ledger_cosido` con menos trades OOS que `n_folds` (imposible construir
  folds no vacíos).
- **R2** (DEBE). `errors.py` DEBE definir `DsrPboConfigError(GenesisValidationError)` para: (a)
  `n_windows < 4` (techo mínimo para CSCV, decisión 4, §3); (b) matriz de trials con alguna
  configuración de señal con menos de `MIN_TRADES_IS` trades IS agregados en alguna ventana (mismo
  umbral que H, reexpuesto por `dsr_pbo.py`, no reimportado de `wfa.py` — constante propia); (c)
  `n_splits` de CSCV no par o `n_splits > n_windows`.
- **R3** (DEBE). `errors.py` DEBE definir `SensitivityConfigError(GenesisValidationError)` para: (a)
  `WfaResult.windows` vacío; (b) `cost_stress_multipliers` con algún valor `<= 1.0`; (c)
  `cliff_relative_drop_threshold` fuera de `(0.0, 1.0]` o `cliff_pf_floor <= 0.0`.
- **R4** (DEBE). Todo mensaje de excepción nueva de este Change DEBE incluir contexto explícito
  (`candidate_id`, `symbol`, índice de fold/ventana/eje perturbado, valor involucrado) — fail-fast
  con contexto (spec §8).
- **R5** (DEBE). Las tres excepciones nuevas DEBEN heredar de `GenesisValidationError` (raíz de H,
  reutilizada, no redefinida).
- **R6** (NO DEBE). Ninguna excepción de este Change NO DEBE envolver silenciosamente
  `BacktestConfigError`/`SessionBoundaryError`/`WfaConfigError`/`MonteCarloConfigError`: se propagan
  sin capturar cuando ocurren durante un re-run de backtest invocado desde `dsr_pbo.py` o
  `sensitivity.py` (mismo criterio R5 de H).

### 4.2. `_returns.py` — extracción compartida de trades OOS con horizonte (ADR-I1)

- **R7** (DEBE). `_returns.py` DEBE definir `TradeReturn` (`@dataclass(frozen=True, slots=True)`)
  con, como mínimo: `entry_timestamp: datetime`, `exit_timestamp: datetime`, `pnl_delta: float`
  (delta de `equity_after` del `exit_fill`, definición de §2).
  `rg -n "class TradeReturn" src/genesis/validation/_returns.py` DEBE retornar ≥1 coincidencia.
- **R8** (DEBE). `_returns.py` DEBE definir `extract_trade_returns(ledger: Ledger) ->
  list[TradeReturn]`, pareando cada `FillRecord` con `is_exit=False` con el siguiente
  `FillRecord` con `is_exit=True` del mismo `candidate_id`/`symbol` en orden de aparición en el
  ledger (definición de §2). DEBE preservar el orden temporal de aparición en el ledger (no
  reordena por `timestamp_utc`, ya que el ledger es append-only y forward-only por construcción).
- **R9** (DEBE). `_returns.py` NO DEBE ser importado por `wfa.py` ni `montecarlo.py` (R61 extendido
  a este Change: no se modifican los módulos ya cerrados de H). `rg -n "from genesis.validation._returns
  import|from \.\_returns import" src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py`
  DEBE retornar 0 coincidencias.
- **R10** (DEBE). `_returns.py` NO DEBE exportarse en `src/genesis/validation/__init__.py`
  (`__all__`), mismo patrón que `_dsr.py` (R14 de H).

### 4.3. `purged_cv.py` — Purged K-Fold con embargo

- **R11** (DEBE). `purged_cv.py` DEBE definir `PurgedCvConfig` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `n_folds: int = 5`, `embargo_days: int | None = None` (si `None`,
  se calcula un default determinista, R13). DEBE validar en `__post_init__` que `n_folds >= 2` y
  `embargo_days is None or embargo_days >= 0`; en caso contrario, `PurgedCvConfigError`.
- **R12** (DEBE). `purged_cv.py` DEBE definir `run_purged_cv(oos_ledger: Ledger, config:
  PurgedCvConfig) -> PurgedCvResult` (nombre exacto normativo; orden/defaults exactos de parámetros
  se fijan en `design.md`).
- **R13** (DEBE). Si `config.embargo_days is None`, `run_purged_cv` DEBE calcular el embargo por
  defecto como `clip(round(0.01 * total_calendar_days_span(trades)), 1, 30)` (1% del rango temporal
  total de los trades OOS extraídos, práctica estándar de López de Prado, acotado a `[1, 30]` días
  de calendario) — patrón análogo a la fórmula de `block_size` de `montecarlo.py` (decisión 4 de
  H).
- **R14** (DEBE). `run_purged_cv` DEBE extraer los trades OOS de `oos_ledger` vía
  `_returns.extract_trade_returns` (R8), ordenarlos por `exit_timestamp`, y particionarlos en
  `config.n_folds` folds de test contiguos temporalmente de tamaño igual (± 1 por resto de
  división entera).
- **R15** (DEBE). Para cada fold de test `k`, `run_purged_cv` DEBE construir el fold de train
  purgando de **todos** los demás trades cualquiera cuyo intervalo `[entry_timestamp,
  exit_timestamp]` se solape con `[min(entry_timestamp del fold k), max(exit_timestamp del fold
  k)]` (purga por solapamiento de horizonte, definición canónica de López de Prado cap. 7), y
  aplicando adicionalmente el embargo (R13): purgar del train cualquier trade con `entry_timestamp`
  dentro de `[max(exit_timestamp del fold k), max(exit_timestamp del fold k) + embargo_days]`.
- **R16** (DEBE). `run_purged_cv` DEBE lanzar `PurgedCvConfigError` si, tras purga+embargo, el fold
  de train o el fold de test de cualquier `k` queda vacío (R1c).
- **R17** (DEBE). `purged_cv.py` DEBE definir `PurgedFold` (`@dataclass(frozen=True, slots=True)`)
  con, como mínimo: `index: int`, `test_trade_count: int`, `train_trade_count: int`,
  `purged_trade_count: int` (trades removidos del train por solapamiento+embargo),
  `test_period: tuple[datetime, datetime]`. DEBE definir `PurgedCvResult` con, como mínimo:
  `candidate_id`, `symbol`, `config: PurgedCvConfig`, `folds: Sequence[PurgedFold]`,
  `total_trades: int`.
- **R18** (NO DEBE). `run_purged_cv` NO DEBE re-ejecutar ningún backtest ni instanciar
  `CandidateB`/`Simulator`: opera exclusivamente sobre los trades ya extraídos de un `Ledger` (a
  diferencia de `dsr_pbo.py`/`sensitivity.py`, que sí re-ejecutan backtests para construir su matriz
  de trials/perturbaciones).
- **R19** (DEBE). `run_purged_cv` DEBE ser determinista: ninguna partición ni purga depende de
  aleatoriedad (partición temporal contigua pura); dos invocaciones con el mismo `oos_ledger` y
  `config` DEBEN producir un `PurgedCvResult` bit-idéntico.
- **R20** (DEBE). `tests/validation/` DEBE incluir un test de propiedad (`hypothesis`, marcado
  `pytest.mark.unit`) que verifique, para cualquier partición generada: **ningún trade del fold de
  train tiene un intervalo `[entry_timestamp, exit_timestamp]` que se solape con el intervalo del
  fold de test correspondiente** tras purga+embargo (propiedad anti-leakage central del issue #12).

### 4.4. `dsr_pbo.py` — DSR normativo (G4) y PBO vía CSCV (G5)

- **R21** (DEBE). `dsr_pbo.py` DEBE definir `deflated_sharpe_ratio_gate(wfa_result: WfaResult) ->
  float`, que invoca `genesis.validation._dsr.deflated_sharpe_ratio(returns, n_trials=
  wfa_result.n_trials_signal_total)` (decisión 1, §3) sobre los retornos extraídos de
  `wfa_result.oos_ledger_cosido` vía `_returns.extract_trade_returns` (proyectando `pnl_delta`).
  `rg -n "from genesis.validation._dsr import deflated_sharpe_ratio" src/genesis/validation/dsr_pbo.py`
  DEBE retornar ≥1 coincidencia; `rg -n "n_trials_signal_total" src/genesis/validation/dsr_pbo.py`
  DEBE retornar ≥1 coincidencia.
- **R22** (NO DEBE). `deflated_sharpe_ratio_gate` NO DEBE aplicar ninguna deflación adicional por
  número de candidatos del torneo (T1 es responsabilidad exclusiva de `verdict.py`, Issue J, spec
  §2.5/§7.4) — `rg -n "n_candidates|tournament|torneo" src/genesis/validation/dsr_pbo.py` DEBE
  retornar 0 coincidencias relacionadas con deflación de torneo.
- **R23** (DEBE). El `n_trials` de `deflated_sharpe_ratio_gate` DEBE ser un argumento explícito
  internamente derivado de `wfa_result` (nunca hardcodeado como literal `9` fuera de la
  extracción del campo) — un cambio de criterio (p. ej. si `design.md`/una decisión futura revirtiera
  la decisión 1 de §3) debe ser un cambio de una línea, no un rediseño.
- **R24** (DEBE). `dsr_pbo.py` DEBE definir `build_signal_trial_matrix(candidate_id: str, symbol:
  str, frame: pd.DataFrame, firm_profile: FirmProfile, risk_profile: RiskProfile, figure:
  SymbolFigure, funnel_config: InspectorFunnelConfig, costs_config: CostsConfig, news_events:
  Sequence[EconomicEvent], dataset_store: RawParquetStore, tick_store: RawParquetStore | None,
  starting_balance: float, window_config: WfaWindowConfig, grid_config: GridConfig) ->
  SignalTrialMatrix` (nombres exactos normativos; firma exacta se cierra en `design.md`).
- **R25** (DEBE). `build_signal_trial_matrix` DEBE reproducir la misma geometría de ventanas IS/OOS
  que `wfa.py` (mismos `WfaWindowConfig`/`GridConfig` públicos, mismo patrón de troceo de `frame`
  por `trading_day` vía `iter_bars`, spec R8-R10 de H) **sin importar ningún símbolo privado de
  `wfa.py`** (`_run_execution_combo`, `_run_single_window`, `_select_winning_signal_config`, etc.).
  `rg -n "from genesis.validation.wfa import|from \.wfa import" src/genesis/validation/dsr_pbo.py`
  DEBE retornar 0 coincidencias que importen símbolos con prefijo `_`.
- **R26** (DEBE). Para cada ventana `k` y cada una de las `GridConfig.signal_configs()` (9 por
  defecto), `build_signal_trial_matrix` DEBE instanciar `CandidateB`/`Simulator` **nuevos** (mismo
  patrón kwargs directos que H, sin `load_candidate_b_config`) sobre el tramo IS de la ventana `k`
  para las 3 combinaciones de ejecución de esa configuración de señal (variando `risk_pct`),
  agregar los trades IS extraídos (`_returns.extract_trade_returns`) y calcular el DSR-IS agregado
  con `n_trials=9` (mismo criterio R26 de H) — esto reconstruye, de forma independiente y
  determinista, exactamente el mismo cálculo intermedio que `wfa.py` ya hizo mientras seleccionaba,
  sin depender de que H lo haya expuesto.
- **R27** (DEBE). `dsr_pbo.py` DEBE definir `SignalTrialMatrix` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `signal_configs: Sequence[tuple[int, float]]` (9 configuraciones),
  `n_windows: int`, `dsr_is_by_window: Sequence[Mapping[tuple[int, float], float]]` (una entrada
  por ventana, mapa configuración de señal → DSR-IS agregado de esa ventana).
- **R28** (DEBE). `dsr_pbo.py` DEBE definir `combinatorial_symmetric_cross_validation(trial_matrix:
  SignalTrialMatrix, n_splits: int | None = None) -> CscvResult` como función **pura**,
  desacoplada de cualquier re-ejecución de backtest (testable con matrices sintéticas pequeñas). Si
  `n_splits is None`, DEBE usar `n_windows` si es par o `n_windows - 1` si es impar (decisión 4,
  §3), con mínimo `4`; en caso contrario `DsrPboConfigError`.
- **R29** (DEBE). `combinatorial_symmetric_cross_validation` DEBE, para cada una de las
  `math.comb(n_splits, n_splits // 2)` combinaciones `C` de bloques (formados agrupando las
  ventanas en `n_splits` bloques contiguos de tamaño ± 1): (a) calcular, para cada configuración de
  señal, el DSR-IS medio sobre los bloques en `C` ("IS-CSCV") y sobre su complemento ("OOS-CSCV");
  (b) seleccionar la configuración con mayor DSR-IS medio en "IS-CSCV" (`n*`); (c) calcular el rango
  relativo `ω ∈ (0, 1)` de `n*` dentro del ranking por DSR-IS medio en "OOS-CSCV" (posición
  normalizada, empates resueltos por promedio de rango); (d) calcular el logit `λ = ln(ω / (1 -
  ω))` (con `ω` recortado a `[ε, 1-ε]`, `ε = 1e-6`, para evitar división por cero en los extremos).
- **R30** (DEBE). `PBO = (número de combinaciones con λ <= 0) / math.comb(n_splits, n_splits //
  2)` (definición estándar de Bailey, Borwein, López de Prado & Zhu, 2015). `dsr_pbo.py` DEBE
  definir `CscvResult` (`@dataclass(frozen=True, slots=True)`) con, como mínimo: `pbo: float`,
  `n_splits: int`, `n_combinations: int`, `logit_by_combination: Sequence[float]`.
- **R31** (DEBE). `math.comb` (stdlib) DEBE usarse para `math.comb(n_splits, n_splits // 2)` — NO
  DEBE usarse `scipy.special.comb` (decisión 8, §3). `rg -n "^import scipy|^from scipy"
  src/genesis/validation/dsr_pbo.py` DEBE retornar 0 coincidencias.
- **R32** (DEBE). `dsr_pbo.py` DEBE definir `run_dsr_pbo(wfa_result: WfaResult, trial_matrix:
  SignalTrialMatrix, n_splits: int | None = None) -> DsrPboResult`, componiendo
  `deflated_sharpe_ratio_gate` (R21) y `combinatorial_symmetric_cross_validation` (R28) en un único
  artefacto congelado: `DsrPboResult` (`@dataclass(frozen=True, slots=True)`) con, como mínimo:
  `candidate_id`, `symbol`, `config_version`, `dsr: float`, `n_trials_signal_total: int`,
  `pbo: float`, `cscv: CscvResult`.
- **R33** (NO DEBE). Ningún campo de `DsrPboResult` NI ninguna función de `dsr_pbo.py` DEBE evaluar
  el umbral G4 (`>= 0.95`) o G5 (`< 25%`) contra un booleano de "pasa/no pasa": solo produce los
  números; la comparación contra el umbral es responsabilidad de `verdict.py` (Issue J), mismo
  criterio R35/R50 de H.
- **R34** (DEBE). Si en `build_signal_trial_matrix` alguna configuración de señal de alguna ventana
  agrega menos de `MIN_TRADES_IS = 10` trades IS (misma constante que H, redefinida localmente sin
  reimportar de `wfa.py`), esa configuración recibe DSR-IS `-inf` en `dsr_is_by_window` para esa
  ventana (mismo criterio de degradación no silenciosa que R26 de H) — no aborta la construcción de
  la matriz completa a menos que **todas** las configuraciones de **todas** las ventanas caigan en
  ese caso, en cuyo punto se lanza `DsrPboConfigError` (R2b).
- **R35** (DEBE). Ninguna excepción de `Simulator`/`RiskLevelsProvider` lanzada durante el re-run de
  `build_signal_trial_matrix` DEBE ser capturada ni envuelta silenciosamente (R6, mismo criterio
  R34/R5 de H).

### 4.5. `sensitivity.py` — perturbación ±10%, stress de costos, definición de acantilado

- **R36** (DEBE). `sensitivity.py` DEBE definir `SensitivityConfig` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `perturbation_fraction: float = 0.10`,
  `cost_stress_multipliers: tuple[float, ...] = (1.5, 2.0)`, `cliff_pf_floor: float = 1.0`,
  `cliff_relative_drop_threshold: float = 0.5`. DEBE validar en `__post_init__` (R3b, R3c).
- **R37** (DEBE). `sensitivity.py` DEBE definir `run_sensitivity(wfa_result: WfaResult, frame:
  pd.DataFrame, symbol: str, firm_profile: FirmProfile, risk_profile: RiskProfile, figure:
  SymbolFigure, funnel_config: InspectorFunnelConfig, costs_config: CostsConfig, news_events:
  Sequence[EconomicEvent], dataset_store: RawParquetStore, tick_store: RawParquetStore | None,
  starting_balance: float, config: SensitivityConfig) -> SensitivityResult` (nombres exactos
  normativos; orden/defaults exactos se cierran en `design.md`).
- **R38** (DEBE). `run_sensitivity` DEBE operar **exclusivamente** sobre `wfa_result.windows[-1]`
  (la ventana WFA más reciente, decisión 5 §3): recupera `winning_combo` (`N, atr_stop_frac,
  risk_pct`) y el tramo OOS de esa ventana (mismo patrón de troceo por `trading_day` que R10 de H,
  reproducido localmente sin importar símbolos privados de `wfa.py`).
- **R39** (DEBE). Para cada uno de los tres ejes (`n_minutes`, `atr_stop_frac`, `risk_pct`) del
  `winning_combo`, `run_sensitivity` DEBE ejecutar exactamente 2 backtests perturbados
  (`valor_ganador × (1 - perturbation_fraction)` y `valor_ganador × (1 + perturbation_fraction)`),
  con los otros dos parámetros fijos en su valor ganador — perturbación independiente eje-por-eje
  (decisión 5, §3), nunca combinada. `rg -n "def run_sensitivity" src/genesis/validation/sensitivity.py`
  DEBE retornar ≥1 coincidencia.
- **R40** (DEBE). `sensitivity.py` DEBE definir `PerturbationOutcome` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `axis: str`, `direction: int` (`-1`/`+1`), `perturbed_value:
  float`, `profit_factor: float`, `relative_drop: float` (`(pf_ganador - pf_perturbado) /
  pf_ganador`, `0.0` si `pf_ganador == 0.0`), `is_cliff: bool` (decisión 6, §3: `True` si
  `profit_factor <= config.cliff_pf_floor` o `relative_drop >= config.cliff_relative_drop_threshold`).
- **R41** (DEBE). `run_sensitivity` DEBE ejecutar, adicionalmente, un backtest por cada valor de
  `config.cost_stress_multipliers` (por defecto `1.5` y `2.0`) sobre el mismo tramo OOS y
  `winning_combo` sin perturbar, reutilizando el parámetro `stress` que `Simulator.__init__` ya
  acepta (`Simulator(..., stress=multiplier)`). `rg -n "stress=" src/genesis/validation/sensitivity.py`
  DEBE retornar ≥1 coincidencia. DEBE definir `CostStressOutcome` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `multiplier: float`, `profit_factor: float`.
- **R42** (DEBE). `sensitivity.py` DEBE definir `SensitivityResult` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `candidate_id`, `symbol`, `config_version`, `baseline_profit_factor:
  float` (del `winning_combo` sin perturbar, sobre el mismo tramo OOS), `perturbations:
  Sequence[PerturbationOutcome]` (6 elementos: 3 ejes × 2 direcciones), `cost_stress:
  Sequence[CostStressOutcome]`, `has_cliff: bool` (`True` si algún `PerturbationOutcome.is_cliff`).
- **R43** (NO DEBE). `sensitivity.py` NO DEBE implementar la perturbación del proxy de volumen del
  Candidato A (fuera de alcance, §1.3). `rg -n "volume_proxy|proxy_volumen" src/genesis/validation/sensitivity.py`
  DEBE retornar 0 coincidencias.
- **R44** (NO DEBE). `sensitivity.py` NO DEBE evaluar el umbral G8 (`< 30%`) ni G9 (`>= 1.15`)
  contra un booleano de pasa/no pasa: solo produce los números (`profit_factor`, `relative_drop`,
  `has_cliff`); la comparación contra el umbral es responsabilidad de `verdict.py` (Issue J).
- **R45** (DEBE). Ninguna excepción de `Simulator`/`RiskLevelsProvider` lanzada durante los re-runs
  de `sensitivity.py` DEBE capturarse ni envolverse silenciosamente (R6).
- **R46** (DEBE). `sensitivity.py` NO DEBE importar `scipy`/`statsmodels`/`matplotlib`/`quantstats`
  (decisión 8, §3). `rg -n "^import scipy|^import statsmodels|^import matplotlib|^import quantstats"
  src/genesis/validation/sensitivity.py` DEBE retornar 0 coincidencias.

### 4.6. Testing (`tests/validation/`)

- **R47** (DEBE). `tests/validation/` DEBE incluir el test de propiedad anti-leakage de R20
  (`purged_cv`), marcado `pytest.mark.unit`.
- **R48** (DEBE). `tests/validation/` DEBE incluir un test de propiedad (`hypothesis`, marcado
  `pytest.mark.unit`) que verifique que el PBO calculado por `combinatorial_symmetric_cross_validation`
  es **invariante al orden** en que se presentan las configuraciones de señal dentro de
  `SignalTrialMatrix.dsr_is_by_window` (permutar las claves del mapa no cambia el `pbo` resultante).
- **R49** (DEBE). `tests/validation/` DEBE incluir un test de propiedad de determinismo total:
  misma `WfaResult`/`frame`/config ⇒ `PurgedCvResult`/`DsrPboResult`/`SensitivityResult`
  bit-idénticos entre dos invocaciones independientes (spec §8: determinismo total). Dado que
  `purged_cv.py` no usa aleatoriedad (R19) y `dsr_pbo.py`/`sensitivity.py` re-ejecutan backtests
  deterministas (mismo patrón que H), no se requiere una semilla explícita adicional en la firma de
  estos módulos — la determinación depende exclusivamente de los insumos (`frame`, configs, ledgers).
- **R50** (DEBE). `tests/validation/` DEBE incluir, marcado `pytest.mark.statistical` (spec §9, fila
  "Estadístico"), al menos: (a) un golden test de `combinatorial_symmetric_cross_validation` con una
  matriz sintética pequeña (p. ej. 2-4 trials × 4-8 ventanas) cuyo PBO se calcula a mano siguiendo
  exactamente R29-R30, comparado con un caso publicado o derivado de la literatura de López de
  Prado (Bailey et al. 2015); (b) un golden test de `run_purged_cv` con un caso de purga+embargo
  calculado a mano (López de Prado, *Advances in Financial Machine Learning*, cap. 7, ejemplo de
  purga con solapamiento conocido). Ninguno de los dos DEBE usar `scipy` como oráculo (decisión 8,
  §3, mismo criterio R22 de H).
- **R51** (DEBE). `tests/validation/` DEBE incluir un golden test de `deflated_sharpe_ratio_gate`
  que confirme, sobre un `WfaResult` sintético con `n_windows` conocido, que `n_trials` efectivo
  pasado a `_dsr.deflated_sharpe_ratio` es `n_windows * 9` (R21, R23).
- **R52** (DEBE). `tests/validation/` DEBE incluir un test unitario que confirme la definición
  operativa de "acantilado" (R40): un caso sintético con `profit_factor <= cliff_pf_floor` y otro
  con `relative_drop >= cliff_relative_drop_threshold` DEBEN marcar `is_cliff=True`; un caso con
  degradación moderada (p. ej. `relative_drop = 0.2`) DEBE marcar `is_cliff=False`.
- **R53** (DEBE). `tests/validation/` DEBE incluir al menos un test de integración
  (`pytest.mark.integration`) que ejecute el pipeline `run_wfa` → `run_purged_cv` +
  `build_signal_trial_matrix` + `run_dsr_pbo` + `run_sensitivity` sobre el fixture sintético
  existente (`short_wfa_frame` de `tests/validation/conftest.py` o un fixture ampliado), en
  segundos, verificando artefactos no vacíos y métricas finitas.
- **R54** (DEBE). `tests/validation/` DEBE incluir al menos un test marcado `pytest.mark.slow` que
  ejerza `build_signal_trial_matrix` (el re-run más costoso: 9 configuraciones × N ventanas) sobre
  un volumen de datos realista, separado de la suite rápida por defecto.
- **R55** (DEBE). `uv run pytest tests/validation/ -v` DEBE pasar en verde (exit code 0), incluyendo
  `uv run pytest tests/validation/ -v -m statistical` en verde (spec §9).

---

## 5. Invariantes transversales

- **R56** (DEBE). Ningún archivo de `src/genesis/data/`, `src/genesis/strategy/`,
  `src/genesis/backtest/`, `src/genesis/validation/wfa.py`, `src/genesis/validation/montecarlo.py`,
  `src/genesis/validation/_dsr.py` ni `src/genesis/validation/window_config.py` DEBE modificarse en
  este Change (`git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
  src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py src/genesis/validation/_dsr.py
  src/genesis/validation/window_config.py` vacío).
- **R57** (DEBE). Solo trades OOS DEBEN alimentar `run_purged_cv`, `deflated_sharpe_ratio_gate` y
  `run_sensitivity` (spec §6.1, "regla sin excepción"); `build_signal_trial_matrix` es la única
  excepción documentada — usa trades **IS** deliberadamente porque reconstruye la métrica de
  selección IS del WFA (DSR-IS), nunca la usa como sustituto de OOS en el DSR/PF normativos de los
  gates.
- **R58** (NO DEBE). Este Change NO DEBE añadir `scipy` ni `statsmodels` a `pyproject.toml`
  (`[project.dependencies]` ni `dependency-groups.dev`) — decisión 8, §3. `rg -n
  "scipy|statsmodels" pyproject.toml` DEBE no mostrar ninguna de esas dependencias añadida respecto
  al estado previo al Change.
- **R59** (DEBE). Toda excepción de dominio nueva de este Change DEBE heredar de
  `GenesisValidationError` y llevar mensaje con contexto explícito (R4-R5).
- **R60** (DEBE). `src/genesis/validation/__init__.py` DEBE extender su `__all__` mínimo y curado
  con, como mínimo: `PurgedCvConfigError`, `DsrPboConfigError`, `SensitivityConfigError`,
  `PurgedCvConfig`, `PurgedCvResult`, `run_purged_cv`, `DsrPboResult`, `run_dsr_pbo`,
  `SensitivityConfig`, `SensitivityResult`, `run_sensitivity` — NUNCA `_returns.py`
  (`extract_trade_returns`/`TradeReturn`) ni `build_signal_trial_matrix`/`SignalTrialMatrix` si
  `design.md` los mantiene como detalle interno de `dsr_pbo.py` (a decidir en `design.md`, sin
  bloquear este documento).
- **R61** (DEBE). Ningún artefacto de este Change (`PurgedCvResult`, `DsrPboResult`,
  `SensitivityResult`, `SignalTrialMatrix`) DEBE serializarse a disco (Parquet/JSON) — estructuras
  en memoria únicamente (decisión 10, §3).
- **R62** (DEBE). `uv run mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/validation/` y `tests/validation/` extendidos.
- **R63** (DEBE). El loop de re-runs de `build_signal_trial_matrix` (9 configs × N ventanas × 3
  `risk_pct`) y de `run_sensitivity` (8 backtests) DEBE ejecutarse de forma secuencial (sin
  `multiprocessing`/`concurrent.futures`). `rg -n "multiprocessing|concurrent\.futures"
  src/genesis/validation/dsr_pbo.py src/genesis/validation/sensitivity.py` DEBE retornar 0
  coincidencias.

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `PurgedCvConfigError` | `genesis.validation.errors` | `n_folds<2`; `embargo_days<0`; fold train/test vacío tras purga+embargo (R16); `oos_ledger` con menos trades que `n_folds` | Aborta `run_purged_cv` antes de (o durante) la construcción del fold afectado |
| `DsrPboConfigError` | `genesis.validation.errors` | `n_windows<4`; todas las configuraciones de todas las ventanas por debajo de `MIN_TRADES_IS` (R34); `n_splits` no par o `> n_windows` | Aborta `build_signal_trial_matrix`/`run_dsr_pbo` antes de intentar CSCV |
| `SensitivityConfigError` | `genesis.validation.errors` | `wfa_result.windows` vacío; `cost_stress_multipliers` con valor `<=1.0`; umbrales de acantilado fuera de rango | Aborta `run_sensitivity` antes de ejecutar cualquier backtest |
| (heredado, propagado sin envolver) `BacktestConfigError` | `genesis.backtest.errors` | Candidato/config inválida durante un re-run invocado por `dsr_pbo.py`/`sensitivity.py` | Aborta la función que lo invocó (R35/R45) |
| (heredado, propagado sin envolver) `SessionBoundaryError` | `genesis.backtest.errors` | Posición viva tras cierre de sesión durante un re-run | Aborta la función que lo invocó (R35/R45) |
| (heredado, sin cambios) `WfaConfigError`, `MonteCarloConfigError` | `genesis.validation.errors` | Sin cambios respecto a H | N/A para este Change (no se invocan `run_wfa`/`monte_carlo_*` desde estos tres módulos) |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/validation/errors.py
CUANDO rg -n "class PurgedCvConfigError" src/genesis/validation/errors.py
       y rg -n "class DsrPboConfigError" src/genesis/validation/errors.py
       y rg -n "class SensitivityConfigError" src/genesis/validation/errors.py
ENTONCES las tres retornan >=1 coincidencia; las tres heredan de GenesisValidationError (R1-R5)
```

```
DADO   un Ledger sintético con trades OOS de duración e intervalos conocidos
CUANDO se invoca run_purged_cv(ledger, PurgedCvConfig(n_folds=5))
ENTONCES ningún trade del fold de train de cualquier k tiene [entry_timestamp, exit_timestamp]
         solapado con el intervalo del fold de test k tras purga+embargo (R15, R20)
```

```
DADO   un fold de train o test que quedaría vacío tras purga+embargo
CUANDO se invoca run_purged_cv(...) con esa configuración
ENTONCES se lanza PurgedCvConfigError (R16)
```

```
DADO   un WfaResult sintético con n_windows conocido
CUANDO se invoca dsr_pbo.deflated_sharpe_ratio_gate(wfa_result)
ENTONCES internamente se invoca _dsr.deflated_sharpe_ratio con n_trials == n_windows * 9
         (== wfa_result.n_trials_signal_total), no con n_windows * 27 (R21, R23)
```

```
DADO   el archivo src/genesis/validation/dsr_pbo.py
CUANDO rg -n "from genesis.validation.wfa import" src/genesis/validation/dsr_pbo.py
ENTONCES no importa ningún símbolo con prefijo "_" de wfa.py (R25)
```

```
DADO   una SignalTrialMatrix sintética de 4 trials x 8 ventanas con un PBO calculado a mano
       siguiendo R29-R30
CUANDO se invoca combinatorial_symmetric_cross_validation(trial_matrix, n_splits=8)
ENTONCES el pbo retornado coincide con el valor calculado a mano dentro de una tolerancia numérica
         fijada en el propio test, sin invocar scipy en ningún punto (R28-R31, R50a)
```

```
DADO   n_windows < 4 en el WfaResult de entrada
CUANDO se invoca build_signal_trial_matrix(...) o run_dsr_pbo(...)
ENTONCES se lanza DsrPboConfigError antes de construir ninguna combinación CSCV (R2a)
```

```
DADO   el archivo src/genesis/validation/sensitivity.py
CUANDO rg -n "def run_sensitivity" src/genesis/validation/sensitivity.py
       y rg -n "stress=" src/genesis/validation/sensitivity.py
       y rg -n "volume_proxy|proxy_volumen" src/genesis/validation/sensitivity.py
ENTONCES las dos primeras retornan >=1 coincidencia; la tercera retorna 0 (R37, R41, R43)
```

```
DADO   un caso sintético con profit_factor <= cliff_pf_floor
       y otro con (pf_ganador - pf_perturbado) / pf_ganador >= cliff_relative_drop_threshold
       y otro con relative_drop == 0.2 (degradación moderada, sin acantilado)
CUANDO se construye PerturbationOutcome para cada caso
ENTONCES los dos primeros tienen is_cliff=True y el tercero is_cliff=False (R40, R52)
```

```
DADO   un WfaResult con >=1 ventana y un frame/config compatible
CUANDO se invoca run_sensitivity(wfa_result, ...)
ENTONCES el SensitivityResult contiene exactamente 6 PerturbationOutcome (3 ejes x 2 direcciones)
         y 2 CostStressOutcome (multiplicadores 1.5 y 2.0 por defecto), todos con profit_factor
         finito (R39, R41-R42)
```

```
DADO   el archivo pyproject.toml tras completar este Change
CUANDO rg -n "scipy|statsmodels" pyproject.toml
ENTONCES no muestra ninguna de esas dependencias añadida a [project.dependencies] ni a
         dependency-groups.dev respecto al estado previo al Change (R58)
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
       src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py
       src/genesis/validation/_dsr.py src/genesis/validation/window_config.py
ENTONCES no retorna ninguna línea (R56)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/validation/ -v
ENTONCES pasa en verde, incluyendo:
         - >=1 test de propiedad anti-leakage de Purged K-Fold (R20, R47)
         - >=1 test de propiedad de invariancia al orden del PBO (R48)
         - >=1 test de propiedad de determinismo total (R49)
         - >=2 golden tests marcados pytest.mark.statistical contra casos de López de Prado
           (CSCV/PBO y purged K-fold, R50)
         - >=1 golden test del n_trials efectivo del DSR de gate (R51)
         - >=1 test unitario de la definición de "acantilado" (R52)
         - >=1 test de integración del pipeline completo en segundos (R53)
         - >=1 test marcado pytest.mark.slow de build_signal_trial_matrix en volumen realista (R54)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/validation/ -v -m statistical
       y uv run mise run ci
ENTONCES ambos pasan en verde (exit code 0, R55, R62)
```

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | `deflated_sharpe_ratio_gate` con `n_trials=9` (decisión 1, §3) podría interpretarse como menos conservador que usar 27; si una auditoría externa exige el conteo de ejecución, el gate G4 quedaría subestimado en severidad. | Un candidato marginal podría pasar G4 con 9 trials y no con 27. | `n_trials` es un argumento explícito derivado de un único campo de `WfaResult` (R23) — revertir a `n_trials_execution_total` es un cambio de una línea; la justificación textual del spec §6.2 queda citada en este documento para trazabilidad de auditoría. |
| Rg-2 | `build_signal_trial_matrix` reconstruye por completo el grid IS de 9 configuraciones × N ventanas (mismo volumen que el propio `wfa.py`, aunque solo IS, no OOS) — es el re-run más costoso de este Change y duplica esencialmente el trabajo de selección de H sin poder evitarlo (WfaResult no expone las 8 configuraciones descartadas por diseño de H). | Runtime de `dsr_pbo.py` comparable al de `wfa.py`; en CI puede requerir el mismo marcador `slow` que H ya usa para su grid completo. | R54 exige explícitamente un test `slow` separado; el test de integración rápido (R53) usa un fixture reducido (`short_wfa_frame`, pocas ventanas) para mantener la suite por defecto en segundos. |
| Rg-3 | `S`/`n_splits` de CSCV limitado por `n_windows` (decisión 4, §3: `S ≤ n_windows`) — con historias WFA de pocas ventanas (p. ej. 2-3 años de datos ⇒ 4-6 ventanas OOS de 6 meses), el mínimo `S=4` puede dejar muy pocas combinaciones `C(4,2)=6`, reduciendo la resolución estadística del PBO. | PBO poco informativo (alta varianza) en historias cortas. | `DsrPboConfigError` fail-fast si `n_windows < 4` (R2a) documenta el piso mínimo explícitamente; `verdict.py` (Issue J) puede tratar un PBO de baja resolución como señal de alerta adicional, no oculta el problema. |
| Rg-4 | Definición operativa de "acantilado" (decisión 6, §3) es una elección de diseño sin respaldo numérico directo del spec (que solo dice "sin acantilados"); los umbrales `cliff_pf_floor=1.0`/`cliff_relative_drop_threshold=0.5` podrían resultar demasiado laxos o estrictos frente a la volatilidad real de PF del Candidato B. | Un umbral mal calibrado podría dejar pasar sobreajuste real o rechazar candidatos válidos. | Ambos umbrales son parámetros explícitos de `SensitivityConfig` (R36), nunca constantes hardcodeadas — recalibrables sin rediseño; documentados con su justificación relativa a G8 (el doble de estricto que la degradación general de 30%). |
| Rg-5 | `run_sensitivity` opera solo sobre la última ventana WFA (decisión 5, §3) — si el candidato mostrara alta variabilidad de robustez entre ventanas (una ventana temprana muy sensible, la última no), G8/G9 no lo detectarían. | Falso negativo de robustez si la última ventana no es representativa del comportamiento histórico completo. | Documentado explícitamente como decisión de diseño (última ventana = candidata a incubación en vivo, spec §10); si `design.md`/una iteración futura decide extender a todas las ventanas, el costo crece linealmente y requiere revisar el marcador `slow` (Rg-2 análogo). |
| Rg-6 | Igual que Rg-1 de H: `CandidateB` reinstanciado en frío (`atr_value=None`) en cada re-run de `build_signal_trial_matrix`/`sensitivity.py` — mismos primeros `atr_period` (14) días sin componente ATR completo. | Menor efecto en tramos OOS más cortos (una sola ventana en `sensitivity.py`) que en H (252 días IS de margen). | Aceptado como comportamiento heredado del Candidato B (Issue E), documentado explícitamente; `OOS_WINDOW_TRADING_DAYS=126` (H) sigue dando margen razonable (14/126) sobre el sesgo. |
| Rg-7 | La definición de "trade" (§2, R7-R8: par `entry_fill (is_exit=False)` → siguiente `exit_fill (is_exit=True)` del mismo símbolo) asume que el Candidato B nunca mantiene más de una posición abierta simultánea por símbolo. Si un candidato futuro (o una extensión del B) permitiera posiciones concurrentes, el pareado secuencial de `_returns.extract_trade_returns` produciría horizontes de trade incorrectos. | Horizonte de purga (Purged K-Fold) o extracción de retornos corrupta para un candidato con concurrencia de posiciones. | Documentado explícitamente como supuesto válido para el alcance actual (único candidato implementado, Candidato B, spec §2.3: rango de apertura único por día); `design.md`/un Change futuro que introduzca concurrencia de posiciones debe revisar `_returns.py` antes de reutilizarlo. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Firma exacta (orden de parámetros, kw-only vs. posicional, defaults) de `run_purged_cv`,
  `build_signal_trial_matrix`, `run_dsr_pbo`, `run_sensitivity` — se resuelve en `design.md`
  respetando el comportamiento normativo de esta especificación (R12, R24, R32, R37).
  - **Nota de progreso**: al momento de redactar este `spec.md`, el change dir ya contiene un
    `design.md`/`tasks.md` no vacíos (fase `specify` en curso según `state.yaml`); este documento
    no los inspecciona ni los valida — es responsabilidad de la fase `design` verificar que
    respeten los requisitos aquí fijados, o corregirlos si divergen.
- Si `build_signal_trial_matrix`/`SignalTrialMatrix` y `extract_trade_returns`/`TradeReturn` se
  exportan en `__init__.__all__` (superficie pública reutilizable por Issue J) o se mantienen como
  detalle interno de `dsr_pbo.py`/`_returns.py` — R60 fija el mínimo obligatorio sin bloquear una
  superficie más amplia si `design.md` lo justifica.
- Si el `S` de CSCV debería ser configurable por el llamador de `run_dsr_pbo` más allá del default
  determinista de R28, o si el spec de un futuro Issue (J) requiere un valor fijo institucional
  — se difiere hasta que exista un caso de uso concreto.
- Si la extensión de `sensitivity.py` a todas las ventanas WFA (en vez de solo la última, decisión
  5 §3) debería revisarse una vez que exista historia real de The5ers (Issue B) que muestre
  variabilidad significativa de robustez entre ventanas — riesgo Rg-5, sin evidencia hoy de que sea
  necesario.

---

## 10. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/12.
- `idea.md` / `proposal.md` de este Change (fases explore/propose) — hipótesis de solución y 10
  decisiones/posturas resueltas definitivamente en este documento (§3), con dos correcciones
  explícitas (CSCV multi-trial, decisión 4; no introducción de `scipy`/`statsmodels`, decisión 8).
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §2.5 (aislamiento entre
  candidatos, T1 exclusivo de `verdict.py`), §3 ("núcleo propio, periferia pragmática"), §6 (tabla
  capa 4), §6.1 (flujo, reglas sin excepción), §6.2 (presupuesto de grid 27/9, distinción de
  conteo para el DSR), §7.1 (gates G4/G5/G8/G9), §7.4 (gate T1), §7.6 (sanity-check G4/T1, `ln(27)
  ≈ 3.30`), §8 (errores, determinismo total), §9 (testing, fila "Estadístico" — única que nombra
  `dsr_pbo`/`purged_cv` explícitamente), §11 (tabla de issues, H bloquea I, I bloquea J), §11.1
  (PA-5), §11.2 (dependencias de runtime del proyecto, `scipy`/`statsmodels` declaradas pero no
  obligatorias de introducir en cada Issue).
- `src/genesis/validation/wfa.py` — `WfaResult` (`n_trials_signal_total`/`n_trials_execution_total`
  líneas 89-90, `_N_TRIALS_SIGNAL=9`/`_N_TRIALS_EXECUTION=27` líneas 50-51), `WindowResult`
  (`is_ledger_winning`, `oos_ledger`, `dsr_is` — solo la combinación ganadora, líneas 55-75),
  `_extract_exit_returns` (línea 94, patrón replicado y extendido por `_returns.py`).
- `src/genesis/validation/_dsr.py` — `deflated_sharpe_ratio(returns, n_trials) -> float` (línea 98,
  reutilizada tal cual por `dsr_pbo.deflated_sharpe_ratio_gate`), `_standard_normal_cdf`/
  `_standard_normal_ppf` (Acklam+Halley, stdlib puro, sin `scipy`).
- `src/genesis/validation/window_config.py` — `WfaWindowConfig`, `GridConfig`
  (`signal_configs()`/`execution_combos()`, líneas 92-106), `_grid_config_hash`,
  `window_identity_hash` — geometría pública reutilizada por `build_signal_trial_matrix` sin
  modificación.
- `src/genesis/validation/errors.py` — `GenesisValidationError`, `WfaConfigError`,
  `MonteCarloConfigError` — patrón de jerarquía propia extendido con
  `PurgedCvConfigError`/`DsrPboConfigError`/`SensitivityConfigError`.
- `src/genesis/validation/__init__.py` — `__all__` curado (R65 de H, nunca reexporta `_dsr.py`);
  este Change extiende el patrón sin reexportar `_returns.py` (R10).
- `src/genesis/backtest/ledger.py` — `FillRecord` (`timestamp_utc`, `is_exit`, `equity_after`,
  líneas 62-72), `Ledger`, `RunProvenance` — base de `_returns.TradeReturn`/`extract_trade_returns`.
- `src/genesis/backtest/simulator.py` — `Simulator.__init__` (`stress: float = 1.0`, línea 227,
  reutilizado tal cual por `sensitivity.py` para el stress de costos de G9).
- `src/genesis/strategy/candidate_b/candidate.py` — `CandidateB.__init__` (kwargs directos
  `n_minutes`, `risk_pct`, `atr_stop_frac`, líneas 56-67; una única posición abierta por símbolo a
  la vez, base del supuesto de Rg-7).
- `pyproject.toml` — `scipy`/`statsmodels` ausentes de `[project.dependencies]` y de
  `dependency-groups.dev` (confirmado, no se añaden en este Change); marcador `statistical` ya
  registrado (línea ~80) sin uso previo, primer consumidor de este Change.
- `.pulse/changes/archive/10-h-feat-validation-wfa-grid-is-dsr-is-wfe-monte-carlo-s-mbolo-y-p/
  spec.md` — formato y estilo replicado (R1..Rn, tabla de resolución de decisiones, criterios
  DADO/CUANDO/ENTONCES, tabla de riesgos); precedentes directamente contrastados (ADR-H5, decisión
  4 de "núcleo propio sin `scipy`" ahora extendida por tercera vez).
- `tests/validation/conftest.py`, `tests/validation/test_dsr.py`, `tests/validation/
  test_wfa_lookahead.py`, `tests/validation/test_wfa_determinism.py` — patrones de fixtures y tests
  a replicar/extender para `test_returns.py`, `test_purged_cv.py`, `test_dsr_pbo.py`,
  `test_sensitivity.py`.
- Referencias externas citadas por el spec y esta especificación: Bailey, D. H. & López de Prado, M.
  (2014). "The Deflated Sharpe Ratio..."; Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q.
  J. (2015). "The Probability of Backtest Overfitting" (definición exacta de PBO/CSCV, R28-R30);
  López de Prado, M. (2018). *Advances in Financial Machine Learning*, cap. 7 (Purged K-Fold con
  embargo, R15) y cap. 11 (CSCV).
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, flujo SDD, cadena de dependencias
  A→B→C→{D/E,G}→H→I→J→K.

<!-- change:14-j-feat-validation-prop-sim-verdict-con-gates-t-tearsheet-manifes -->
<!-- change:14-j-feat-validation-prop-sim-verdict-con-gates-t-tearsheet-manifes -->
# Specification: `prop_sim.py` + `verdict.py` con gates T + tearsheet + manifest (Issue #14 / J)

SSoT: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` (en adelante «el spec») — §1.1, §1.2,
§1.3, §2.4, §2.5, §3, §6, §6.1, §6.2, §7.1–§7.6, §8, §9, §11, §11.2. Este documento formaliza
`idea.md` y `proposal.md` de este Change en requisitos verificables. Los gates G/C/P/T del spec
**nunca se relajan**; ningún requisito de este documento puede contradecirlos. Este Change cierra
la capa 4 de validación (`src/genesis/validation/`) con `prop_sim.py` (economía prop a nivel de
cuenta, gates P1–P6) y `verdict.py` (agregación G+C+P por candidato, deflación de torneo T1,
ensemble T2, veredicto, tearsheet y manifest reproducible) — último módulo del camino crítico
A → B → C → {E, G} → H → I → **J**, habilita K (Candidato C + ensemble).

Convención de rutas: el spec usa pseudocódigo `python/validation/...` (§6); el repo real usa
`src/genesis/validation/...`. Todas las rutas de este documento son las reales del repo.

Este documento **corrige una decisión de `proposal.md` con evidencia técnica nueva** (§3, decisión
4): la propuesta de usar `metrics.worst_daily_floating_excursion` (`src/genesis/backtest/
metrics.py:86-93`) como "factor de ensanchamiento" del proxy de base dual de P3 es inviable —
verificado en código, esa función retorna `max(magnitudes de BreachEvent(DAILY), default=0.0)`:
es **idénticamente `0.0`** para cualquier `Ledger` OOS sin infracciones diarias registradas, y el
gate P6 (§7.3: "Violaciones de reglas de firma en simulación OOS = 0") **garantiza exactamente esa
condición** para todo candidato que llega a `prop_sim.py`/`verdict.py`. La función no puede
"ensanchar" nada: es cero en el escenario en el que `prop_sim.py` la necesitaría. Este documento
fija una resolución distinta (§3, decisión 4; R33-R35).

---

## 1. Objetivo y alcance

### 1.1. Objetivo

Cerrar la capa 4 de validación con dos módulos nuevos — `src/genesis/validation/prop_sim.py` y
`src/genesis/validation/verdict.py` — que consumen exclusivamente la API pública ya cerrada de H
(`WfaResult`, `McSymbolResult`, `McPortfolioResult`) e I (`DsrPboResult`, `SensitivityResult`,
`PurgedCvResult`) y la de las capas 1-3 (`FirmProfile`, `RiskProfile`, `Ledger`, `ArtifactMetadata`),
sin modificar ningún archivo de esas capas. `prop_sim.py` aplica la ficha de economía del challenge
a trayectorias de portafolio resampleadas desde `oos_ledgers_by_symbol`, produciendo los insumos de
los gates P1-P6. `verdict.py` agrega G+C+P por candidato, aplica T1 (deflación de torneo) y T2
(ensemble), y emite el veredicto de torneo (§7.5) con tearsheet Markdown y manifest JSON
reproducible con un comando — sin esto, ningún candidato recibe veredicto y K (Candidato C +
ensemble) queda bloqueado (spec §11).

### 1.2. Alcance IN

- `src/genesis/validation/errors.py` (extendido, sin tocar las clases existentes de H/I):
  `PropSimConfigError`, `VerdictConfigError`.
- `src/genesis/validation/prop_sim.py`: `PhaseSpec`, `PropEconomicsProfile`,
  `load_prop_economics_profile`, `prop_economics_profile_hash`, `PropSimConfig`,
  `PropSimOutcomeKind`, `PathOutcome`, `PropSimResult`, `simulate_challenge_paths`,
  `run_prop_sim`.
- `src/genesis/validation/verdict.py`: `CandidateValidationBundle`, `SymbolGateOutcome`,
  `CandidateGateSummary`, `VerdictKind`, `EnsembleResult`, `VerdictResult`, `run_verdict`,
  `render_tearsheet`, `write_verdict_artifacts`.
- `src/genesis/validation/__init__.py`: extensión del `__all__` mínimo y curado (patrón R65 de H,
  R60 de I) con la superficie normativa de este Change.
- Fixture JSON empaquetado de `PropEconomicsProfile` para The5ers (nombre/ruta exactos se fijan en
  `design.md`, colocado junto a `prop_sim.py` en `src/genesis/validation/`, mismo patrón de
  empaquetado de `risk_profile.json`).
- `tests/validation/`: `test_prop_economics.py`, `test_prop_sim.py`, `test_verdict.py`, extensión de
  `conftest.py`/`fixtures/` según necesidad, con los niveles unit/property/golden/integración/slow
  del spec §9.

### 1.3. Alcance OUT (YAGNI explícito)

- **CLI completo** (`prop-sim`, `verdict`, `full-validation`, spec §6): diferido, mismo criterio
  consistente en G/H/I (funcionalidad de librería primero, sin caso de uso verificable de CLI
  todavía). `rg -n "argparse|\[project\.scripts\]"` sobre este Change no debe mostrar adiciones.
- **Candidato C (TSMOM) implementación real**: Issue K. Solo su universo de 11 símbolos (§2.4) es
  referencia normativa para calcular el DSR de torneo cuando K exista; `n_candidatos_torneo` de
  este Change es siempre el conteo real de candidatos pasados a `run_verdict`, nunca hardcodeado a 3.
- **Ejecución real del ensemble** (asignación de capital en vivo, puente de ejecución): T2 solo
  *valida* la elegibilidad del ensemble como candidato adicional con su propio `prop_sim`
  (`simulate_challenge_paths` sobre la canasta ponderada por vol-inversa); la ejecución real es
  post-veredicto (§10.3, fuera de v1).
- **Puente de ejecución** hacia MT5/cTrader (§10.3): fuera de v1, cadena de issues propia.
- **Confirmación de campos de ficha The5ers** (PA-1/PA-2 de B): no reabierto salvo que bloquee un
  campo requerido por `prop_sim` directamente.
- **Extensión de `montecarlo.py`** (Opción (a) del hallazgo crítico de granularidad, idea.md): se
  rechaza explícitamente — `prop_sim.py` reimplementa localmente su propio resampleo diario
  (R15-R22), sin modificar `montecarlo.py` ni importar sus símbolos privados.
- **Modificación de cualquier archivo bajo `src/genesis/data/`, `src/genesis/strategy/`,
  `src/genesis/backtest/`**, ni de `wfa.py`, `montecarlo.py`, `_dsr.py`, `window_config.py`,
  `dsr_pbo.py`, `sensitivity.py`, `purged_cv.py`, `_returns.py`, `_windowing.py` (capa 4 ya cerrada
  por H/I): `git diff --stat` sobre esos árboles DEBE quedar vacío (R125).
- **Dependencias de runtime nuevas** (`scipy`/`statsmodels`/`matplotlib`/`quantstats`): no se
  introducen — percentiles (`numpy.percentile`), correlación (`numpy.corrcoef`), aritmética de la
  máquina de estados y `_dsr.deflated_sharpe_ratio` (ya sin `scipy`) cubren íntegramente las
  necesidades de este Change, extendiendo "núcleo propio, periferia pragmática" (spec §3) una
  cuarta vez consecutiva (G, H, I, J).
- **Persistencia a disco dentro de `prop_sim.py`**: `PropSimResult`/`PathOutcome` son dataclasses
  congeladas en memoria (mismo patrón ligero de H/I); solo `verdict.py`
  (`write_verdict_artifacts`) serializa manifest/tearsheet a disco.
- **Histograma completo de distribución de intentos** como parte obligatoria de la API pública: se
  documentan media + `p50`/`p90` (`PropSimResult.expected_attempts*`); un histograma detallado
  queda como detalle de implementación no normativo.
- **Paralelismo** (`multiprocessing`/`concurrent.futures`): loop secuencial de trayectorias, mismo
  criterio de G/H/I; tests de volumen realista marcados `pytest.mark.slow`.
- **`purged_cv.py` como insumo normativo de gate**: `PurgedCvResult` se adjunta al manifest de
  `verdict.py` como diagnóstico **informativo**, sin participar en la lógica booleana G/C/P/T
  (ningún gate del spec §7 lo referencia).
- **Escenario golden "triple rollover"** (spec §9) en `prop_sim.py`: los deltas diarios que
  `prop_sim.py` resamplea provienen de `oos_ledgers_by_symbol` ya netos de swap/costos (aplicados
  por `Simulator`/`costs.py` en G, Issue #6) — el triple swap de miércoles ya está cubierto por la
  suite de costos de capa 3 (G); `prop_sim.py` no reimplementa esa cobertura.

---

## 2. Convenciones de esta especificación

- Los requisitos usan **DEBE** (MUST) y **NO DEBE**, numerados `R1..Rn` (numeración propia de este
  Change, no continúa la de H/I), cada uno verificable por al menos un test o una aserción `rg`/`fd`.
- Nombres de funciones/clases/excepciones/constantes son **normativos**; firmas exactas (orden,
  kw-only vs. posicional, defaults no fijados aquí) se resuelven en `design.md` respetando el
  comportamiento descrito aquí.
- Identificadores en inglés, docstrings y mensajes de error en español.
- **"Canasta diaria"** (compartida por `prop_sim.py` y `verdict.py`, patrón de `montecarlo.py`,
  duplicación deliberada ADR-H5/ADR-I1): agrupación de `(symbol, delta)` por `trading_day` sobre
  todos los símbolos de un candidato, sumando los deltas del mismo día en un único P&L de canasta
  (`daily_totals: Mapping[date, float]`) — mismo criterio de `_build_basket`/
  `_extract_exit_returns_by_day` de `montecarlo.py:287-301,268-284`, **reimplementado localmente**
  en `prop_sim.py` (`_build_daily_basket`, R15-R17) y reutilizado (no reimportado como símbolo
  privado de otro módulo) por `verdict.py` para T1/T2/ensemble (R71, R79-R83) — ambos módulos de
  este mismo Change comparten la reimplementación entre sí (mismo criterio ADR-I1 de compartir
  dentro de un único Change), pero ninguno importa símbolos con prefijo `_` de
  `montecarlo.py`/`wfa.py`/`dsr_pbo.py`.
- **Gates P a nivel de cuenta, nunca por símbolo** (spec §6.1): `prop_sim.py` opera siempre sobre la
  canasta combinada de todos los símbolos del universo de un candidato (o del ensemble), nunca
  evalúa P1-P6 símbolo por símbolo.
- **Determinismo total**: todo RNG nuevo es `numpy.random.default_rng(seed)` explícito; `seed` es un
  argumento requerido sin default en las funciones públicas de `prop_sim.py`.

---

## 3. Resolución de las decisiones abiertas de `idea.md`/`proposal.md`

| # | Decisión pendiente | Resolución de este documento | Requisitos |
|---|---|---|---|
| 1 | Ubicación de `PropEconomicsProfile`/ficha de economía del challenge | Vive en `prop_sim.py` (capa 4), no en `RiskProfile`/capa 3 (ningún consumidor de `Simulator` necesita `profit_split`/`payout_cycle`) — confirma la hipótesis de `proposal.md`. Nombre/ruta exacta del fixture JSON empaquetado se fija en `design.md` (no bloquea este documento, mismo criterio que I dejó abierta la firma exacta de sus funciones). | R7-R14 |
| 2 | Valores default de `challenge_cost`/`profit_split`/`payout_cycle` | `payout_cycle_days=14` es **definitivo** (spec §1.3: "payouts quincenales", no es un placeholder). `challenge_cost_pct_of_balance=3.0` y `profit_split_pct=80.0` son **placeholders conservadores explícitos, "a confirmar"** (mismo patrón textual que `FirmProfile` aplicó a `daily_reset_time`, `data/profile.py:30-37`) — no bloquean el código; el tearsheet DEBE marcar el veredicto como "economía no confirmada" mientras esos dos campos no se actualicen desde el fixture default (R14, R107). | R9, R14, R107 |
| 3 | Techo de intentos por trayectoria | `PropSimConfig.max_attempts: int = 10` (constante configurable, sin cifra en el spec) — documentado como "techo operativo de simulación", no como regla de negocio de la firma. | R23, R25 |
| 4 | **Base dual de P3 sobre trayectorias MC — corrige `proposal.md`** | `metrics.worst_daily_floating_excursion` (`backtest/metrics.py:86-93`) es idénticamente `0.0` para cualquier `Ledger` OOS sin `BreachEvent(DAILY)` — condición que P6 (§7.3) garantiza para todo candidato que llega a `prop_sim.py`. No sirve como "factor de ensanchamiento". Resolución: `prop_sim.py` evalúa P3 **únicamente sobre la base de balance al cierre del día anterior** (`daily_loss = max(0, balance_inicio_día - balance_fin_día)` contra `firm_profile.daily_loss_limit_pct`) — la pierna de balance-a-balance de la base dual (§1.3/§7.3), que el resampleo diario **sí reproduce exactamente** (los deltas resampleados ya son cierre-a-cierre). La pierna de equity flotante intradía real (`simulator.py:358-378`, resolución M1) **no es reconstruible** desde P&L diario agregado sin re-simular M1 — se documenta explícitamente como limitación aceptada, sesgo conocido hacia subestimar P3 (el breach real puede disparar antes, intradía, de lo que el proxy de cierre-a-cierre detecta). Esto se declara en el tearsheet (R107) como "P3 es una cota inferior conservadora sobre la base intradía". | R33-R35, R107 |
| 5 | Tratamiento de trayectorias "en curso" al cierre del horizonte de 12 meses | Censura por la derecha (Kaplan-Meier simplificado): trayectorias fondeadas que llegan al fin del horizonte sin breach total cuentan como supervivencia `≥ horizon_months` para P4; si más del 50% de las trayectorias fondeadas sobreviven el horizonte completo, `median_funded_survival_months = horizon_months` (mediana censurada, documentada explícitamente, R47). Trayectorias nunca fondeadas (challenge agotado o en curso al fin del horizonte de la ruta simulada) no contribuyen a P4; contribuyen `net_payout_12m=0.0` a P5 (R44-R46, R51). | R44-R47, R51 |
| 6 | Formato exacto de tearsheet y manifest | Tearsheet **Markdown puro** (sin `quantstats`/`matplotlib`, ninguna necesidad real de código verificada, confirma `proposal.md`); manifest **JSON** con metadata extendida tipo `ArtifactMetadata` (patrón `to_json`/`from_json`, `data/metadata.py:50-98`). Ambos se generan desde el mismo `VerdictResult` (única fuente de verdad). `write_verdict_artifacts(result, output_dir)` escribe `manifest.json` + `tearsheet.md` en `output_dir` (provisto explícitamente por el llamador — sin ruta por defecto hardcodeada, coherente con la ausencia de CLI en este Change). | R96-R108 |
| 7 | Alcance de `PurgedCvResult` en el manifest | Diagnóstico informativo: si `CandidateValidationBundle.purged_cv_results_by_symbol` no es `None`, el manifest incluye un resumen por símbolo (`n_folds`, `total_trades`, `purged_trade_count` total) — nunca participa en la lógica booleana de veredicto. | R98, R106 |
| 8 | Fórmula exacta de deflación T1 | `n_trials_deflactado = n_trials_signal_total_candidato_ganador + (n_candidatos_torneo - 1)`, donde `n_trials_signal_total_candidato_ganador = sum(wfa_result.n_trials_signal_total for wfa_result in bundle.wfa_results_by_symbol.values())` (spec §6.1: "trials contados mecánicamente **por candidato**" — soporte textual directo para sumar entre símbolos del mismo candidato) y `n_candidatos_torneo = len(candidates)` (nunca hardcodeado, nunca fijo a 3). Interpretación: elegir el mejor de N candidatos añade `N-1` trials de selección adicionales al conteo de señal ya acumulado del ganador (Bailey/López de Prado: la deflación es función del número total de comparaciones consideradas en la selección). El DSR de T1 se calcula sobre la **canasta diaria combinada** del candidato ganador (mismo criterio "a nivel de cuenta" de P, no una concatenación de trades por símbolo fuera de orden temporal). | R71-R78 |
| 9 | Reutilización de semillas MC vs. `prop_sim` | `prop_sim.py` usa un `seed` **independiente** del de `monte_carlo_portfolio` (las trayectorias reducidas de `McPathsResult` no contienen la serie diaria necesaria, R18-R19); documentado explícitamente en el manifest (`prop_sim_seed` por candidato, distinto de `mc_seed`). | R19, R98 |
| 10 | Granularidad de `tasks.md` (recomendación, no bloquea `specify`) | Se recomienda partir `tasks.md` en dos bloques secuenciales dentro del mismo Change: (a) ficha + resampleo + máquina de estados de `prop_sim.py`; (b) agregación G+C+P+T1+T2+veredicto+tearsheet+manifest de `verdict.py` — cada uno testeable de forma aislada antes de integrar el pipeline completo. Decisión final de `design.md`/`tasks.md`, no de este documento. | (informativo) |

---

## 4. Requisitos por módulo

### 4.1. `errors.py` — extensión de la jerarquía de excepciones (sin tocar clases existentes)

- **R1** (DEBE). `errors.py` DEBE definir `PropSimConfigError(GenesisValidationError)` para: (a)
  `n_paths <= 0`; (b) `max_attempts < 1`; (c) `horizon_months < 1`; (d)
  `path_horizon_trading_days < horizon_months * trading_days_per_month` (piso insuficiente para
  cubrir el horizonte); (e) `oos_ledgers_by_symbol` sin ningún trade OOS extraíble (canasta diaria
  vacía); (f) ficha `PropEconomicsProfile` con `phases` vacío, algún `profit_target_pct <= 0`,
  `min_profitable_days < 0` o `payout_cycle_days <= 0`.
- **R2** (DEBE). `errors.py` DEBE definir `VerdictConfigError(GenesisValidationError)` para: (a)
  `candidates` vacío (`len(candidates) == 0`); (b) algún `CandidateValidationBundle` con
  `wfa_results_by_symbol` vacío o con símbolos que no coinciden entre `wfa_results_by_symbol`,
  `dsr_pbo_results_by_symbol`, `sensitivity_results_by_symbol`, `mc_symbol_results_by_symbol`; (c)
  `starting_balance <= 0`; (d) intersección de días de trading de un par de candidatos con menos de
  2 observaciones para T2 (correlación indefinida, R84).
- **R3** (DEBE). Todo mensaje de excepción nueva de este Change DEBE incluir contexto explícito
  (`candidate_id`, `symbol` si aplica, valor involucrado) — fail-fast con contexto (spec §8).
- **R4** (DEBE). Las dos excepciones nuevas DEBEN heredar de `GenesisValidationError` (raíz
  reutilizada de H, `errors.py:17-22`, no redefinida).
- **R5** (NO DEBE). Ninguna excepción de este Change NO DEBE envolver silenciosamente
  `BacktestConfigError`/`SessionBoundaryError`/`WfaConfigError`/`MonteCarloConfigError`/
  `PurgedCvConfigError`/`DsrPboConfigError`/`SensitivityConfigError` recibidas como insumo — se
  propagan sin capturar si el llamador de `run_prop_sim`/`run_verdict` las produce antes de invocar
  estas funciones (este Change nunca re-ejecuta backtests, por lo que no debería observarlas
  directamente, pero el criterio se documenta por consistencia con R5/R6 de H/I).
- **R6** (DEBE). `rg -n "class PropSimConfigError|class VerdictConfigError"
  src/genesis/validation/errors.py` DEBE retornar exactamente 2 coincidencias, ambas heredando de
  `GenesisValidationError` (no de `GenesisBacktestError`/`GenesisStrategyError`/`GenesisDataError`).

### 4.2. `prop_sim.py` — ficha de economía del challenge (`PropEconomicsProfile`)

Mismo patrón que `RiskProfile`/ADR-G2 (`backtest/risk_profile.py:29-40,43-69,72-84`): ficha propia
de capa, cargada desde un recurso JSON empaquetado con `importlib.resources`, con función de hash
determinista para `RunProvenance`/manifest.

- **R7** (DEBE). `prop_sim.py` DEBE definir `PhaseSpec` (`@dataclass(frozen=True, slots=True)`) con,
  como mínimo: `profit_target_pct: float`, `min_profitable_days: int`,
  `min_profit_per_day_pct: float`, `max_calendar_days: int | None` (`None` = sin límite, spec §1.3:
  "Plazo: Sin límite de tiempo").
- **R8** (DEBE). `prop_sim.py` DEBE definir `PropEconomicsProfile` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `name: str`, `phases: tuple[PhaseSpec, ...]`,
  `challenge_cost_pct_of_balance: float`, `profit_split_pct: float`, `payout_cycle_days: int`,
  `max_lots: float | None`, `max_positions: int | None`, `consistency_rule_pct: float | None`. NO
  DEBE duplicar `weekend_holding_allowed`/`max_loss_limit_pct`/`max_loss_limit_kind`
  (`RiskProfile`, recibido como argumento independiente por `run_prop_sim`, mismo criterio que
  `montecarlo.py` ya aplica) ni `daily_loss_limit_pct`/`daily_reset_time` (`FirmProfile`, ídem).
- **R9** (DEBE). El recurso JSON empaquetado por defecto para The5ers DEBE fijar, como valores
  definitivos derivados del spec §1.3: dos `PhaseSpec` — fase 1 (`profit_target_pct=8.0`,
  `min_profitable_days=3`, `min_profit_per_day_pct=0.5`, `max_calendar_days=None`), fase 2
  (`profit_target_pct=5.0`, `min_profitable_days=3`, `min_profit_per_day_pct=0.5`,
  `max_calendar_days=None`); `payout_cycle_days=14` (**definitivo**, "payouts quincenales", §1.3);
  `consistency_rule_pct=None` (§1.3 no menciona `consistency_rule` como aplicable a The5ers v1).
  `challenge_cost_pct_of_balance=3.0` y `profit_split_pct=80.0` son **placeholders explícitos "a
  confirmar"** (decisión 2, §3) — no tienen cifra en el spec. `max_lots=None`,
  `max_positions=None` (sin dato en el spec, no bloqueante).
- **R10** (DEBE). `prop_sim.py` DEBE definir `load_prop_economics_profile(path: Path | None = None)
  -> PropEconomicsProfile` (mismo patrón que `load_risk_profile`, `risk_profile.py:43-69`):
  `path=None` carga el recurso empaquetado por defecto (R9); lanza `PropSimConfigError` (R1f) con
  el campo faltante/inválido en el mensaje ante configuración incompleta o inválida.
- **R11** (DEBE). `prop_sim.py` DEBE definir `prop_economics_profile_hash(profile:
  PropEconomicsProfile) -> str` (mismo patrón `sha256` canónico sobre JSON ordenado que
  `risk_profile_hash`, `risk_profile.py:72-84`, y `firm_profile_hash`, `data/profile.py:99-115`) —
  determinista, incorporado al manifest (R98).
- **R12** (DEBE). `PropEconomicsProfile.__post_init__` (o validación equivalente en
  `load_prop_economics_profile`) DEBE rechazar, vía `PropSimConfigError`: `phases` vacío; algún
  `PhaseSpec.profit_target_pct <= 0`; `min_profitable_days < 0`; `min_profit_per_day_pct < 0`;
  `payout_cycle_days <= 0`; `challenge_cost_pct_of_balance < 0`; `profit_split_pct` fuera de
  `(0.0, 100.0]`.
- **R13** (NO DEBE). `PropEconomicsProfile` NO DEBE ser consumida por ningún archivo de
  `src/genesis/backtest/` (`Simulator`/`RiskLevelsProvider`): ningún consumidor de capa 3 necesita
  `profit_split`/`payout_cycle`/`challenge_cost` (decisión 1, §3). `rg -n
  "PropEconomicsProfile" src/genesis/backtest/` DEBE retornar 0 coincidencias.
- **R14** (DEBE). El tearsheet (R107) y el manifest (R98) DEBEN marcar explícitamente si
  `challenge_cost_pct_of_balance`/`profit_split_pct` provienen del placeholder por defecto (R9) o
  de un fixture confirmado distinto — campo `economics_confirmed: bool` en `VerdictResult`
  (`True` solo si el llamador pasa un `PropEconomicsProfile` distinto del cargado por
  `load_prop_economics_profile()` sin argumentos; determinado por comparación de
  `prop_economics_profile_hash` contra el hash del fixture empaquetado por defecto, calculado una
  vez en tiempo de import).

### 4.3. `prop_sim.py` — resampleo diario local (sin tocar `montecarlo.py`)

- **R15** (DEBE). `prop_sim.py` DEBE definir `_build_daily_basket(oos_ledgers_by_symbol:
  Mapping[str, Ledger]) -> tuple[list[date], dict[date, float]]`, reimplementación local del mismo
  criterio de agrupación por `trading_day` que `montecarlo._build_basket`/
  `_extract_exit_returns_by_day` (`montecarlo.py:287-301,268-284`): para cada símbolo, extrae
  deltas de `FillRecord` de salida etiquetados por `payload.timestamp_utc.date()` (mismo proxy de
  `trading_day`, ADR-H8) y los suma por día across símbolos, retornando `(basket_days ordenados,
  daily_totals: dict[date, float])` — a diferencia de `_build_basket`, retorna directamente los
  totales sumados por día (no una lista de `(symbol, delta)` por día), porque `prop_sim.py` nunca
  necesita el desglose por símbolo dentro del día (gates P a nivel de cuenta).
- **R16** (NO DEBE). `prop_sim.py` NO DEBE importar ningún símbolo con prefijo `_` de
  `montecarlo.py`. `rg -n "from genesis\.validation\.montecarlo import _|from \.montecarlo import
  _" src/genesis/validation/prop_sim.py` DEBE retornar 0 coincidencias.
- **R17** (DEBE). Si `_build_daily_basket` produce una lista vacía de `basket_days`, `run_prop_sim`
  DEBE lanzar `PropSimConfigError` (R1e) antes de intentar ningún resampleo.
- **R18** (DEBE). `prop_sim.py` DEBE definir un tamaño de bloque de resampleo con la misma fórmula
  que `montecarlo._default_block_size` (`montecarlo.py:110-112`,
  `clip(round(n_trading_days ** (1/3)), 5, 60)`) — reimplementada localmente (constantes propias
  `_MIN_BLOCK_SIZE`/`_MAX_BLOCK_SIZE`, sin importar las de `montecarlo.py`), usada solo cuando
  `PropSimConfig.block_size is None`.
- **R19** (DEBE). `run_prop_sim`/`simulate_challenge_paths` DEBEN recibir `seed: int` como argumento
  requerido, independiente del `seed` usado por `monte_carlo_portfolio` (decisión 9, §3) — ningún
  valor por defecto. RNG explícito: `numpy.random.default_rng(seed)`.
- **R20** (DEBE). El resampleo de cada trayectoria DEBE producir una secuencia de exactamente
  `config.path_horizon_trading_days` días (con reposición, bloques contiguos de tamaño
  `resolved_block_size` tomados de `basket_days`/`daily_totals`, mismo criterio de bootstrap por
  bloques que `montecarlo._portfolio_block_bootstrap_paths`, `montecarlo.py:327-340`,
  reimplementado localmente sin importar esa función).
- **R21** (DEBE). `PropSimConfig` (`@dataclass(frozen=True, slots=True)`) DEBE incluir, como
  mínimo: `n_paths: int`, `seed: int`, `max_attempts: int = 10` (decisión 3, §3),
  `horizon_months: int = 12`, `trading_days_per_month: int = 21`,
  `path_horizon_trading_days: int = 750`, `block_size: int | None = None`. `__post_init__` DEBE
  validar `n_paths > 0`, `max_attempts >= 1`, `horizon_months >= 1`, `trading_days_per_month >= 1`,
  `path_horizon_trading_days >= horizon_months * trading_days_per_month`, `block_size is None or
  block_size > 0` — en caso contrario, `PropSimConfigError` (R1a-R1d).
- **R22** (DEBE). `run_prop_sim`/`simulate_challenge_paths` DEBEN ejecutarse en un loop secuencial
  sobre `n_paths` trayectorias (sin `multiprocessing`/`concurrent.futures`, mismo criterio de
  G/H/I). `rg -n "multiprocessing|concurrent\.futures" src/genesis/validation/prop_sim.py` DEBE
  retornar 0 coincidencias.

### 4.4. `prop_sim.py` — máquina de estados del challenge (por trayectoria)

`simulate_challenge_paths(daily_pnl_by_day: Mapping[date, float], starting_balance: float,
prop_economics_profile: PropEconomicsProfile, firm_profile: FirmProfile, risk_profile: RiskProfile,
config: PropSimConfig) -> PropSimResult` es el **núcleo puro** reutilizable (no depende de
`Ledger`/`oos_ledgers_by_symbol`): opera directamente sobre una serie de P&L diario ya combinada,
para que `verdict.py` pueda invocarlo también sobre la canasta ponderada del ensemble (R79-R83)
sin reconstruir `Ledger`s sintéticos. `run_prop_sim(oos_ledgers_by_symbol, ...)` es un envoltorio de
conveniencia: construye la canasta diaria (R15) y delega en `simulate_challenge_paths`.

- **R23** (DEBE). `prop_sim.py` DEBE definir `PropSimOutcomeKind` (`StrEnum`) con exactamente 4
  miembros: `FUNDED_SURVIVED_HORIZON`, `FUNDED_BREACHED_TOTAL`, `NEVER_FUNDED_ATTEMPTS_EXHAUSTED`,
  `IN_PROGRESS_UNFUNDED_AT_PATH_END` (mismo criterio de enumeración cerrada que `BreachKind`,
  `ledger.py:21-31`: ampliar esta enumeración es un cambio de alcance).
- **R24** (DEBE). Para cada trayectoria resampleada (secuencia de `path_horizon_trading_days` P&L
  diarios), la máquina de estados DEBE recorrer los días en orden, manteniendo como mínimo:
  `attempt` (contador de intentos, inicia en 1), `phase_index` (índice en
  `prop_economics_profile.phases`, inicia en 0), `phase_start_balance` (balance al inicio del
  intento/fase vigente, inicia en `starting_balance`), `balance` (balance corriente),
  `phase_profitable_days` (contador de días con retorno diario `>= min_profit_per_day_pct` desde el
  inicio de la fase vigente), `is_funded: bool`, y, una vez fondeada, `funded_reference_balance`
  (ancla estática o pico de equity, según `risk_profile.max_loss_limit_kind`) y
  `days_since_last_payout`.
- **R25** (DEBE). **Reinicio de intento** (challenge no fondeado): si el día produce un breach
  DIARIO (`daily_loss = max(0.0, phase_start_of_day_balance - balance) >=
  phase_start_of_day_balance * firm_profile.daily_loss_limit_pct / 100.0`, decisión 4 §3) o un
  breach TOTAL (`total_loss = max(0.0, attempt_reference_balance - balance) >=
  attempt_reference_balance * risk_profile.max_loss_limit_pct / 100.0`, con
  `attempt_reference_balance` estático = `phase_start_balance` del intento si
  `risk_profile.max_loss_limit_kind is MaxLossLimitKind.STATIC`, o el pico de `balance` observado
  desde el inicio del intento si `TRAILING` — mismo criterio de ancla que
  `simulator.py:380-406`), la máquina DEBE: si `attempt < config.max_attempts`, incrementar
  `attempt`, resetear `balance = starting_balance`, `phase_index = 0`, `phase_start_balance =
  starting_balance`, `phase_profitable_days = 0`, y continuar con el siguiente día; si `attempt ==
  config.max_attempts`, terminar la trayectoria con `outcome =
  NEVER_FUNDED_ATTEMPTS_EXHAUSTED`.
- **R26** (DEBE). **Avance de fase**: si no hubo breach ese día, la máquina DEBE evaluar `retorno
  diario_pct = 100.0 * daily_pnl / phase_start_of_day_balance`; si `retorno_diario_pct >=
  phases[phase_index].min_profit_per_day_pct`, incrementar `phase_profitable_days`. Si
  `(balance - phase_start_balance) >= phase_start_balance *
  phases[phase_index].profit_target_pct / 100.0` **y** `phase_profitable_days >=
  phases[phase_index].min_profitable_days`, la fase se considera cruzada: si
  `phase_index + 1 == len(phases)`, la trayectoria pasa a `is_funded = True` (registra
  `funded_trading_day_index`, `funded_reference_balance = balance`,
  `days_since_last_payout = 0`); si no, `phase_index += 1`, `phase_start_balance = balance`,
  `phase_profitable_days = 0` (nueva fase, mismo intento, sin nuevo `challenge_cost`).
- **R27** (DEBE). **Estado fondeado**: cada día, la máquina DEBE evaluar el mismo breach DIARIO
  (R25, base balance-a-balance únicamente, contra el balance del día anterior en estado fondeado) y
  el mismo breach TOTAL (R25, `attempt_reference_balance` = `funded_reference_balance` estático o
  el pico de `balance` desde el fondeo si `TRAILING`). Cualquiera de los dos DEBE: (a) incrementar
  el contador de meses fondeados con infracción diaria del mes en curso (R41); (b) terminar la
  trayectoria con `outcome = FUNDED_BREACHED_TOTAL` (una infracción de firma durante el estado
  fondeado termina la cuenta fondeada — mismo criterio de invariante de §10.2 aplicado aquí en
  `prop_sim`, aunque §10.2 describe la incubación real, no la simulación).
- **R28** (DEBE). **Ciclo de payout**: en estado fondeado sin breach ese día, `days_since_last_payout
  += 1`; cuando `days_since_last_payout >= prop_economics_profile.payout_cycle_days`, DEBE calcular
  `payout = max(0.0, balance - funded_reference_balance) *
  prop_economics_profile.profit_split_pct / 100.0`, acumularlo en `cumulative_net_payout`, y
  resetear `funded_reference_balance = balance`, `days_since_last_payout = 0` (el payout solo
  cuenta ganancia nueva desde el último ciclo, práctica estándar de payout incremental).
- **R29** (DEBE). **Fin de horizonte fondeado**: si la trayectoria permanece fondeada sin breach
  hasta acumular `horizon_months * trading_days_per_month` días fondeada, DEBE terminar con
  `outcome = FUNDED_SURVIVED_HORIZON` (censura por la derecha, decisión 5 §3) — no continúa
  simulando más allá del horizonte aunque la trayectoria resampleada tenga más días disponibles.
- **R30** (DEBE). **Fin de ruta sin resolución**: si se agotan los `path_horizon_trading_days`
  disponibles sin que la trayectoria haya sido fondeada ni haya agotado `max_attempts`, DEBE
  terminar con `outcome = IN_PROGRESS_UNFUNDED_AT_PATH_END` (censura por longitud finita de la
  ruta simulada, distinta de `NEVER_FUNDED_ATTEMPTS_EXHAUSTED`; ambas cuentan como "no fondeada" a
  efectos de P1, R42).
- **R31** (DEBE). `prop_sim.py` DEBE definir `PathOutcome` (`@dataclass(frozen=True, slots=True)`)
  con, como mínimo: `outcome: PropSimOutcomeKind`, `n_attempts_used: int`,
  `funded_trading_day_index: int | None`, `breach_trading_day_index: int | None`,
  `funded_survival_trading_days: int | None` (`None` si nunca fondeada), `net_payout_12m: float`
  (acumulado hasta `min(horizonte, fin de la trayectoria)`), `n_funded_months_observed: int`,
  `n_funded_months_with_daily_breach: int`.
- **R32** (DEBE). Ningún campo de `PathOutcome`/`PropSimResult` DEBE evaluar el umbral P1-P6 contra
  un booleano de pasa/no-pasa: solo produce los números; la comparación contra el umbral es
  responsabilidad de `verdict.py` (mismo criterio R33/R44 de I).
- **R33** (DEBE). El breach DIARIO evaluado por la máquina de estados (R25, R27) DEBE usar
  **únicamente** la base balance-a-balance (`phase_start_of_day_balance - balance` del día,
  comparado contra `firm_profile.daily_loss_limit_pct`), decisión 4 §3 — corrección explícita de
  `proposal.md` (no usa `metrics.worst_daily_floating_excursion`, que es idénticamente `0.0` para
  cualquier candidato que llega a `prop_sim.py`, ver preámbulo y decisión 4 §3).
- **R34** (NO DEBE). `prop_sim.py` NO DEBE importar ni invocar
  `genesis.backtest.metrics.worst_daily_floating_excursion` ni
  `min_distance_to_daily_limit`. `rg -n "worst_daily_floating_excursion|min_distance_to_daily_limit"
  src/genesis/validation/prop_sim.py` DEBE retornar 0 coincidencias.
- **R35** (DEBE). La docstring de la función que evalúa el breach diario (o de `PropSimResult`,
  campo `p_daily_breach_funded_month`) DEBE documentar explícitamente la limitación de la decisión
  4 (§3): el proxy de cierre-a-cierre es una cota **inferior conservadora** de la probabilidad real
  de breach diario (la base de equity flotante intradía real puede disparar antes).
- **R36** (DEBE). El breach TOTAL (R25, R27) DEBE respetar `risk_profile.max_loss_limit_kind`
  (`MaxLossLimitKind.STATIC` vs. `TRAILING`, `risk_profile.py:22-26`) con la misma semántica de
  ancla que `simulator._evaluate_total_breach` (`simulator.py:380-406`): `STATIC` ancla al balance
  de inicio del intento (o de la ficha fondeada); `TRAILING` ancla al pico de `balance` observado
  desde el inicio del intento (o desde el fondeo).
- **R37** (DEBE). Un nuevo intento (R25) DEBE incrementar un acumulador informativo
  `total_challenge_cost_paid` en `prop_economics_profile.challenge_cost_pct_of_balance / 100.0 *
  starting_balance` por cada intento iniciado (incluido el primero) — expuesto como campo
  informativo agregado en `PropSimResult` (no es un gate P normativo, spec §7.3 no lista un umbral
  de costo).
- **R38** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir al menos tres golden tests
  calculados a mano (spec §9, "escenarios de challenge calculados a mano"): (a) una trayectoria que
  **roza** el límite diario sin cruzarlo (breach evitado por un margen conocido); (b) una
  trayectoria que **viola** el límite diario (breach exacto en el umbral, `daily_loss == threshold`
  cuenta como breach, operador `>=`); (c) una trayectoria que viola el límite total bajo
  `MaxLossLimitKind.STATIC` y otra bajo `MaxLossLimitKind.TRAILING` con el mismo P&L pero
  `outcome`/`breach_trading_day_index` distintos entre ambas (verifica R36).
- **R39** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir un golden test de avance de fase
  (R26) con un caso sintético donde el target acumulado se cruza en un día sin que
  `phase_profitable_days` alcance `min_profitable_days` todavía (la fase NO avanza ese día) y otro
  donde ambas condiciones se cumplen simultáneamente (la fase SÍ avanza).
- **R40** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir un golden test de reinicio de
  intento con `max_attempts=1` que verifique que la trayectoria termina en
  `NEVER_FUNDED_ATTEMPTS_EXHAUSTED` en el primer breach (sin segundo intento).

### 4.5. `prop_sim.py` — agregación P1-P6 (`PropSimResult`)

- **R41** (DEBE). `prop_sim.py` DEBE definir `PropSimResult` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `candidate_id: str`, `config_version: str`, `seed: int`,
  `n_paths: int`, `p_pass: float` (P1), `expected_attempts: float` (P2, media),
  `expected_attempts_p50: float`, `expected_attempts_p90: float`,
  `p_daily_breach_funded_month: float` (P3), `median_funded_survival_months: float` (P4),
  `payout_p25_12m: float` (P5), `n_paths_never_funded: int`,
  `n_paths_funded_breached_total: int`, `n_paths_funded_survived_horizon: int`.
- **R42** (DEBE). `p_pass` (P1) DEBE ser la fracción de trayectorias con `outcome in
  {FUNDED_SURVIVED_HORIZON, FUNDED_BREACHED_TOTAL}` (cualquier resultado que alcanzó el fondeo,
  independientemente de lo que pase después) sobre `n_paths` totales.
- **R43** (DEBE). `expected_attempts`/`expected_attempts_p50`/`expected_attempts_p90` (P2) DEBEN
  calcularse **condicionados a las trayectorias que alcanzan el fondeo** (`n_attempts_used` de las
  trayectorias con `outcome in {FUNDED_SURVIVED_HORIZON, FUNDED_BREACHED_TOTAL}`), consistente con
  la literalidad del gate ("intentos **hasta fondeo**", §7.3). Si ninguna trayectoria se fondea,
  `expected_attempts = float("inf")` (documentado explícitamente; P1 ya sería ~0, el gate P2
  fallaría trivialmente).
- **R44** (DEBE). `p_daily_breach_funded_month` (P3) DEBE calcularse como
  `sum(n_funded_months_with_daily_breach) / sum(n_funded_months_observed)` sobre todas las
  trayectorias con al menos un mes fondeado observado (`n_funded_months_observed > 0`); `0.0` si
  ninguna trayectoria observa un mes fondeado completo (documentado: no hay evidencia suficiente
  para estimar P3, no se interpreta como "pasa" per se en `verdict.py`, ver R63).
- **R45** (DEBE). `median_funded_survival_months` (P4) DEBE calcularse sobre `funded_survival_months
  = funded_survival_trading_days / trading_days_per_month` de las trayectorias con `outcome in
  {FUNDED_SURVIVED_HORIZON, FUNDED_BREACHED_TOTAL}`, tratando las `FUNDED_SURVIVED_HORIZON` como
  observaciones censuradas en `horizon_months` (decisión 5, §3).
- **R46** (DEBE). El cálculo de la mediana censurada (R45) DEBE seguir esta regla explícita: si al
  menos el 50% de las trayectorias fondeadas tienen `funded_survival_months >= mediana empírica
  simple` Y esa mediana simple corresponde a una trayectoria censurada
  (`FUNDED_SURVIVED_HORIZON`), `median_funded_survival_months = horizon_months` (la mediana real es
  `>= horizon_months`, se reporta el valor censurado como cota inferior, nunca se extrapola más
  allá del horizonte simulado).
- **R47** (DEBE). Si ninguna trayectoria alcanza el fondeo, `median_funded_survival_months = 0.0`
  (documentado explícitamente: sin evidencia de supervivencia fondeada).
- **R48** (DEBE). `payout_p25_12m` (P5) DEBE calcularse con `numpy.percentile(net_payout_12m_array,
  25)` sobre **todas** las `n_paths` trayectorias (no solo las fondeadas): las no fondeadas
  contribuyen `net_payout_12m = 0.0` (correcto por construcción: sin fondeo no hay payout).
- **R49** (DEBE). El gate **P6** (violaciones de reglas de firma en simulación OOS = 0) NO DEBE
  evaluarse dentro de `prop_sim.py`/`PropSimResult`: se evalúa en `verdict.py` directamente sobre
  el `Ledger` OOS real (`BreachEvent`/`RejectionRecord` del `oos_ledger_cosido` de `WfaResult`,
  R66) — es el único gate P que no usa trayectorias MC (idea.md, tabla de gates).
- **R50** (DEBE). `run_prop_sim(oos_ledgers_by_symbol: Mapping[str, Ledger], starting_balance:
  float, firm_profile: FirmProfile, risk_profile: RiskProfile, prop_economics_profile:
  PropEconomicsProfile, config: PropSimConfig, candidate_id: str) -> PropSimResult` DEBE construir
  la canasta diaria (R15) y delegar en `simulate_challenge_paths` (nombres exactos normativos;
  orden/defaults exactos se cierran en `design.md`).
- **R51** (DEBE). `simulate_challenge_paths`/`run_prop_sim` DEBEN ser deterministas: misma `seed` +
  mismo `daily_pnl_by_day`/`oos_ledgers_by_symbol` + misma config + misma ficha ⇒ `PropSimResult`
  bit-idéntico entre dos invocaciones independientes (spec §8).
- **R52** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir un test de propiedad
  (`hypothesis`, marcado `pytest.mark.unit`) de **monotonía de la ficha**: endurecer
  `PropEconomicsProfile` (subir `challenge_cost_pct_of_balance`, bajar `profit_split_pct`, o subir
  `phases[i].profit_target_pct`) sobre la misma serie de P&L resampleada (mismo `seed`) NUNCA
  mejora `p_pass`/`payout_p25_12m`/`median_funded_survival_months` respecto a la ficha original
  (P1, P4, P5 no mejoran; P2/P3 no mejoran en la dirección de "más fácil").
- **R53** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir un test de determinismo byte a
  byte (R51): dos invocaciones independientes de `run_prop_sim` con los mismos insumos producen
  `PropSimResult` idéntico campo a campo.
- **R54** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir al menos un test de integración
  (`pytest.mark.integration`) que ejecute `oos_ledgers_by_symbol` (fixture sintético) → `run_prop_sim`
  en segundos, verificando que todos los campos de `PropSimResult` son finitos y están en rango
  `[0, 1]` para las fracciones/probabilidades.
- **R55** (DEBE). `tests/validation/test_prop_sim.py` DEBE incluir al menos un test marcado
  `pytest.mark.slow` con `n_paths` de volumen realista (p. ej. `>= 2000`), separado de la suite
  rápida por defecto.
- **R56** (DEBE). `rg -n "def run_prop_sim|def simulate_challenge_paths|class PropSimResult|class
  PropEconomicsProfile" src/genesis/validation/prop_sim.py` DEBE retornar ≥1 coincidencia cada uno.

### 4.6. `verdict.py` — insumos y agregación de gates G (por símbolo, dentro de un candidato)

- **R57** (DEBE). `verdict.py` DEBE definir `CandidateValidationBundle` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `candidate_id: str`, `wfa_results_by_symbol: Mapping[str,
  WfaResult]`, `dsr_pbo_results_by_symbol: Mapping[str, DsrPboResult]`,
  `sensitivity_results_by_symbol: Mapping[str, SensitivityResult]`, `mc_symbol_results_by_symbol:
  Mapping[str, McSymbolResult]`, `mc_portfolio_result: McPortfolioResult`, `prop_sim_result:
  PropSimResult`, `purged_cv_results_by_symbol: Mapping[str, PurgedCvResult] | None = None`.
- **R58** (DEBE). `verdict.py` DEBE validar, para cada `CandidateValidationBundle`, que las claves
  de `wfa_results_by_symbol`, `dsr_pbo_results_by_symbol`, `sensitivity_results_by_symbol` y
  `mc_symbol_results_by_symbol` coinciden exactamente (mismo conjunto de símbolos) — en caso
  contrario, `VerdictConfigError` (R2b) con el candidato y los símbolos en conflicto en el mensaje.
- **R59** (DEBE). `verdict.py` DEBE definir `SymbolGateOutcome` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo, un campo de valor y un campo booleano `_pass` por cada gate G1-G9:
  `trades_oos_total: int`, `g1_pass: bool`; `wfe: float`, `g2_pass: bool`; `profit_factor: float`,
  `g3_pass: bool`; `dsr: float`, `g4_pass: bool`; `pbo: float`, `g5_pass: bool`;
  `mc_maxdd_p95_pct_of_limit: float`, `g6_pass: bool`; `mc_breach_probability_12m: float`,
  `g7_pass: bool`; `sensitivity_has_cliff: bool`, `sensitivity_max_degradation_pct: float`,
  `g8_pass: bool`; `pf_cost_stress_1_5x: float`, `g9_pass: bool`; `all_pass: bool` (AND de G1-G9).
- **R60** (DEBE). `verdict.py` DEBE construir un `SymbolGateOutcome` por `(candidate_id, symbol)`
  comparando los insumos ya producidos por H/I contra los umbrales **definitivos** de spec §7.1,
  sin recalcular ninguna métrica de H/I: `G1: trades_oos_total = len(extract_trade_returns(
  wfa_result.oos_ledger_cosido)) >= 300`; `G2: wfa_result.wfe >= 0.5`; `G3: profit_factor(
  wfa_result.oos_ledger_cosido) >= 1.3` (`genesis.backtest.metrics.profit_factor`,
  `metrics.py:42-49`); `G4: dsr_pbo_result.dsr >= 0.95`; `G5: dsr_pbo_result.pbo < 0.25`; `G6:
  mc_symbol_result.block_bootstrap.max_drawdown_p95 <= 0.5 * risk_profile.max_loss_limit_pct /
  100.0 * starting_balance` (50% del `max_loss_limit`, en unidades absolutas de
  `max_drawdown_p95`); `G7: mc_symbol_result.block_bootstrap.breach_probability < 0.05`; `G8:
  not sensitivity_result.has_cliff and max(p.relative_drop for p in
  sensitivity_result.perturbations) < 0.30`; `G9: min(c.profit_factor for c in
  sensitivity_result.cost_stress if c.multiplier == 1.5) >= 1.15`.
- **R61** (NO DEBE). `verdict.py` NO DEBE reimplementar ni recalcular ningún valor ya producido por
  `wfa.py`/`montecarlo.py`/`dsr_pbo.py`/`sensitivity.py` (H/I): solo compara los campos existentes
  de `WfaResult`/`DsrPboResult`/`SensitivityResult`/`McSymbolResult` contra los umbrales de R60.
- **R62** (DEBE). `verdict.py` DEBE evaluar **P6** (violaciones de reglas de firma en simulación OOS
  = 0) directamente sobre `wfa_result.oos_ledger_cosido` de cada símbolo: `p6_pass = all(
  count(BreachEvent) == 0 for entry in oos_ledger_cosido.entries)` (ningún `BreachEvent` de ningún
  `BreachKind` en el ledger OOS cosido de ningún símbolo del candidato) — corrección de nombre
  respecto a R49: P6 se evalúa por candidato (todos los símbolos deben estar limpios), no es un
  gate G por símbolo aislado, pero usa el mismo `Ledger` real (nunca MC).
- **R63** (DEBE). Los umbrales de gates de `verdict.py` (G1-G9, C1-C2, P1-P6, T1-T2) DEBEN ser
  constantes de módulo nombradas (p. ej. `_G1_MIN_TRADES_OOS = 300`, `_G3_MIN_PROFIT_FACTOR =
  1.3`, `_P1_MIN_PASS_PROBABILITY = 0.5`), nunca literales embebidos en la lógica de comparación —
  facilita auditoría y evita relajación silenciosa de un gate (spec: "los gates nunca se
  relajan").
- **R64** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test unitario por cada uno de
  los 9 umbrales G (R60) que verifique, con un `SymbolGateOutcome` sintético justo en el umbral y
  justo debajo/encima, el resultado esperado de `_pass` (p. ej. `dsr=0.95` → `g4_pass=True`;
  `dsr=0.9499` → `g4_pass=False`).
- **R65** (DEBE). `rg -n "0\.95|0\.25|1\.3|0\.5\b|300\b|1\.15" src/genesis/validation/verdict.py`
  DEBE mostrar los umbrales exactos de spec §7.1-§7.4 asignados a constantes nombradas (R63), no
  usados como literales sueltos dentro de la lógica.
- **R66** (DEBE). El gate P6 (R62) DEBE evaluarse con contexto explícito: si algún símbolo del
  candidato tiene ≥1 `BreachEvent` en su `oos_ledger_cosido`, el `CandidateGateSummary` (R67) DEBE
  registrar el símbolo y el `BreachKind` en un campo informativo (`p6_violating_symbols:
  Mapping[str, tuple[BreachKind, ...]]`) para auditoría del veredicto.

### 4.7. `verdict.py` — gates C (coherencia de canasta) y P (economía prop) por candidato

- **R67** (DEBE). `verdict.py` DEBE definir `CandidateGateSummary` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `candidate_id: str`, `symbol_gate_outcomes: Mapping[str,
  SymbolGateOutcome]`, `c1_fraction_passing: float`, `c1_pass: bool`, `c2_min_pf_non_passing:
  float`, `c2_pass: bool`, `p1_pass: bool` .. `p6_pass: bool` (6 campos booleanos explícitos, uno
  por gate P), `p6_violating_symbols: Mapping[str, tuple[BreachKind, ...]]`,
  `passes_g_c_p: bool` (AND de C1, C2, P1-P6).
- **R68** (DEBE). `c1_fraction_passing = count(symbol for symbol, outcome in
  symbol_gate_outcomes.items() if outcome.all_pass) / len(symbol_gate_outcomes)`; `c1_pass =
  c1_fraction_passing >= 0.60` (spec §7.2, umbral definitivo).
- **R69** (DEBE). `c2_min_pf_non_passing = min(outcome.profit_factor for symbol, outcome in
  symbol_gate_outcomes.items() if not outcome.all_pass)`, o `float("inf")` si todos los símbolos
  pasan G1-G9 (vacuamente cumplido); `c2_pass = c2_min_pf_non_passing >= 0.8` (spec §7.2, umbral
  definitivo) — `float("inf") >= 0.8` es `True` por construcción cuando no aplica.
- **R70** (DEBE). `p1_pass = prop_sim_result.p_pass >= 0.5`; `p2_pass =
  prop_sim_result.expected_attempts <= 2.0`; `p3_pass =
  prop_sim_result.p_daily_breach_funded_month < 0.02`; `p4_pass =
  prop_sim_result.median_funded_survival_months >= 6.0`; `p5_pass =
  prop_sim_result.payout_p25_12m > 0.0`; `p6_pass` de R62 — los 6 umbrales son los definitivos de
  spec §7.3.

### 4.8. `verdict.py` — gate T1 (deflación de torneo)

- **R71** (DEBE). `verdict.py` DEBE definir `n_candidatos_torneo = len(candidates)` (parámetro
  `candidates: Mapping[str, CandidateValidationBundle]` de `run_verdict`) — nunca una constante
  hardcodeada (decisión 8, §3); si `len(candidates) == 0`, `VerdictConfigError` (R2a).
- **R72** (DEBE). `verdict.py` DEBE identificar al **candidato ganador** como el que, entre los
  candidatos con `passes_g_c_p=True` (R67), tiene el mayor `prop_sim_result.payout_p25_12m`;
  empates resueltos por el mayor `prop_sim_result.median_funded_survival_months`; si ningún
  candidato pasa G+C+P, no hay ganador y T1 no se evalúa (veredicto NO-GO, R91).
- **R73** (DEBE). `verdict.py` DEBE construir la canasta diaria combinada del candidato ganador
  (mismo `_build_daily_basket` de R15, compartido dentro de este Change, R16 aplica igual: no
  importa símbolos privados de otros módulos) a partir de `oos_ledger_cosido` de cada símbolo del
  candidato ganador (vía `extract_trade_returns` de `genesis.validation._returns`, reutilizado tal
  cual como módulo interno del paquete — mismo patrón de reuso que `dsr_pbo.py` ya aplica sobre
  `_returns`/`_dsr`, `dsr_pbo.py:59-70`).
- **R74** (DEBE). `n_trials_signal_total_ganador = sum(wfa_result.n_trials_signal_total for
  wfa_result in candidatos[ganador].wfa_results_by_symbol.values())` (decisión 8, §3, soporte
  textual: spec §6.1 "trials contados mecánicamente por candidato").
- **R75** (DEBE). `n_trials_deflactado = n_trials_signal_total_ganador + (n_candidatos_torneo - 1)`
  (decisión 8, §3). `rg -n "n_candidatos_torneo|n_trials_deflactado" src/genesis/validation/
  verdict.py` DEBE retornar ≥1 coincidencia cada uno; `n_candidatos_torneo` NO DEBE aparecer como
  literal `3` hardcodeado en ningún punto de la lógica de deflación.
- **R76** (DEBE). `verdict.py` DEBE reutilizar `genesis.validation._dsr.deflated_sharpe_ratio`
  **tal cual** (sin duplicar la fórmula, mismo patrón de reuso interno que
  `dsr_pbo.deflated_sharpe_ratio_gate`, `dsr_pbo.py:59-70`) invocada como
  `deflated_sharpe_ratio(daily_returns_canasta_ganador, n_trials=n_trials_deflactado)` para
  producir `t1_dsr: float`. `rg -n "from genesis\.validation\._dsr import deflated_sharpe_ratio"
  src/genesis/validation/verdict.py` DEBE retornar ≥1 coincidencia.
- **R77** (DEBE). `t1_pass = t1_dsr >= 0.95` (spec §7.4, umbral definitivo, idéntico al de G4 pero
  sobre el DSR deflactado por torneo, nunca el DSR de G4 sin deflactar).
- **R78** (DEBE). `verdict.py` DEBE registrar en el manifest (R98), como mínimo: `t1_dsr_pre_
  deflation` (DSR sin ajuste de torneo, para trazabilidad/auditoría), `t1_dsr` (deflactado),
  `n_trials_signal_total_ganador`, `n_candidatos_torneo`, `n_trials_deflactado` — auditable sin
  necesidad de re-ejecutar el cálculo.

### 4.9. `verdict.py` — gate T2 (ensemble por correlación y vol-inversa)

- **R79** (DEBE). `verdict.py` DEBE calcular, para cada par de candidatos con `passes_g_c_p=True`
  (R67), la correlación de Pearson (`numpy.corrcoef`) entre sus canastas diarias combinadas (R73)
  restringidas a la **intersección** de `trading_day`s comunes entre ambos candidatos. Si la
  intersección tiene menos de 2 días, `VerdictConfigError` (R2d) con los dos `candidate_id` en el
  mensaje.
- **R80** (DEBE). Un par de candidatos es **elegible para ensemble** si su correlación (R79) es `<
  0.3` (spec §7.4/§2.5, umbral definitivo). Si el torneo tiene exactamente 2 candidatos que pasan
  G+C+P, la elegibilidad del ensemble depende únicamente de ese par. Si tiene 3 o más, el ensemble
  se forma con el **subconjunto máximo de candidatos mutuamente elegibles dos a dos** (todas las
  correlaciones del subconjunto `< 0.3`) — decisión explícita de este documento (el spec no
  detalla el caso `>2` candidatos).
- **R81** (DEBE). Si el ensemble es elegible (≥2 candidatos en el subconjunto de R80), `verdict.py`
  DEBE calcular pesos por **vol-inversa**: `std_i` = desviación estándar de la canasta diaria
  combinada del candidato `i` (sobre la intersección común de `trading_day`s del subconjunto
  elegible); `w_i = (1/std_i) / sum_j(1/std_j)`, normalizados a `sum(w_i) == 1.0`.
  `VerdictConfigError` si algún `std_i == 0.0` (varianza degenerada, ensemble indefinido).
- **R82** (DEBE). `verdict.py` DEBE construir la canasta diaria del ensemble como
  `daily_pnl_ensemble[day] = sum(w_i * daily_pnl_i[day] for i in subconjunto elegible)` sobre la
  intersección de días comunes, y DEBE invocar `prop_sim.simulate_challenge_paths` (núcleo puro,
  R24) sobre esa canasta con un `seed` **independiente** (documentado en el manifest como
  `ensemble_prop_sim_seed`, distinto de los `seed` de cada candidato individual) para producir un
  `PropSimResult` propio del ensemble, evaluado contra los mismos umbrales P1-P5 de R70 (P6 no
  aplica al ensemble: no existe un `Ledger` real del ensemble, solo trayectorias simuladas).
- **R83** (DEBE). `verdict.py` DEBE definir `EnsembleResult` (`@dataclass(frozen=True,
  slots=True)`) con, como mínimo: `member_candidate_ids: tuple[str, ...]`,
  `pairwise_correlations: Mapping[tuple[str, str], float]`, `weights: Mapping[str, float]`,
  `prop_sim_result: PropSimResult`, `passes_p_gates: bool` (P1-P5 sobre `prop_sim_result` del
  ensemble, mismos umbrales R70).
- **R84** (DEBE). Si ningún par de candidatos que pasan G+C+P tiene correlación `< 0.3`,
  `EnsembleResult` DEBE ser `None` en `VerdictResult` — el veredicto usa solo el candidato de mejor
  economía P (R72), consistente con spec §7.4: "en caso contrario, solo el de mejor economía P".
- **R85** (DEBE). Si solo 0 o 1 candidato pasa G+C+P, T2 NO DEBE evaluarse (no hay par que
  correlacionar); `EnsembleResult = None`.
- **R86** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test unitario de T2 con dos
  candidatos sintéticos de correlación conocida `< 0.3` (ensemble elegible) y otro par con
  correlación conocida `>= 0.3` (ensemble no elegible), verificando `EnsembleResult`
  presente/ausente respectivamente.
- **R87** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de propiedad
  (`hypothesis`, marcado `pytest.mark.unit`) de **invariancia al orden**: los pesos de vol-inversa
  (R81) y la canasta diaria resultante del ensemble (R82) no dependen del orden de iteración del
  subconjunto elegible (permutar el orden de los candidatos en el `dict` de entrada produce el
  mismo `EnsembleResult.weights` y el mismo `daily_pnl_ensemble`).
- **R88** (DEBE). El cálculo de correlación (R79) DEBE ser simétrico:
  `correlation(A, B) == correlation(B, A)` (propiedad trivial de `numpy.corrcoef`, verificada por
  un test unitario).
- **R89** (NO DEBE). `verdict.py` NO DEBE construir ni ejecutar ningún puente de ejecución real del
  ensemble (asignación de capital en vivo): solo produce `EnsembleResult` con su propio
  `PropSimResult` simulado (spec §10.3, fuera de alcance).
- **R90** (DEBE). `rg -n "def _pairwise_correlation|corrcoef" src/genesis/validation/verdict.py`
  DEBE retornar ≥1 coincidencia; `rg -n "^import scipy|^import statsmodels"
  src/genesis/validation/verdict.py` DEBE retornar 0 coincidencias.

### 4.10. `verdict.py` — veredicto de torneo (§7.5)

- **R91** (DEBE). `verdict.py` DEBE definir `VerdictKind` (`StrEnum`) con exactamente 4 miembros:
  `GO`, `GO_ENSEMBLE`, `GO_PARCIAL`, `NO_GO` (mismos 4 valores normativos de spec §7.5, sin
  variantes adicionales).
- **R92** (DEBE). La lógica de veredicto DEBE seguir exactamente esta prioridad: (a) si
  `EnsembleResult is not None and EnsembleResult.passes_p_gates`, `verdict = GO_ENSEMBLE`
  (incubación del ensemble); (b) si no, y el candidato ganador (R72) pasa G+C+P+T1
  (`passes_g_c_p and t1_pass`), `verdict = GO` (candidato ganador, universo completo); (c) si no,
  pero el candidato ganador pasa en un subconjunto de símbolos (`c1_fraction_passing > 0` pero
  `< 0.60`, o `passes_g_c_p` es `False` solo por C1/C2 mientras P1-P6+T1 mantienen validez sobre
  el subconjunto de símbolos que sí pasan G1-G9), `verdict = GO_PARCIAL` (incubación restringida a
  ese subconjunto); (d) en cualquier otro caso, `verdict = NO_GO`.
- **R93** (DEBE). `verdict.py` DEBE definir `VerdictResult` (`@dataclass(frozen=True, slots=True)`)
  con, como mínimo: `verdict: VerdictKind`, `winning_candidate_id: str | None`,
  `candidate_summaries: Mapping[str, CandidateGateSummary]`, `t1_dsr: float | None`,
  `t1_dsr_pre_deflation: float | None`, `n_candidatos_torneo: int`, `n_trials_deflactado: int |
  None`, `ensemble: EnsembleResult | None`, `economics_confirmed: bool` (R14),
  `no_go_iteration_used: bool = False` (R95).
- **R94** (DEBE). El resultado `VerdictResult.verdict` (y `winning_candidate_id`) DEBE ser
  **invariante al orden** de los candidatos de entrada: permutar el orden de iteración del `dict`
  `candidates` de `run_verdict` produce el mismo `VerdictResult` salvo, trivialmente, el orden de
  iteración interno de `candidate_summaries` (que no es observable si se compara por contenido, no
  por orden de inserción).
- **R95** (DEBE). Si `verdict == NO_GO`, `VerdictResult` DEBE exponer un campo
  `no_go_iteration_used: bool` (default `False`) que el llamador puede fijar en una invocación
  posterior de `run_verdict` para registrar la **única** iteración de política de riesgo/firma
  permitida (spec §7.5): cuando `no_go_iteration_used=True`, `n_candidatos_torneo` para T1 en esa
  invocación posterior DEBE incluir `+1` trial adicional (la iteración cuenta como trial para T1,
  spec §7.5) — `verdict.py` no impone un límite automático de "una sola vez" (es responsabilidad
  del proceso humano/organizacional, documentado explícitamente, no bloqueante para este Change).
- **R95bis** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de propiedad
  (`hypothesis`, marcado `pytest.mark.unit`) que verifique R94 con al menos 3 candidatos
  sintéticos permutados en 3+ órdenes distintos.

### 4.11. `verdict.py` — tearsheet Markdown y manifest JSON reproducible

- **R96** (DEBE). `verdict.py` DEBE definir `render_tearsheet(result: VerdictResult) -> str`, una
  función **pura** (sin I/O) que produce un documento Markdown con, como mínimo: el `VerdictKind`
  resultante y el candidato/ensemble ganador; una tabla por candidato con los 9 valores G, C1/C2,
  P1-P6 y sus `_pass` booleanos; T1 (`t1_dsr_pre_deflation`, `t1_dsr`, `n_trials_deflactado`,
  `n_candidatos_torneo`); T2 (correlaciones por par, pesos del ensemble si aplica); las dos
  advertencias explícitas de la decisión 4 y 2 (§3): "P3 es una cota inferior conservadora sobre
  la base intradía" y, si `economics_confirmed=False`, "economía del challenge con valores
  placeholder, a confirmar".
- **R97** (DEBE). `render_tearsheet` y el manifest (R98) DEBEN generarse a partir del **mismo**
  `VerdictResult` (única fuente de verdad, sin dos caminos de cálculo independientes) — ninguna
  cifra del tearsheet puede divergir de la del manifest para el mismo `VerdictResult`.
- **R98** (DEBE). `verdict.py` DEBE definir una función de serialización del manifest (p. ej.
  `verdict_result_to_manifest_json(result: VerdictResult, config_version: str, dataset_hash_by_
  symbol: Mapping[str, str], firm_profile_hash: str, risk_profile_hash: str,
  prop_economics_profile_hash: str, seeds: Mapping[str, int], git_commit: str) -> str`) que
  produce un JSON con, como mínimo: `config_version`, `dataset_hash_by_symbol` (uno por símbolo,
  patrón `ArtifactMetadata.dataset_hash` extendido a múltiples símbolos), `firm_profile_hash`,
  `risk_profile_hash`, `prop_economics_profile_hash`, `candidate_ids: tuple[str, ...]`,
  `winning_candidate_id`, `verdict`, `seeds` (mapa `candidate_id -> {mc_seed, prop_sim_seed}` +
  `ensemble_prop_sim_seed` si aplica), `git_commit`, `n_candidatos_torneo`,
  `n_trials_deflactado`, resultados por candidato (mismos campos que el tearsheet), y el resumen
  informativo de `purged_cv` si está presente (R106).
- **R99** (DEBE). El manifest DEBE incluir un método/función inversa (`manifest_json_to_verdict_
  summary` o equivalente) que reconstruye, sin pérdida, los campos serializados — round-trip
  `to_json`/`from_json` verificado por test (mismo patrón que `ArtifactMetadata.to_json`/
  `from_json`, `data/metadata.py:66-98`), aunque `VerdictResult` completo (con las dataclasses de
  H/I anidadas) no necesita reconstruirse 1:1 — el contrato de round-trip aplica a los campos
  escalares/serializables del manifest (R98), no a los objetos `WfaResult`/`DsrPboResult`
  originales (que no se serializan).
- **R100** (DEBE). `verdict.py` DEBE definir `write_verdict_artifacts(result: VerdictResult,
  output_dir: Path, config_version: str, dataset_hash_by_symbol: Mapping[str, str],
  firm_profile_hash: str, risk_profile_hash: str, prop_economics_profile_hash: str, seeds:
  Mapping[str, int], git_commit: str | None = None) -> tuple[Path, Path]` que escribe
  `output_dir/manifest.json` y `output_dir/tearsheet.md`, creando `output_dir` si no existe
  (`Path.mkdir(parents=True, exist_ok=True)`), y retorna las dos rutas escritas. `output_dir` es
  **siempre provisto por el llamador** — sin ruta por defecto hardcodeada (decisión 6, §3,
  coherente con la ausencia de CLI en este Change).
- **R101** (DEBE). Si `git_commit is None`, `write_verdict_artifacts` DEBE resolverlo con
  `genesis.data.metadata.current_git_commit()` (reutilizado tal cual, `metadata.py:29-47`) — DEBE
  propagar `GenesisDataError` sin capturar si no se puede determinar el commit (fail-fast,
  consistente con R5).
- **R102** (DEBE). `write_verdict_artifacts` es la **única** función de este Change que realiza
  I/O de escritura a disco (`prop_sim.py` y el resto de `verdict.py` son puros); `rg -n
  "open\(|\.write_text\(|\.write_bytes\(" src/genesis/validation/prop_sim.py` DEBE retornar 0
  coincidencias.
- **R103** (DEBE). `manifest.json` DEBE ser determinista byte a byte: mismos insumos ⇒ mismo JSON
  (claves ordenadas, `json.dumps(..., sort_keys=True)`, mismo patrón que
  `firm_profile_hash`/`risk_profile_hash`).
- **R104** (DEBE). `tearsheet.md` NO DEBE requerir `quantstats`/`matplotlib` para generarse — texto
  Markdown puro (tablas, listas), verificable con `rg -n "^import quantstats|^import matplotlib"
  src/genesis/validation/verdict.py` retornando 0 coincidencias.
- **R105** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de round-trip del
  manifest (`to_json`-equivalente → `from_json`-equivalente) verificando que los campos
  escalares (R98) se reconstruyen sin pérdida.
- **R106** (DEBE). Si `CandidateValidationBundle.purged_cv_results_by_symbol is not None`, el
  manifest DEBE incluir, por símbolo: `n_folds`, `total_trades`, y la suma de
  `purged_trade_count` de todos los `PurgedFold` — como bloque `purged_cv_summary`, marcado
  explícitamente como "diagnóstico informativo, no participa en el veredicto" (decisión 7, §3).
- **R107** (DEBE). El tearsheet DEBE incluir, siempre, la advertencia textual exacta de la
  decisión 4 (§3) sobre P3 ("cota inferior conservadora... la base de equity flotante intradía
  real puede disparar antes") y, condicionalmente (si `economics_confirmed=False`), la advertencia
  de la decisión 2 (§3) sobre economía no confirmada.
- **R108** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de integración
  (`pytest.mark.integration`) sobre `tmp_path` que invoque `write_verdict_artifacts` y verifique
  que ambos archivos existen, son no vacíos, y el manifest es JSON válido.

### 4.12. Testing transversal de `verdict.py`

- **R109** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de determinismo byte a
  byte: mismos `CandidateValidationBundle`s + mismos hashes/seeds ⇒ `VerdictResult` idéntico entre
  dos invocaciones independientes de `run_verdict`.
- **R110** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test unitario por cada rama
  de la prioridad de veredicto (R92): un caso sintético que produce `GO`, uno que produce
  `GO_ENSEMBLE`, uno que produce `GO_PARCIAL`, uno que produce `NO_GO`.
- **R111** (DEBE). `tests/validation/test_verdict.py` DEBE incluir un test de propiedad
  (`hypothesis`) de monotonía a nivel de candidato: degradar cualquier insumo de un candidato
  (bajar `dsr_pbo_result.dsr`, subir `sensitivity_result` con `has_cliff=True`, empeorar
  `prop_sim_result.p_pass`) nunca mejora su `CandidateGateSummary.passes_g_c_p` ni el veredicto
  final a su favor.
- **R112** (DEBE). `tests/validation/test_verdict.py` DEBE incluir al menos un test de integración
  (`pytest.mark.integration`) del pipeline completo: `monte_carlo_portfolio`/
  `oos_ledgers_by_symbol` → `run_prop_sim` → `run_verdict` → `write_verdict_artifacts` sobre
  datasets de muestra (1-2 candidatos sintéticos), en segundos, en CI.
- **R113** (DEBE). `tests/validation/test_verdict.py` DEBE incluir al menos un test marcado
  `pytest.mark.slow` que ejercite `run_verdict` con 3+ candidatos sintéticos y `n_paths` de
  `prop_sim` de volumen realista (ensemble incluido), separado de la suite rápida.
- **R114** (DEBE). `uv run pytest tests/validation/ -v` DEBE pasar en verde (exit code 0),
  incluyendo los tests nuevos de `prop_sim.py`/`verdict.py`.
- **R115** (DEBE). `mise run ci` (lint + `ty` + test) DEBE pasar en verde sobre
  `src/genesis/validation/prop_sim.py`, `src/genesis/validation/verdict.py`,
  `src/genesis/validation/errors.py` y `tests/validation/` extendidos.
- **R116** (DEBE). `rg -n "class CandidateValidationBundle|class VerdictResult|def run_verdict|
  VerdictKind\.GO_ENSEMBLE|VerdictKind\.GO_PARCIAL|VerdictKind\.NO_GO"
  src/genesis/validation/verdict.py` DEBE retornar ≥1 coincidencia cada patrón.
- **R117** (DEBE). `tests/validation/test_public_api.py` (existente, patrón de H/I) DEBE extenderse
  para verificar que `genesis.validation.__all__` incluye la superficie normativa mínima de este
  Change (R118) y no re-exporta símbolos con prefijo `_` de `prop_sim.py`/`verdict.py`.
- **R118** (DEBE). `src/genesis/validation/__init__.py` DEBE extender su `__all__` mínimo y curado
  con, como mínimo: `PropSimConfigError`, `VerdictConfigError`, `PhaseSpec`,
  `PropEconomicsProfile`, `load_prop_economics_profile`, `prop_economics_profile_hash`,
  `PropSimConfig`, `PropSimOutcomeKind`, `PathOutcome`, `PropSimResult`,
  `simulate_challenge_paths`, `run_prop_sim`, `CandidateValidationBundle`, `SymbolGateOutcome`,
  `CandidateGateSummary`, `VerdictKind`, `EnsembleResult`, `VerdictResult`, `run_verdict`,
  `render_tearsheet`, `write_verdict_artifacts` — NUNCA `_build_daily_basket`/funciones auxiliares
  internas de comparación de umbrales si `design.md` las mantiene privadas.

---

## 5. Invariantes transversales

- **R119** (DEBE). Ningún archivo de `src/genesis/data/`, `src/genesis/strategy/`,
  `src/genesis/backtest/`, `src/genesis/validation/wfa.py`, `src/genesis/validation/montecarlo.py`,
  `src/genesis/validation/_dsr.py`, `src/genesis/validation/window_config.py`,
  `src/genesis/validation/dsr_pbo.py`, `src/genesis/validation/sensitivity.py`,
  `src/genesis/validation/purged_cv.py`, `src/genesis/validation/_returns.py`,
  `src/genesis/validation/_windowing.py` DEBE modificarse en este Change (R125).
- **R120** (DEBE). Solo trades OOS DEBEN alimentar `run_prop_sim`/`simulate_challenge_paths` y toda
  la lógica de `verdict.py` (spec §6.1, "regla sin excepción") — `oos_ledgers_by_symbol`,
  `oos_ledger_cosido`, nunca ledgers IS.
- **R121** (NO DEBE). Este Change NO DEBE añadir `scipy`, `statsmodels`, `matplotlib` ni
  `quantstats` a `pyproject.toml` (`[project.dependencies]` ni `dependency-groups.dev`). `rg -n
  "scipy|statsmodels|matplotlib|quantstats" pyproject.toml` DEBE mostrar el mismo estado que antes
  del Change (sin adiciones).
- **R122** (DEBE). Toda excepción de dominio nueva de este Change DEBE heredar de
  `GenesisValidationError` y llevar mensaje con contexto explícito (R3-R4).
- **R123** (DEBE). Ningún artefacto de `prop_sim.py` (`PropSimResult`, `PathOutcome`) DEBE
  serializarse a disco — estructuras en memoria únicamente (R123 aplica a `prop_sim.py`; solo
  `verdict.write_verdict_artifacts` serializa, R100-R102).
- **R124** (DEBE). El loop de trayectorias de `prop_sim.py` (R22) y cualquier loop de candidatos/
  pares de `verdict.py` (T2, R79) DEBEN ejecutarse de forma secuencial (sin `multiprocessing`/
  `concurrent.futures`). `rg -n "multiprocessing|concurrent\.futures"
  src/genesis/validation/prop_sim.py src/genesis/validation/verdict.py` DEBE retornar 0
  coincidencias.
- **R125** (DEBE). `git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
  src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py
  src/genesis/validation/_dsr.py src/genesis/validation/window_config.py
  src/genesis/validation/dsr_pbo.py src/genesis/validation/sensitivity.py
  src/genesis/validation/purged_cv.py src/genesis/validation/_returns.py
  src/genesis/validation/_windowing.py` DEBE quedar vacío al cierre de este Change.

---

## 6. Manejo de errores (resumen normativo, spec §8)

| Excepción | Módulo | Disparador | Efecto |
|---|---|---|---|
| `PropSimConfigError` | `genesis.validation.errors` | `n_paths<=0`; `max_attempts<1`; `horizon_months<1`; `path_horizon_trading_days` insuficiente (R21); canasta diaria vacía (R17); ficha `PropEconomicsProfile` inválida (R12) | Aborta `run_prop_sim`/`simulate_challenge_paths`/`load_prop_economics_profile` antes de simular ninguna trayectoria |
| `VerdictConfigError` | `genesis.validation.errors` | `candidates` vacío (R71); símbolos inconsistentes entre insumos de un candidato (R58); `starting_balance<=0`; intersección de días insuficiente para T2 (R79); varianza degenerada en vol-inversa (R81) | Aborta `run_verdict` antes de evaluar ningún gate |
| (heredado, sin cambios) `WfaConfigError`, `MonteCarloConfigError`, `PurgedCvConfigError`, `DsrPboConfigError`, `SensitivityConfigError` | `genesis.validation.errors` | Sin cambios respecto a H/I | N/A para este Change (`prop_sim.py`/`verdict.py` no invocan `run_wfa`/`monte_carlo_*`/`run_purged_cv`/`run_dsr_pbo`/`run_sensitivity`, solo consumen sus resultados ya producidos) |
| (heredado, propagado sin envolver) `GenesisDataError` | `genesis.data.errors` | `current_git_commit()` no puede determinar el commit vigente (R101) | Aborta `write_verdict_artifacts` |

---

## 7. Criterios de aceptación (evals ejecutables)

```
DADO   el archivo src/genesis/validation/errors.py
CUANDO rg -n "class PropSimConfigError" src/genesis/validation/errors.py
       y rg -n "class VerdictConfigError" src/genesis/validation/errors.py
ENTONCES ambas retornan >=1 coincidencia; ambas heredan de GenesisValidationError (R1-R6)
```

```
DADO   metrics.worst_daily_floating_excursion (src/genesis/backtest/metrics.py:86-93)
CUANDO se invoca sobre un Ledger OOS sin ningún BreachEvent(DAILY)
ENTONCES retorna 0.0; rg -n "worst_daily_floating_excursion" src/genesis/validation/prop_sim.py
         retorna 0 coincidencias (R33-R35, corrección de proposal.md)
```

```
DADO   una ficha PropEconomicsProfile sintética y una canasta diaria sintética con un breach
       diario calculado a mano (rozar el límite sin cruzarlo)
CUANDO se invoca simulate_challenge_paths(..., seed=42, ...)
ENTONCES ninguna trayectoria reinicia intento ese día; el mismo caso con un delta que sí cruza
         el umbral (daily_loss >= threshold) SÍ reinicia el intento (R25, R38a-b)
```

```
DADO   un caso sintético de breach total con MaxLossLimitKind.STATIC
       y el mismo P&L con MaxLossLimitKind.TRAILING
CUANDO se invoca simulate_challenge_paths con cada RiskProfile
ENTONCES el día de breach (o su ausencia) difiere entre ambos según el ancla usada (R36, R38c)
```

```
DADO   un WfaResult sintético con n_trials_signal_total conocido por símbolo y n_candidatos_torneo
       conocido (len(candidates))
CUANDO se invoca run_verdict(candidates, ...)
ENTONCES n_trials_deflactado == sum(n_trials_signal_total por símbolo del ganador) +
         (n_candidatos_torneo - 1), y t1_dsr se calcula invocando
         genesis.validation._dsr.deflated_sharpe_ratio con ese n_trials (R74-R78)
```

```
DADO   dos candidatos sintéticos con correlación OOS conocida < 0.3
       y otro par con correlación conocida >= 0.3
CUANDO se invoca run_verdict con cada configuración
ENTONCES el primer caso produce EnsembleResult no nulo con pesos de vol-inversa normalizados a 1.0;
         el segundo produce EnsembleResult=None (R79-R86)
```

```
DADO   3+ candidatos sintéticos presentados en distintos órdenes de iteración del mapa de entrada
CUANDO se invoca run_verdict con cada permutación
ENTONCES VerdictResult.verdict y winning_candidate_id son idénticos entre todas las permutaciones
         (R94, R95bis)
```

```
DADO   un VerdictResult sintético con verdict=NO_GO
CUANDO se invoca render_tearsheet(result) y la función de manifest (R98) sobre el mismo result
ENTONCES ambos documentos reportan exactamente las mismas cifras de gates G/C/P/T (R97)
```

```
DADO   un directorio temporal (tmp_path) vacío
CUANDO se invoca write_verdict_artifacts(result, tmp_path, ...)
ENTONCES tmp_path/manifest.json y tmp_path/tearsheet.md existen, son no vacíos, y manifest.json es
         JSON válido y determinista byte a byte entre dos invocaciones con los mismos insumos
         (R100, R103, R108)
```

```
DADO   el diff del commit que cierra este Change
CUANDO git diff --stat -- src/genesis/data src/genesis/strategy src/genesis/backtest
       src/genesis/validation/wfa.py src/genesis/validation/montecarlo.py
       src/genesis/validation/_dsr.py src/genesis/validation/window_config.py
       src/genesis/validation/dsr_pbo.py src/genesis/validation/sensitivity.py
       src/genesis/validation/purged_cv.py src/genesis/validation/_returns.py
       src/genesis/validation/_windowing.py
ENTONCES no retorna ninguna línea (R125)
```

```
DADO   el archivo pyproject.toml tras completar este Change
CUANDO rg -n "scipy|statsmodels|matplotlib|quantstats" pyproject.toml
ENTONCES no muestra ninguna de esas dependencias añadida respecto al estado previo al Change (R121)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/validation/ -v
ENTONCES pasa en verde, incluyendo:
         - >=3 golden tests de prop_sim.py calculados a mano (R38-R40)
         - >=1 test de propiedad de monotonía de la ficha de economía (R52)
         - >=1 test de propiedad de invariancia al orden del veredicto (R94, R95bis)
         - >=1 test de propiedad de invariancia al orden del ensemble (R87)
         - >=1 test de determinismo byte a byte de PropSimResult (R53) y de VerdictResult (R109)
         - >=1 test de round-trip del manifest (R105)
         - >=1 test de integración del pipeline completo en segundos (R112)
         - >=1 test marcado pytest.mark.slow de prop_sim (R55) y de verdict con ensemble (R113)
```

```
DADO   el repositorio tras completar este Change
CUANDO uv run pytest tests/validation/ -v y mise run ci
ENTONCES ambos pasan en verde (exit code 0, R114-R115)
```

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| Rg-1 | Corrección de `proposal.md` sobre `worst_daily_floating_excursion` (decisión 4, §3): P3 se evalúa solo sobre la base balance-a-balance, nunca la intradía real — el proxy subestima sistemáticamente la probabilidad real de breach diario. | Un candidato podría pasar P3 en `prop_sim` y aun así violar el límite diario real con mayor frecuencia de la estimada (la base intradía dispara primero en el simulador real, `simulator.py:358-378`). | Documentado explícitamente en tearsheet/manifest (R35, R107) como "cota inferior conservadora"; la incubación en vivo (§10.1-§10.2) actúa como red de seguridad adicional — cualquier breach real durante incubación cancela el forward test incondicionalmente (spec §10.2), mitigando el riesgo residual de este proxy optimista. |
| Rg-2 | Ficha de economía con `challenge_cost_pct_of_balance`/`profit_split_pct` sin cifra confirmada del spec (placeholders, decisión 2 §3). | El veredicto de negocio (interpretación de P2/P5) podría ser optimista o pesimista según cuán alejados estén los placeholders de los valores reales de The5ers. | `economics_confirmed: bool` explícito en `VerdictResult`/tearsheet (R14, R107); no bloquea el código, solo condiciona la interpretación de negocio — mismo criterio que B aplicó a `daily_reset_time`/`daily_loss_limit`. |
| Rg-3 | `n_candidatos_torneo` dinámico (decisión 8, §3): un veredicto emitido con 1-2 candidatos (A archivado o no, B implementado) se compara más adelante con uno que incluya al Candidato C (K, con 3 candidatos). | Confusión si se comparan veredictos de distintas épocas sin revisar `n_candidatos_torneo`. | El manifest registra explícitamente `n_candidatos_torneo`/`n_trials_deflactado` de cada invocación (R78, R98) — cada veredicto es auditable con su propio conteo, sin necesidad de re-ejecutar retroactivamente. |
| Rg-4 | Máquina de estados del challenge (R24-R30) es la lógica más compleja de este Change; un error de un signo/comparación (`>=` vs. `>`, ancla estática vs. trailing) puede alterar sutilmente P1-P5 sin que ningún test unitario aislado lo detecte. | Gates P mal calibrados podrían aprobar o rechazar candidatos incorrectamente. | R38-R40 exigen golden tests calculados a mano para los bordes exactos (rozar/violar, estático/trailing); R52 (monotonía) actúa como test de propiedad adicional independiente de los valores exactos. |
| Rg-5 | Reconstrucción del ensemble (R79-R83) reimplementa la canasta diaria y el resampleo dentro de `verdict.py`, duplicando parcialmente la lógica de `prop_sim.py` (mismo criterio ADR-H5/ADR-I1, pero ahora dentro del mismo Change). | Riesgo de divergencia sutil entre la canasta diaria de `prop_sim.py` y la de `verdict.py` si no se comparte cuidadosamente la función `_build_daily_basket`. | Ambos módulos de este Change comparten la misma reimplementación (documentado en §2, "Canasta diaria"); un test de paridad (`tests/validation/test_verdict.py`) verifica que la canasta diaria de un candidato individual calculada por `verdict.py` coincide exactamente con la de `prop_sim._build_daily_basket` sobre los mismos ledgers. |
| Rg-6 | Alcance grande para un solo Change (idea.md, riesgo explícito): `prop_sim.py` (máquina de estados completa) + `verdict.py` (G+C+P+T1+T2+veredicto+tearsheet+manifest+ensemble) es el Change más grande del camino crítico. | Riesgo de que `design.md`/`tasks.md` subestimen el esfuerzo de implementación y testing. | Decisión 10 (§3) recomienda partir `tasks.md` en dos bloques secuenciales testeables de forma aislada; el volumen de requisitos de este documento (R1-R125) ya refleja esa descomposición modular. |

---

## 9. Preguntas abiertas (no bloquean este Change)

- Nombre/ruta exacta del fixture JSON empaquetado de `PropEconomicsProfile` (decisión 1, §3): se
  resuelve en `design.md` siguiendo el patrón de empaquetado exacto de `risk_profile.json`.
- Firma exacta (orden de parámetros, kw-only vs. posicional, defaults) de `run_prop_sim`,
  `simulate_challenge_paths`, `run_verdict`, `write_verdict_artifacts` — se resuelve en
  `design.md` respetando el comportamiento normativo de esta especificación.
  - **Nota de progreso**: al momento de redactar este `spec.md`, el change dir ya contiene un
    `design.md`/`tasks.md` con placeholders sin llenar (`<!-- Task description -->`, `<!--
    Technical Approach -->`); este documento no los inspecciona ni los valida — es
    responsabilidad de la fase `design` llenarlos respetando los requisitos aquí fijados.
- Regla exacta de "subconjunto máximo de candidatos mutuamente elegibles" para el ensemble cuando
  hay 3+ candidatos que pasan G+C+P (R80) — hoy es teórica (solo B está implementado; A puede
  archivarse en D, C está diferido a K); se revisita con evidencia real cuando exista más de un
  candidato simultáneamente viable.
- Si `challenge_cost_pct_of_balance`/`profit_split_pct` deben confirmarse contra los términos
  vigentes de The5ers antes de interpretar un veredicto `GO` como decisión de negocio definitiva —
  delegado al mismo proceso humano que confirma `daily_reset_time`/símbolos MT5 (Issue B, PA-1/
  PA-2), fuera del alcance de este Change.
- Si `sensitivity.py`/`dsr_pbo.py` deberían exponer sus umbrales de gate (G4/G5/G8/G9) como
  constantes compartidas importables (en vez de que `verdict.py` las redefina localmente, R63) —
  se difiere a `design.md`: I documentó explícitamente que "la comparación contra el umbral es
  responsabilidad de `verdict.py`" (R33 de I, `dsr_pbo.py`), sin mandato de compartir la constante
  numérica en sí.

---

## 10. Referencias

- Issue: https://github.com/bbenja11/genesis/issues/14.
- `.pulse/changes/14-j-feat-validation-prop-sim-verdict-con-gates-t-tearsheet-manifes/idea.md` —
  inventario completo, hallazgo crítico de granularidad MC vs. `prop_sim`, tabla de insumos por
  gate P1-P6/T1-T2, 10 preguntas abiertas.
- `.pulse/changes/14-j-feat-validation-prop-sim-verdict-con-gates-t-tearsheet-manifes/proposal.md`
  — hipótesis de solución, alcance IN/OUT propuesto, 7 preguntas abiertas para `specify` (resueltas
  en §3 de este documento, con una corrección explícita de la decisión 4 sobre
  `worst_daily_floating_excursion`).
- Spec vigente: `docs/SPEC_GENESIS_v1.2_PropTrading_TorneoCandidatos.md` — §1.1 (ficha de la firma),
  §1.2 (economía del embudo), §1.3 (ficha definitiva The5ers: fases 8%/5%, `min_profitable_days=3`,
  `daily_loss_limit=5%` base dual, `max_loss_limit=10%`, "payouts quincenales"), §2.4/§2.x
  (universo de 11 símbolos del Candidato C, referencia de DSR de torneo), §2.5 (higiene del
  torneo: aislamiento, T1, T2), §3 (núcleo propio, periferia pragmática), §6 (tabla capa 4,
  `prop_sim.py`/`verdict.py`), §6.1 (flujo, reglas sin excepción), §6.2 (conteo mecánico de trials
  por candidato — soporte textual de la decisión 8, §3), §7.1-§7.4 (umbrales G/C/P/T definitivos),
  §7.5 (veredicto GO/GO-ENSEMBLE/GO-PARCIAL/NO-GO, iteración única de NO-GO), §7.6 (sanity-checks
  de alcanzabilidad), §8 (manejo de errores, determinismo total), §9 (testing: golden tests de
  challenge calculados a mano, propiedad de monotonía), §10.1-§10.2 (incubación, criterio de
  salida por violación de firma — red de seguridad de Rg-1), §11 (tabla de issues, I bloquea J),
  §11.2 (dependencias de runtime del proyecto).
- `.pulse/specs/validation/spec.md` — spec de dominio acumulada de H+I (líneas 1-1347), en
  particular las notas explícitas "exclusivo de `verdict.py` (Issue J)" repetidas en H e I y la
  tabla de decisiones de I (DSR con `n_trials_signal_total`, reuso de `_dsr.py`, persistencia en
  memoria).
- `.pulse/heuristics/validation.md` — heurísticas de cierre de #10 (H) y #12 (I).
- `src/genesis/validation/__init__.py` (líneas 1-77) — `__all__` curado actual (R65 de H, R60 de
  I), superficie a extender (R118).
- `src/genesis/validation/montecarlo.py` — `McPathsResult` (líneas 32-46), `McSymbolResult`
  (49-56), `McPortfolioResult` (59-68), `monte_carlo_portfolio` (343-393), `_build_basket`
  (287-301), `_extract_exit_returns_by_day` (268-284), `_default_block_size` (110-112),
  `_portfolio_block_bootstrap_paths` (327-340) — patrón de canasta diaria reimplementado
  localmente por `prop_sim.py` (R15-R20), nunca importado.
- `src/genesis/validation/wfa.py` — `WfaResult` (77-90: `oos_ledger_cosido`, `n_windows`,
  `n_trials_signal_total`, `n_trials_execution_total`), `WindowResult` (53-74).
- `src/genesis/validation/dsr_pbo.py` — `deflated_sharpe_ratio_gate` (59-70, patrón de reuso
  interno de `_dsr.py`/`_returns.py` replicado por T1 de `verdict.py`, R76), `DsrPboResult`
  (350-365).
- `src/genesis/validation/_dsr.py` — `deflated_sharpe_ratio(returns, n_trials)` (97-130,
  reutilizada tal cual para T1, sin duplicar la fórmula).
- `src/genesis/validation/_returns.py` — `TradeReturn` (21-33), `extract_trade_returns` (36-68,
  reutilizado por `verdict.py` para construir la canasta diaria del candidato ganador, R73).
- `src/genesis/validation/errors.py` (líneas 1-71) — `GenesisValidationError` y jerarquía existente
  de H/I, extendida con `PropSimConfigError`/`VerdictConfigError` (R1-R6).
- `src/genesis/backtest/metrics.py` — `profit_factor` (42-49), `worst_daily_floating_excursion`
  (86-93, **evidencia de la corrección de la decisión 4, §3**: retorna `0.0` sin
  `BreachEvent(DAILY)`), `min_distance_to_daily_limit` (96-110, mismo patrón, no usado por
  `prop_sim.py`, R34).
- `src/genesis/backtest/ledger.py` — `BreachKind` (21-31), `BreachEvent` (34-47), `RejectionRecord`
  (50-57), `FillRecord` (60-71), `RunProvenance` (74-82), `Ledger` (97-106).
- `src/genesis/backtest/simulator.py` — `_evaluate_daily_breach` (358-378, base dual real:
  `daily_loss = max(loss_vs_close, loss_vs_peak)`, referencia normativa de la decisión 4 §3, R33,
  R35), `_evaluate_total_breach` (380-406, ancla estática vs. trailing, referencia normativa de
  R36).
- `src/genesis/backtest/risk_profile.py` — `MaxLossLimitKind` (22-26), `RiskProfile` (29-40),
  `load_risk_profile` (43-69), `risk_profile_hash` (72-84) — patrón ADR-G2 replicado por
  `PropEconomicsProfile` (R7-R11).
- `src/genesis/data/profile.py` — `FirmProfile` (30-47: `daily_loss_limit_pct`,
  `daily_reset_time`), `firm_profile_hash` (99-115) — patrón de "default conservador, a confirmar"
  replicado por la decisión 2 (§3).
- `src/genesis/data/metadata.py` — `ArtifactMetadata` (50-98, `to_json`/`from_json`), `sha256_of`
  (21-26), `current_git_commit` (29-47) — patrón institucional extendido por el manifest de
  `verdict.py` (R98-R102).
- `pyproject.toml` — dependencias runtime actuales (`metatrader5`, `numpy`, `pandas`, `pyarrow`,
  sin `scipy`/`statsmodels`/`matplotlib`/`quantstats`), marcadores `unit`/`integration`/`e2e`/
  `statistical`/`slow` ya registrados (líneas 76-82), ninguno nuevo requerido por este Change.
- `tests/validation/` — `conftest.py`, `fixtures/`, patrón `test_integration_pipeline_i.py`,
  `test_slow_volume_i.py`, `test_public_api.py` a replicar/extender para
  `test_prop_economics.py`, `test_prop_sim.py`, `test_verdict.py`.
- `.pulse/changes/archive/12-i-feat-validation-purged-k-fold-dsr-pbo-sensibilidad/spec.md` —
  formato y estilo replicado (R1..Rn, tabla de resolución de decisiones, criterios
  DADO/CUANDO/ENTONCES, tabla de riesgos, corrección explícita de una decisión de `proposal.md`
  con evidencia de código, mismo patrón aplicado aquí a la decisión 4).
- Referencias externas citadas por el spec y esta especificación: Bailey, D. H. & López de Prado,
  M. (2014). "The Deflated Sharpe Ratio..." (base de T1, R76); Moskowitz, Ooi & Pedersen (2012)
  (TSMOM, Candidato C, fuera de alcance de este Change).
- Reglas de proceso: `.agents/rules/architecture-conventions.md`,
  `.agents/rules/eval-tdd-conventions.md`, `.agents/rules/tooling-conventions.md`.
- `CLAUDE.md` (raíz) — arquitectura de 4 capas, flujo SDD, cadena de dependencias
  A→B→C→{D/E,G}→H→I→J→K.

<!-- change:46-perf-core-reducir-complejidad-algor-tmica-del-camino-caliente-y -->
<!-- change:46-perf-core-reducir-complejidad-algor-tmica-del-camino-caliente-y -->
# Delta: relajación acotada de la prohibición de importar privados (Issue #46 / perf(core))

Este bloque modifica una regla de los Changes H e I de esta misma capa. No toca ningún gate
G/C/P/T, que **nunca se relajan**, ni ningún requisito de cálculo.

## Qué decía la regla y por qué existía

ADR-I1 y ADR-I2 (y su expresión como requisitos en este documento) prohíben importar símbolos
con prefijo `_` de un módulo ya cerrado por un Change anterior. El objetivo era legítimo:
impedir que un Change nuevo se acoplara a los internos de otro y los congelara de hecho.

El precio se pagó en duplicación. `clip` terminó escrito **tres veces**, byte por byte, en
`montecarlo.py`, `purged_cv.py` y `prop_sim.py`.

## Qué cambia

Se permite un módulo **interno compartido** dentro de la propia capa, `genesis/validation/_shared.py`,
para helpers que sean **idénticos** en todas sus copias. Lleva prefijo `_`, no se exporta en
`genesis/validation/__init__.py` y por tanto no amplía la superficie pública de la capa: la
preocupación original —acoplarse a los internos de otro módulo— no aplica, porque nadie importa
un privado ajeno; importan un helper común que no pertenece a ningún Change.

Alcance de la relajación, deliberadamente estrecho:

| Helper | Decisión | Motivo |
|---|---|---|
| `clip` | **Consolidado** en `_shared.py` | Las 3 copias eran byte-idénticas |
| `_default_block_size` | **No se toca** | La variante de `strategy/candidate_a/diagnostics.py` usa otros bounds (sin piso de 5, con guarda `n <= 0`): unificarla cambiaría resultados numéricos |
| `_first_fill_record` | **No se toca** | Difiere en firma (kwarg `candidate_id`) y en el tipo de excepción entre `montecarlo.py` y `purged_cv.py` |
| Partición contigua (`dsr_pbo` / `purged_cv`) | **No se toca** | Difieren en el tipo de retorno (`tuple` vs `list`) |
| `_extract_exit_returns` (`wfa` / `montecarlo`) | **No se toca**; ADR-H5 sigue vigente | Fundirlos obliga a reabrir un módulo cerrado por un beneficio cosmético. El riesgo real —que las copias divergieran en silencio— se cierra con un test de equivalencia entre ambas, no con un import |

## Por qué no se consolidó más

Porque el criterio no es «reducir líneas» sino «no cambiar resultados». Tres de los cuatro
helpers restantes parecen duplicados y no lo son; unificarlos a ciegas habría alterado la
salida numérica sin que ningún test lo delatara. La regla que gobierna este Change —equivalencia
observacional bit a bit— manda sobre el impulso de deduplicar.

<!-- change:51-fix-validation-un-rechazo-total-de-intents-por-sizing-produce-un -->
# Specification — señalizar "ausencia de evidencia" en rechazos totales de sizing

Change #51 (Refs #46). Formaliza `idea.md` + `proposal.md` acotados a **Capa 1** (decisión
humana registrada en `mem:change-51-scope-decision`): detectar y señalizar que un candidato
quedó sin evidencia porque el embudo Inspector rechazó sus intents por
`LOT_SIZE_OUT_OF_BOUNDS`, sin que esa causa sea indistinguible de un `NO_GO` por desempeño real.

## Objetivo

Que el veredicto de torneo (`run_verdict`) y sus artefactos serializados (manifest JSON,
tearsheet) permitan distinguir, para cada `(candidate_id, symbol)`:

- **G1 falla por desempeño**: hubo `trades_oos_total` insuficientes pero > 0, o 0 trades sin que
  el sizing sea la causa dominante.
- **G1 falla por ausencia de evidencia de sizing**: el candidato nunca llegó a operar ese símbolo
  porque el sizer produjo lotes inviables antes de tocar el mercado.

Sin relajar ningún gate G/C/P/T existente (SSoT `docs/SPEC_GENESIS_v1.4_...md`) y sin ampliar
`VerdictKind` más allá de sus 4 miembros normativos (R91,
`.pulse/specs/validation/spec.md:1977`).

## Alcance

### IN

1. Contar, por `(candidate_id, symbol)`, los intents propuestos por el candidato y clasificarlos
   en autorizados vs. rechazados por motivo, a partir del `Ledger` ya producido por el backtest
   (`RejectionRecord` / `FillRecord`), sin cambiar el formato del ledger.
2. Definir una señal booleana explícita de "evidencia de sizing ausente" a nivel símbolo
   (`SymbolGateOutcome`), agregada a nivel candidato (`CandidateGateSummary`), calculada **antes**
   de `run_verdict` — sin introducir un quinto `VerdictKind`.
3. Exponer esa señal en el manifest JSON y en el tearsheet Markdown (misma fuente única de datos
   que ya usan ambos, `_candidate_summary_payload`), de forma que un consumidor automatizado
   (incl. un futuro arquitecto de estrategias) pueda leerla sin parsear prosa.
4. Fijar un umbral concreto y no ambiguo para esta señal (ver R3), documentado como decisión de
   este Change — no como parámetro configurable (eso es Capa 3, fuera de alcance).

### OUT (YAGNI explícito — changes de seguimiento, no de este Change)

- **Capa 2**: pre-flight algebraico de factibilidad de sizing (banda de `stop_distance` viable).
  Depende de que cada `StrategyCandidate` exponga su fórmula de sizing como dato de primera
  clase; solo verificada para `CandidateB`.
- **Capa 3**: política de sizing configurable (`reject`/`clamp_to_min`/`exclude_symbol`), su
  default, y el versionado/hash de esa configuración (`inspector_funnel_config_hash`).
- Migrar `min_lot`/`max_lot` de `InspectorFunnelConfig` (global) a `SymbolFigure` (por
  símbolo/bróker).
- Cualquier modificación de `VerdictKind` (R91) o de la prioridad de `run_verdict` (R92): si el
  diseño concluyera que hace falta un quinto veredicto, **debe** elevarse explícitamente al
  humano como decisión de spec normativo (`.pulse/specs/validation/spec.md`), no asumirse en
  `design`.
- Un contador explícito de "intents vistos" en `_process_new_entries` (ver hallazgo H1 más abajo:
  no es necesario para este Change, el conteo por inferencia del ledger es correcto y suficiente).

## Hallazgo de verificación de código (resuelve la pregunta abierta 7 del proposal)

**H1 — `_open_position`/`_resolve_entry_fill` NO puede perder el fill de un intent ya
autorizado.** Verificado en `src/genesis/backtest/simulator.py`:

- `_resolve_entry_fill` (líneas 169-185) tiene tipo de retorno `ResolvedFill` (no
  `ResolvedFill | None`): si `coverage` es `True` y hay ticks en la ventana de la barra, usa el
  primer tick; en **cualquier otro caso** (sin cobertura, o con cobertura pero sin ticks en la
  ventana) cae al fallback `ResolvedFill(price=bar.open, timestamp_utc=bar.timestamp_utc)`
  (línea 185). No hay ninguna rama que retorne `None` o that omita el registro.
- `_open_position` (líneas 507-561) se invoca únicamente desde `_process_new_entries` (línea 505)
  cuando `verdict.authorized is True`, y **siempre** — sin condicional — construye un
  `OpenPosition` y hace `self.ledger.append(FillRecord(..., is_exit=False, ...))` (líneas
  533-555) usando el resultado no-opcional de `_resolve_entry_fill`.
- Conclusión: todo intent autorizado produce **exactamente un** `FillRecord(is_exit=False)` en el
  ledger, sin excepción y sin dependencia de cobertura de ticks. La asunción del proposal
  ("`n_intents_totales = n_rejections + n_fills_de_entrada`") es **correcta por construcción**,
  no una inferencia post-hoc frágil. No hace falta agregar un contador explícito de "intents
  vistos" en `_process_new_entries` para que el conteo de intents totales sea confiable.

## Requisitos funcionales

- **R1** (mapea idea.md §1/§2, proposal "Contexto observado"). Debe existir una función pura
  (nueva, en `src/genesis/backtest/metrics.py` o módulo equivalente de la capa 3) que, dado un
  `Ledger` de un `(candidate_id, symbol)`, retorne el conteo de intents autorizados
  (`count(FillRecord donde is_exit=False)`) y el conteo de intents rechazados por motivo
  (`count(RejectionRecord)` agrupado por `RejectionReason`), sin mutar el ledger ni depender de
  estado del `Simulator` (forward-only, determinismo).
- **R2** (mapea idea.md §3, proposal "SymbolGateOutcome"). `SymbolGateOutcome`
  (`src/genesis/validation/verdict.py`) debe extenderse con un campo booleano
  `sizing_evidence_insufficient: bool` y con el desglose de motivos de rechazo usado para
  calcularlo, construido en `_build_symbol_gate_outcome` a partir de `wfa_result.oos_ledger_cosido`
  (el `Ledger` ya disponible ahí, sin I/O adicional). No debe alterar `g1_pass` ni ningún otro
  campo `gN_pass` existente: los gates no se relajan.
- **R3** (mapea idea.md pregunta abierta 1, proposal "umbral"). El umbral que fija
  `sizing_evidence_insufficient=True` para un símbolo es: **todos** los intents propuestos para
  ese `(candidate_id, symbol)` fueron rechazados (`intents_autorizados == 0` y
  `intents_totales > 0`) **y** el motivo de rechazo dominante (mayor conteo) es
  `LOT_SIZE_OUT_OF_BOUNDS`. Es un umbral fijo de este Change, no configurable (Capa 3 queda
  fuera). Si `intents_totales == 0` (el candidato nunca propuso ningún intent para ese símbolo,
  p. ej. por señal de entrada inexistente), `sizing_evidence_insufficient` debe ser `False`: es un
  caso distinto (ausencia de señal, no ausencia de evidencia por sizing) y no debe confundirse.
- **R4** (mapea idea.md pregunta abierta 2, proposal "granularidad"). La señal es **por símbolo**
  (`SymbolGateOutcome.sizing_evidence_insufficient`), consistente con la granularidad de G1-G9.
  `CandidateGateSummary` debe agregar hacia arriba con un campo
  `symbols_with_insufficient_sizing_evidence: frozenset[str]` (símbolos del candidato con la señal
  activa), sin promediar ni colapsar la información por símbolo.
- **R5** (mapea idea.md pregunta abierta 3, proposal "reemplaza/rodea R91"). La señal **no**
  introduce un quinto `VerdictKind` ni modifica R91/R92: vive exclusivamente en
  `SymbolGateOutcome`/`CandidateGateSummary`, evaluada antes de `run_verdict`. `VerdictKind`
  sigue teniendo exactamente 4 miembros y `run_verdict` sigue la misma prioridad
  GO_ENSEMBLE→GO→GO_PARCIAL→NO_GO sin ninguna rama nueva. Esta decisión queda fijada por este
  Change; si `design` encontrara que es insuficiente, debe elevarlo al humano en vez de tocar R91
  por su cuenta.
- **R6** (mapea idea.md §4, proposal "manifest/tearsheet"). `_candidate_summary_payload` y
  `render_tearsheet` (`src/genesis/validation/verdict.py`) deben serializar/renderizar
  `sizing_evidence_insufficient` por símbolo y `symbols_with_insufficient_sizing_evidence` por
  candidato, preservando la propiedad R97 existente (tearsheet y manifest comparten la misma
  fuente de datos).
- **R7** (mapea idea.md §3, proposal "nadie actúa sobre `rejection_rate_by_reason`"). El nuevo
  cómputo (R1) reemplaza, para el propósito de esta señal, la dependencia en
  `rejection_rate_by_reason` (que normaliza sobre eventos de riesgo, no sobre intents totales, y
  no tiene consumidores productivos hoy). No es necesario modificar ni eliminar
  `rejection_rate_by_reason`: queda como está, fuera de alcance.

## Criterios de aceptación (evals ejecutables)

- **A1**
  ```
  DADO  un Ledger sintético de un (candidate_id, symbol) con 24 RejectionRecord
        (verdict.rejection_reason=LOT_SIZE_OUT_OF_BOUNDS) y 0 FillRecord(is_exit=False)
  CUANDO se invoca la función de R1 sobre ese Ledger
  ENTONCES retorna intents_autorizados=0, intents_totales=24,
           conteo_por_motivo={"lot_size_out_of_bounds": 24}
  ```
  (test de pytest, `tests/backtest/test_metrics.py` o módulo nuevo equivalente,
  `pytest.mark.unit`).

- **A2**
  ```
  DADO  el Ledger sintético de A1 usado como wfa_result.oos_ledger_cosido de un símbolo
  CUANDO se construye SymbolGateOutcome vía _build_symbol_gate_outcome
  ENTONCES outcome.sizing_evidence_insufficient is True
       Y   outcome.g1_pass is False (sin cambios respecto al comportamiento actual: 0 trades)
       Y   outcome.trades_oos_total == 0
  ```
  (test de pytest, `tests/validation/test_verdict.py`, `pytest.mark.unit`).

- **A3**
  ```
  DADO  un Ledger sintético con 0 RejectionRecord y 0 FillRecord para un símbolo
        (candidato sin señal de entrada en ese símbolo, no un rechazo de sizing)
  CUANDO se construye SymbolGateOutcome vía _build_symbol_gate_outcome
  ENTONCES outcome.sizing_evidence_insufficient is False
  ```
  (test de pytest, `tests/validation/test_verdict.py`, `pytest.mark.unit`; distingue
  explícitamente "sin evidencia por sizing" de "sin señal").

- **A4**
  ```
  DADO  un Ledger sintético con 20 RejectionRecord LOT_SIZE_OUT_OF_BOUNDS y 4
        FillRecord(is_exit=False) para el mismo símbolo (rechazo parcial, no total)
  CUANDO se construye SymbolGateOutcome vía _build_symbol_gate_outcome
  ENTONCES outcome.sizing_evidence_insufficient is False
  ```
  (test de pytest, `tests/validation/test_verdict.py`, `pytest.mark.unit`; confirma que el umbral
  de R3 es "rechazo total", no cualquier concentración).

- **A5**
  ```
  DADO  un VerdictResult con >=1 CandidateGateSummary cuyo símbolo tiene
        sizing_evidence_insufficient=True
  CUANDO se llama render_tearsheet(result) y verdict_result_to_manifest_json(result, ...)
  ENTONCES ambas salidas incluyen la marca de sizing_evidence_insufficient para ese símbolo
       Y   len(VerdictKind) == 4 (no se rompió R91: test de conteo existente sigue en verde)
  ```
  (test de pytest, `tests/validation/test_verdict.py`, `pytest.mark.unit` + `pytest.mark.golden`
  si el repo usa ese marcador para snapshots de tearsheet/manifest — verificar convención
  existente en `tests/validation/` antes de implementar).

- **A6**
  ```
  DADO  el repositorio en el estado posterior a implementar R1-R7
  CUANDO rg -n "class VerdictKind" -A 8 src/genesis/validation/verdict.py
  ENTONCES el bloque sigue mostrando exactamente los 4 miembros GO, GO_ENSEMBLE, GO_PARCIAL,
           NO_GO (ninguno agregado)
  ```
  (eval `rg`, verificación de no-regresión de R91/R5).

- **A7** (propiedad, spec §9). Property test con `hypothesis`: para cualquier combinación de
  conteos `(n_rejections_lot_size, n_rejections_otros_motivos, n_fills)` con
  `n_rejections_lot_size + n_rejections_otros_motivos + n_fills >= 0`,
  `sizing_evidence_insufficient` es `True` si y solo si `n_fills == 0` y
  `n_rejections_lot_size > 0` y `n_rejections_lot_size >= n_rejections_otros_motivos` (motivo
  dominante) y `(n_rejections_lot_size + n_rejections_otros_motivos) > 0`. Marcado
  `pytest.mark.unit`.

## Riesgos

- **Riesgo 1**: si `design` decide construir la señal recorriendo `wfa_result.oos_ledger_cosido`
  en cada llamada a `_build_symbol_gate_outcome`, el costo es O(n_entries) adicional por símbolo;
  a la escala actual del torneo (candidatos × símbolos × ventanas WFA) es marginal, pero debe
  perfilarse si `bench_diagnose.py` lo señala como regresión (no bloquea CI, spec de performance
  en `mem:perf-simulador-y-tickcache`).
- **Riesgo 2**: extender `_candidate_summary_payload` sin actualizar snapshots/golden tests
  existentes de tearsheet/manifest puede romper tests de formato exacto si el repo los tiene
  (verificar `tests/validation/` antes de implementar; no confirmado en esta fase si existen
  golden tests literales del tearsheet completo).
- **Riesgo 3**: el umbral fijo de R3 (100 % de rechazo, motivo dominante
  `LOT_SIZE_OUT_OF_BOUNDS`) es deliberadamente conservador y puede no capturar casos de rechazo
  parcial severo (p. ej. 95 % rechazado) que también constituyen "evidencia insuficiente" en la
  práctica. Se acepta este límite en este Change (ver Preguntas abiertas P1) para no inventar un
  umbral de dominio no pedido por el issue.

## Preguntas abiertas (para el humano / para el Change de seguimiento)

- **P1**: ¿el umbral fijo de "100 % de rechazo por sizing" (R3) es suficiente, o el negocio
  quiere una banda de tolerancia (p. ej. ">=95 %") para capturar casi-rechazos totales? Este
  Change fija 100 % por ser el caso literal reportado en el issue y evitar inventar un valor de
  dominio no especificado; requiere confirmación humana si se quiere ampliar.
- **P2**: si en un Change de seguimiento se retoma Capa 2/Capa 3, ¿el campo
  `sizing_evidence_insufficient` de este Change debe reutilizarse como entrada de esas capas, o
  quedará obsoleto una vez exista el pre-flight algebraico (que evitaría el escenario por
  completo)? No se resuelve aquí — es diseño del Change de seguimiento.
- **P3**: heredada de `proposal.md` — fórmula de sizing de `CandidateA` no verificada; irrelevante
  para este Change (Capa 1 no depende de la fórmula de sizing de ningún candidato, solo del
  resultado ya rechazado/autorizado en el ledger), pero condiciona el alcance de un futuro Change
  de Capa 2.
