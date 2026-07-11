"""Capa 4 — validación: WFA, MC, purged K-fold, DSR/PBO, sensibilidad, prop_sim, veredicto.

`__all__` mínimo y curado (patrón `genesis.backtest.__init__`, R65): expone
únicamente la superficie normativa de H (`errors.py`, `window_config.py`,
`wfa.py`, `montecarlo.py`), Issue I (`purged_cv.py`, `dsr_pbo.py`,
`sensitivity.py`, R60) e Issue J (`prop_sim.py`, `verdict.py`, R117/R118).
Ningún módulo interno de detalle (prefijo guion bajo) ni función/dataclase de
composición interna de esos módulos se re-exporta aquí (R14, R10, ADR-I5,
§1.10): la canasta diaria compartida de capa 4, las constantes de umbral de
gate, y las funciones de (de)serialización del manifest (detalle de
composición de `write_verdict_artifacts`) permanecen internos.
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
    PropSimConfigError,
    PurgedCvConfigError,
    SensitivityConfigError,
    VerdictConfigError,
    WfaConfigError,
)
from genesis.validation.montecarlo import (
    McPathsResult,
    McPortfolioResult,
    McSymbolResult,
    monte_carlo_portfolio,
    monte_carlo_symbol,
)
from genesis.validation.prop_sim import (
    PathOutcome,
    PhaseSpec,
    PropEconomicsProfile,
    PropSimConfig,
    PropSimOutcomeKind,
    PropSimResult,
    load_prop_economics_profile,
    prop_economics_profile_hash,
    run_prop_sim,
    simulate_challenge_paths,
)
from genesis.validation.purged_cv import PurgedCvConfig, PurgedCvResult, PurgedFold, run_purged_cv
from genesis.validation.sensitivity import (
    CostStressOutcome,
    PerturbationOutcome,
    SensitivityConfig,
    SensitivityResult,
    run_sensitivity,
)
from genesis.validation.verdict import (
    CandidateGateSummary,
    CandidateValidationBundle,
    EnsembleResult,
    SymbolGateOutcome,
    VerdictKind,
    VerdictResult,
    render_tearsheet,
    run_verdict,
    write_verdict_artifacts,
)
from genesis.validation.wfa import WfaResult, WindowResult, run_wfa
from genesis.validation.window_config import GridConfig, WfaWindowConfig, window_identity_hash

__all__ = [
    "CandidateGateSummary",
    "CandidateValidationBundle",
    "CostStressOutcome",
    "CscvResult",
    "DsrPboConfigError",
    "DsrPboResult",
    "EnsembleResult",
    "GenesisValidationError",
    "GridConfig",
    "McPathsResult",
    "McPortfolioResult",
    "McSymbolResult",
    "MonteCarloConfigError",
    "PathOutcome",
    "PerturbationOutcome",
    "PhaseSpec",
    "PropEconomicsProfile",
    "PropSimConfig",
    "PropSimConfigError",
    "PropSimOutcomeKind",
    "PropSimResult",
    "PurgedCvConfig",
    "PurgedCvConfigError",
    "PurgedCvResult",
    "PurgedFold",
    "SensitivityConfig",
    "SensitivityConfigError",
    "SensitivityResult",
    "SignalTrialMatrix",
    "SymbolGateOutcome",
    "VerdictConfigError",
    "VerdictKind",
    "VerdictResult",
    "WfaConfigError",
    "WfaResult",
    "WfaWindowConfig",
    "WindowResult",
    "build_signal_trial_matrix",
    "load_prop_economics_profile",
    "monte_carlo_portfolio",
    "monte_carlo_symbol",
    "prop_economics_profile_hash",
    "render_tearsheet",
    "run_dsr_pbo",
    "run_prop_sim",
    "run_purged_cv",
    "run_sensitivity",
    "run_verdict",
    "run_wfa",
    "simulate_challenge_paths",
    "window_identity_hash",
    "write_verdict_artifacts",
]
