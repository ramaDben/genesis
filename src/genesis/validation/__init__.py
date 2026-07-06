"""Capa 4 — validación: WFA, MC, purged K-fold, DSR/PBO, prop_sim, veredicto.

`__all__` mínimo y curado (patrón `genesis.backtest.__init__`, R65): expone
únicamente la superficie normativa de este Change (`errors.py`, `window_config.py`,
`wfa.py`, `montecarlo.py`). El módulo interno de Deflated Sharpe Ratio (`_dsr.py`,
usado exclusivamente por `wfa.py` para seleccionar dentro del grid IS) **nunca** se
re-exporta aquí (R14): no es la implementación normativa del gate G4/T1 (Issue I).
"""

from genesis.validation.errors import (
    GenesisValidationError,
    MonteCarloConfigError,
    WfaConfigError,
)
from genesis.validation.montecarlo import (
    McPathsResult,
    McPortfolioResult,
    McSymbolResult,
    monte_carlo_portfolio,
    monte_carlo_symbol,
)
from genesis.validation.wfa import WfaResult, WindowResult, run_wfa
from genesis.validation.window_config import GridConfig, WfaWindowConfig, window_identity_hash

__all__ = [
    "GenesisValidationError",
    "GridConfig",
    "McPathsResult",
    "McPortfolioResult",
    "McSymbolResult",
    "MonteCarloConfigError",
    "WfaConfigError",
    "WfaResult",
    "WfaWindowConfig",
    "WindowResult",
    "monte_carlo_portfolio",
    "monte_carlo_symbol",
    "run_wfa",
    "window_identity_hash",
]
