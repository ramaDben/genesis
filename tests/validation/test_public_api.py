"""Tests de la API pública re-exportada por `genesis.validation.__init__` (R14, R60, R65)."""

import pytest

import genesis.validation as validation_pkg

pytestmark = pytest.mark.unit

_EXPECTED_ALL = {
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
    # Issue I (R60, ADR-I5): Purged K-Fold + DSR/PBO + sensibilidad.
    "CostStressOutcome",
    "CscvResult",
    "DsrPboConfigError",
    "DsrPboResult",
    "PerturbationOutcome",
    "PurgedCvConfig",
    "PurgedCvConfigError",
    "PurgedCvResult",
    "PurgedFold",
    "SensitivityConfig",
    "SensitivityConfigError",
    "SensitivityResult",
    "SignalTrialMatrix",
    "build_signal_trial_matrix",
    "run_dsr_pbo",
    "run_purged_cv",
    "run_sensitivity",
    # Issue J (R118): prop_sim.py + verdict.py (gates G/C/P/T1/T2, veredicto, tearsheet/manifest).
    "CandidateGateSummary",
    "CandidateValidationBundle",
    "EnsembleResult",
    "PathOutcome",
    "PhaseSpec",
    "PropEconomicsProfile",
    "PropSimConfig",
    "PropSimConfigError",
    "PropSimOutcomeKind",
    "PropSimResult",
    "SymbolGateOutcome",
    "VerdictConfigError",
    "VerdictKind",
    "VerdictResult",
    "load_prop_economics_profile",
    "prop_economics_profile_hash",
    "render_tearsheet",
    "run_prop_sim",
    "run_verdict",
    "simulate_challenge_paths",
    "write_verdict_artifacts",
    # Issue D (R119-R122): diagnóstico de señal desnuda (kill-switch del Candidato A).
    "ArchiveOrContinue",
    "SignalDiagnosticConfigError",
    "SignalDiagnosticReport",
    "render_signal_diagnostic_markdown",
    "run_signal_diagnostic",
    "write_signal_diagnostic_artifacts",
}


def test_all_contiene_exactamente_la_superficie_curada_minima() -> None:
    assert set(validation_pkg.__all__) == _EXPECTED_ALL


def test_todos_los_nombres_de_all_son_importables() -> None:
    for name in validation_pkg.__all__:
        assert hasattr(validation_pkg, name), f"'{name}' está en __all__ pero no es importable"


def test_deflated_sharpe_ratio_no_se_reexporta() -> None:
    """R14: `deflated_sharpe_ratio` (y sus helpers internos) nunca en `__all__`."""
    assert "deflated_sharpe_ratio" not in validation_pkg.__all__
    assert "_standard_normal_cdf" not in validation_pkg.__all__
    assert "_standard_normal_ppf" not in validation_pkg.__all__
    assert not hasattr(validation_pkg, "deflated_sharpe_ratio")


def test_importa_todos_los_simbolos_publicos_normativos_sin_error() -> None:
    from genesis.validation import (  # noqa: F401
        GenesisValidationError,
        GridConfig,
        McPathsResult,
        McPortfolioResult,
        McSymbolResult,
        MonteCarloConfigError,
        WfaConfigError,
        WfaResult,
        WfaWindowConfig,
        WindowResult,
        monte_carlo_portfolio,
        monte_carlo_symbol,
        run_wfa,
        window_identity_hash,
    )


def test_importa_la_superficie_publica_de_issue_i_sin_error() -> None:
    """R60 (ADR-I5): `build_signal_trial_matrix`/`SignalTrialMatrix` públicos."""
    from genesis.validation import (  # noqa: F401
        CostStressOutcome,
        CscvResult,
        DsrPboConfigError,
        DsrPboResult,
        PerturbationOutcome,
        PurgedCvConfig,
        PurgedCvConfigError,
        PurgedCvResult,
        PurgedFold,
        SensitivityConfig,
        SensitivityConfigError,
        SensitivityResult,
        SignalTrialMatrix,
        build_signal_trial_matrix,
        run_dsr_pbo,
        run_purged_cv,
        run_sensitivity,
    )


def test_detalles_internos_de_issue_i_no_se_reexportan() -> None:
    """R10/ADR-I5: `_returns`/`_windowing`/`deflated_sharpe_ratio_gate`/CSCV interno ausentes."""
    assert "extract_trade_returns" not in validation_pkg.__all__
    assert "TradeReturn" not in validation_pkg.__all__
    assert "deflated_sharpe_ratio_gate" not in validation_pkg.__all__
    assert "combinatorial_symmetric_cross_validation" not in validation_pkg.__all__
    assert not hasattr(validation_pkg, "deflated_sharpe_ratio_gate")


def test_importa_la_superficie_publica_de_issue_j_sin_error() -> None:
    """R117/R118: superficie normativa de prop_sim.py/verdict.py importa sin error."""
    from genesis.validation import (  # noqa: F401
        CandidateGateSummary,
        CandidateValidationBundle,
        EnsembleResult,
        PathOutcome,
        PhaseSpec,
        PropEconomicsProfile,
        PropSimConfig,
        PropSimConfigError,
        PropSimOutcomeKind,
        PropSimResult,
        SymbolGateOutcome,
        VerdictConfigError,
        VerdictKind,
        VerdictResult,
        load_prop_economics_profile,
        prop_economics_profile_hash,
        render_tearsheet,
        run_prop_sim,
        run_verdict,
        simulate_challenge_paths,
        write_verdict_artifacts,
    )


def test_detalles_internos_de_issue_j_no_se_reexportan() -> None:
    """§1.10: `_build_daily_basket` ni las funciones de composición del manifest se reexportan."""
    assert "_build_daily_basket" not in validation_pkg.__all__
    assert "verdict_result_to_manifest_json" not in validation_pkg.__all__
    assert "manifest_json_to_verdict_summary" not in validation_pkg.__all__
    assert not hasattr(validation_pkg, "_build_daily_basket")
    assert not hasattr(validation_pkg, "verdict_result_to_manifest_json")


def test_importa_la_superficie_publica_de_issue_d_sin_error() -> None:
    """R119-R122: superficie normativa de `signal_diagnostic.py` importa sin error."""
    from genesis.validation import (  # noqa: F401
        ArchiveOrContinue,
        SignalDiagnosticConfigError,
        SignalDiagnosticReport,
        render_signal_diagnostic_markdown,
        run_signal_diagnostic,
        write_signal_diagnostic_artifacts,
    )


def test_detalles_internos_de_issue_d_no_se_reexportan() -> None:
    """`estimate_roundtrip_cost`/`decide_verdict`/`signal_diagnostic_report_to_json` internos."""
    assert "estimate_roundtrip_cost" not in validation_pkg.__all__
    assert "decide_verdict" not in validation_pkg.__all__
    assert "signal_diagnostic_report_to_json" not in validation_pkg.__all__
    assert not hasattr(validation_pkg, "estimate_roundtrip_cost")
