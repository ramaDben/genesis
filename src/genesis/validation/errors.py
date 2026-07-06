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
