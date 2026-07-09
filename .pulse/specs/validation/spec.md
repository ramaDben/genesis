
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
