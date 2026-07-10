"""Jerarquía de excepciones de dominio de `genesis.validation` (capa 4: validación).

Raíz propia (`GenesisValidationError`), independiente de `GenesisBacktestError`
(`genesis.backtest.errors`), `GenesisStrategyError` (`genesis.strategy.errors`) y
`GenesisDataError` (`genesis.data.errors`) — no existe una raíz `GenesisError`
compartida entre capas en el repo (mismo criterio que ADR-C4/ADR-G5, R1). Todo
mensaje de excepción de esta capa debe incluir contexto explícito (`candidate_id`,
`symbol`, índice de ventana, valor involucrado, R4) — fail-fast, nunca degradación
silenciosa.

`BacktestConfigError`/`SessionBoundaryError` (capa 3) se propagan sin capturar ni
envolver cuando ocurren durante un run IS/OOS invocado desde `wfa.py` (R5): este
módulo no define ninguna excepción que las envuelva.
"""


class GenesisValidationError(Exception):
    """Raíz de la jerarquía de excepciones de dominio de `genesis.validation` (capa 4).

    Jerarquía independiente de `GenesisBacktestError`, `GenesisStrategyError` y
    `GenesisDataError` (R1): no hereda de ninguna de las tres.
    """


class WfaConfigError(GenesisValidationError):
    """Configuración o geometría inválida del walk-forward (R2).

    Disparadores normativos: (a) historia insuficiente para al menos una ventana
    completa IS+OOS; (b) `WfaWindowConfig`/`GridConfig` fuera del presupuesto de
    grid (más de 27 combinaciones de ejecución o más de 9 de señal); (c) las 9
    configuraciones de señal de una ventana quedan todas por debajo de
    `MIN_TRADES_IS` (ventana inviable).
    """


class MonteCarloConfigError(GenesisValidationError):
    """Configuración inválida del motor de Monte Carlo (R3).

    Disparadores normativos: `n_paths <= 0`, `block_size <= 0` (cuando se fija
    explícitamente), o un `Ledger`/mapa de ledgers sin ningún trade OOS extraíble.
    """


class PurgedCvConfigError(GenesisValidationError):
    """Configuración o partición inválida del Purged K-Fold con embargo (Issue I, R1).

    Disparadores normativos: `(a)` `n_folds < 2`; `(b)` `embargo_days < 0`; `(c)`
    cualquier fold de test o de train que quede vacío tras purga + embargo; `(d)`
    `oos_ledger` con menos trades OOS que `n_folds` (imposible construir folds no
    vacíos).
    """


class DsrPboConfigError(GenesisValidationError):
    """Configuración o geometría inválida del DSR de gate y del PBO vía CSCV (Issue I, R2).

    Disparadores normativos: `(a)` `n_windows < 4` (techo mínimo de CSCV); `(b)`
    todas las configuraciones de señal de todas las ventanas de la matriz de trials
    quedan por debajo de `MIN_TRADES_IS`; `(c)` `n_splits` de CSCV no par o mayor que
    `n_windows`.
    """


class SensitivityConfigError(GenesisValidationError):
    """Configuración inválida de la perturbación de sensibilidad ±10% (Issue I, R3).

    Disparadores normativos: `(a)` `WfaResult.windows` vacío; `(b)`
    `cost_stress_multipliers` con algún valor `<= 1.0`; `(c)`
    `cliff_relative_drop_threshold` fuera de `(0.0, 1.0]` o `cliff_pf_floor <= 0.0`.
    """


class PropSimConfigError(GenesisValidationError):
    """Configuración inválida de la simulación de challenge, `prop_sim.py` (Issue J, R1).

    Disparadores normativos: `(a)` `n_paths <= 0`; `(b)` `max_attempts < 1`;
    `(c)` `horizon_months < 1`; `(d)` `path_horizon_trading_days` insuficiente
    respecto a `horizon_months * trading_days_per_month`; `(e)` canasta diaria
    vacía (`_build_daily_basket` sin ningún trade OOS extraíble); `(f)` ficha
    `PropEconomicsProfile` inválida (`phases` vacío, umbrales fuera de rango).
    """


class VerdictConfigError(GenesisValidationError):
    """Configuración o insumos inválidos del veredicto de torneo, `verdict.py` (Issue J, R2).

    Disparadores normativos: `(a)` `candidates` vacío; `(b)` símbolos
    inconsistentes entre los mapas por símbolo de `CandidateValidationBundle`;
    `(c)` `starting_balance <= 0`; `(d)` intersección de `trading_day` entre dos
    candidatos para T2 con menos de 2 días; `(e)` desviación estándar `std_i == 0`
    de la canasta de un candidato en los pesos vol-inversa del ensemble.
    """
