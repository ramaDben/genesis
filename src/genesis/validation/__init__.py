"""Capa 4 — validación: WFA, MC, purged K-fold, DSR/PBO, sensibilidad, prop_sim, veredicto.

`__all__` mínimo y curado (patrón `genesis.backtest.__init__`, R65): expone
únicamente la superficie normativa de H (`errors.py`, `window_config.py`,
`wfa.py`, `montecarlo.py`) e Issue I (`purged_cv.py`, `dsr_pbo.py`,
`sensitivity.py`, R60). Ningún módulo interno de detalle (prefijo guion bajo)
ni función/dataclass de composición interna de esos módulos se re-exporta
aquí (R14, R10, ADR-I5): no son la implementación normativa de los gates
G4/G5/G8/G9/T1 (Issue J).
"""

from genesis.validation.dsr_pbo import (
    CscvResult,
    DsrPboResult,
    SignalTrialMatrix,
    build_signal_trial_matrix,
    run_dsr_pbo,
)
from genesis.validation.errors import (
    DsrPboConfigError,
    GenesisValidationError,
    MonteCarloConfigError,
    PurgedCvConfigError,
    SensitivityConfigError,
    WfaConfigError,
)
from genesis.validation.montecarlo import (
    McPathsResult,
    McPortfolioResult,
    McSymbolResult,
    monte_carlo_portfolio,
    monte_carlo_symbol,
)
from genesis.validation.purged_cv import PurgedCvConfig, PurgedCvResult, PurgedFold, run_purged_cv
from genesis.validation.sensitivity import (
    CostStressOutcome,
    PerturbationOutcome,
    SensitivityConfig,
    SensitivityResult,
    run_sensitivity,
)
from genesis.validation.wfa import WfaResult, WindowResult, run_wfa
from genesis.validation.window_config import GridConfig, WfaWindowConfig, window_identity_hash

__all__ = [
    "CostStressOutcome",
    "CscvResult",
    "DsrPboConfigError",
    "DsrPboResult",
    "GenesisValidationError",
    "GridConfig",
    "McPathsResult",
    "McPortfolioResult",
    "McSymbolResult",
    "MonteCarloConfigError",
    "PerturbationOutcome",
    "PurgedCvConfig",
    "PurgedCvConfigError",
    "PurgedCvResult",
    "PurgedFold",
    "SensitivityConfig",
    "SensitivityConfigError",
    "SensitivityResult",
    "SignalTrialMatrix",
    "WfaConfigError",
    "WfaResult",
    "WfaWindowConfig",
    "WindowResult",
    "build_signal_trial_matrix",
    "monte_carlo_portfolio",
    "monte_carlo_symbol",
    "run_dsr_pbo",
    "run_purged_cv",
    "run_sensitivity",
    "run_wfa",
    "window_identity_hash",
]
