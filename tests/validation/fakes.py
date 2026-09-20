"""Fakes deterministas reutilizables para la suite `tests/validation/` (R20/D5, Issue #53).

Patrón `tests/strategy/fakes.py`: fábricas deterministas, parametrizables, sin
lógica de trading real. `make_candidate_validation_bundle` (T10) reutiliza el
mismo patrón que las funciones privadas de `tests/validation/test_verdict.py`
(`_wfa_result`/`_dsr_pbo_result`/...), expuesto aquí para que
`test_verdict_ledger.py` no duplique el harness.
"""

from collections.abc import Mapping

import numpy as np

from genesis.backtest.ledger import ExhaustionPolicy, Ledger, RunProvenance
from genesis.validation.dsr_pbo import CscvResult, DsrPboResult
from genesis.validation.montecarlo import McPathsResult, McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import BiasDirection, BreachEvaluationBasis, PropSimResult
from genesis.validation.sensitivity import CostStressOutcome, PerturbationOutcome, SensitivityResult
from genesis.validation.trial_ledger import (
    TrialIdentityContext,
    TrialOutcomeKind,
    TrialRecord,
)
from genesis.validation.verdict import CandidateValidationBundle
from genesis.validation.wfa import WfaResult
from tests.validation.fixtures.ledgers import build_ledger

_DEFAULT_DATASET_HASH_BY_SYMBOL: Mapping[str, str] = {"US500": "dataset-hash-fake"}
_DEFAULT_FIRM_PROFILE_HASH = "firm-profile-hash-fake"
_DEFAULT_EXIT_GEOMETRY_HASH = "exit-geometry-hash-fake"
_DEFAULT_HOUSE_RULE_HASH = "house-rule-hash-fake"
_DEFAULT_GIT_COMMIT = "0000000000000000000000000000000000000fake"
_DEFAULT_CONFIG_VERSION = "genesis-validation-trial-ledger/1"
_DEFAULT_RECORDED_AT_UTC = "2026-01-01T00:00:00+00:00"


def make_trial_identity_context(
    *,
    dataset_hash_by_symbol: Mapping[str, str] | None = None,
    firm_profile_hash: str = _DEFAULT_FIRM_PROFILE_HASH,
    exit_geometry_hash: str = _DEFAULT_EXIT_GEOMETRY_HASH,
    house_rule_hash: str = _DEFAULT_HOUSE_RULE_HASH,
    git_commit: str = _DEFAULT_GIT_COMMIT,
) -> TrialIdentityContext:
    """`TrialIdentityContext` determinista con defaults razonables para tests."""
    return TrialIdentityContext(
        dataset_hash_by_symbol=(
            dataset_hash_by_symbol
            if dataset_hash_by_symbol is not None
            else dict(_DEFAULT_DATASET_HASH_BY_SYMBOL)
        ),
        firm_profile_hash=firm_profile_hash,
        exit_geometry_hash=exit_geometry_hash,
        house_rule_hash=house_rule_hash,
        git_commit=git_commit,
    )


def make_trial_record(
    *,
    trial_id: str = "trial-fake-0",
    candidate_id: str = "A",
    symbol: str = "US500",
    outcome: TrialOutcomeKind = TrialOutcomeKind.WFA_COMPLETADO,
    discard_reason: str | None = None,
    config_version: str = _DEFAULT_CONFIG_VERSION,
    dataset_hash_by_symbol: Mapping[str, str] | None = None,
    firm_profile_hash: str = _DEFAULT_FIRM_PROFILE_HASH,
    exit_geometry_hash: str = _DEFAULT_EXIT_GEOMETRY_HASH,
    house_rule_hash: str = _DEFAULT_HOUSE_RULE_HASH,
    git_commit: str = _DEFAULT_GIT_COMMIT,
    recorded_at_utc: str = _DEFAULT_RECORDED_AT_UTC,
) -> TrialRecord:
    """`TrialRecord` determinista y parametrizable, sin lógica de trading real.

    Dos invocaciones con los mismos argumentos explícitos (incluido
    `recorded_at_utc` fijo) producen `TrialRecord` iguales (`==`).
    """
    return TrialRecord(
        trial_id=trial_id,
        candidate_id=candidate_id,
        symbol=symbol,
        outcome=outcome,
        discard_reason=discard_reason,
        config_version=config_version,
        dataset_hash_by_symbol=(
            dataset_hash_by_symbol
            if dataset_hash_by_symbol is not None
            else dict(_DEFAULT_DATASET_HASH_BY_SYMBOL)
        ),
        firm_profile_hash=firm_profile_hash,
        exit_geometry_hash=exit_geometry_hash,
        house_rule_hash=house_rule_hash,
        git_commit=git_commit,
        recorded_at_utc=recorded_at_utc,
    )


def make_discarded_trial_record(
    *,
    trial_id: str = "trial-discarded-fake-0",
    candidate_id: str = "A",
    symbol: str = "US500",
    discard_reason: str = "descartado antes de completar el WFA (harness sintético)",
    config_version: str = _DEFAULT_CONFIG_VERSION,
    dataset_hash_by_symbol: Mapping[str, str] | None = None,
    firm_profile_hash: str = _DEFAULT_FIRM_PROFILE_HASH,
    exit_geometry_hash: str = _DEFAULT_EXIT_GEOMETRY_HASH,
    house_rule_hash: str = _DEFAULT_HOUSE_RULE_HASH,
    git_commit: str = _DEFAULT_GIT_COMMIT,
    recorded_at_utc: str = _DEFAULT_RECORDED_AT_UTC,
) -> TrialRecord:
    """`TrialRecord` con `outcome=DESCARTADO`, sin ningún `WfaResult` asociado (R20).

    Cubre la regla normativa del usuario (A1): un candidato descartado antes de
    completar un WFA suma igual a `n_trials`. Esta fábrica no acepta ni expone
    ningún `WfaResult`: el descarte ocurre, por definición, sin llegar a producir
    uno.
    """
    return make_trial_record(
        trial_id=trial_id,
        candidate_id=candidate_id,
        symbol=symbol,
        outcome=TrialOutcomeKind.DESCARTADO,
        discard_reason=discard_reason,
        config_version=config_version,
        dataset_hash_by_symbol=dataset_hash_by_symbol,
        firm_profile_hash=firm_profile_hash,
        exit_geometry_hash=exit_geometry_hash,
        house_rule_hash=house_rule_hash,
        git_commit=git_commit,
        recorded_at_utc=recorded_at_utc,
    )


# --- T10 (Change #53): fábrica de bundles con candidate_config, para test_verdict_ledger.py ---

_BUNDLE_STARTING_BALANCE = 100_000.0
_BUNDLE_PROVENANCE = RunProvenance(
    candidate_id="A",
    config_version="genesis-backtest/1",
    dataset_hash="test-dataset-hash",
    firm_profile_hash=_DEFAULT_FIRM_PROFILE_HASH,
    exit_geometry_hash=_DEFAULT_EXIT_GEOMETRY_HASH,
    house_rule_hash=_DEFAULT_HOUSE_RULE_HASH,
    exhaustion_policy=ExhaustionPolicy.RECORD_AND_CONTINUE,
)


def _passing_ledger_fake(*, symbol: str = "US500") -> Ledger:
    """400 trades de +1.0: G1 (>=300 trades) y G3 (PF=inf) trivialmente en verde."""
    return build_ledger([1.0] * 400, symbol=symbol)


def make_wfa_result_fake(
    *, symbol: str = "US500", wfe: float = 0.6, ledger: Ledger | None = None
) -> WfaResult:
    """`WfaResult` determinista mínima para el harness del ledger (sin trading real)."""
    return WfaResult(
        candidate_id="A",
        symbol=symbol,
        config_version="genesis-validation/1",
        windows=[],
        oos_ledger_cosido=ledger if ledger is not None else _passing_ledger_fake(symbol=symbol),
        wfe=wfe,
        n_windows=5,
        n_trials_signal_total=45,
        n_trials_execution_total=135,
        seed=1,
    )


def make_dsr_pbo_result_fake(
    *, symbol: str = "US500", dsr: float = 0.98, pbo: float = 0.1
) -> DsrPboResult:
    return DsrPboResult(
        candidate_id="A",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        dsr=dsr,
        n_trials_signal_total=45,
        pbo=pbo,
        cscv=CscvResult(pbo=pbo, n_splits=4, n_combinations=6, logit_by_combination=[0.1] * 6),
    )


def make_sensitivity_result_fake(
    *,
    symbol: str = "US500",
    has_cliff: bool = False,
    max_relative_drop: float = 0.1,
    pf_stress_1_5x: float = 1.5,
) -> SensitivityResult:
    perturbations = [
        PerturbationOutcome(
            axis="n_minutes",
            direction=1,
            perturbed_value=10.0,
            profit_factor=1.3,
            relative_drop=max_relative_drop,
            is_cliff=has_cliff,
        )
    ]
    cost_stress = [
        CostStressOutcome(multiplier=1.5, profit_factor=pf_stress_1_5x),
        CostStressOutcome(multiplier=2.0, profit_factor=pf_stress_1_5x),
    ]
    return SensitivityResult(
        candidate_id="A",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        baseline_profit_factor=1.4,
        perturbations=perturbations,
        cost_stress=cost_stress,
        has_cliff=has_cliff,
    )


def _mc_paths_result_fake(
    *, max_drawdown_p95: float = 1_000.0, breach_probability: float = 0.01
) -> McPathsResult:
    return McPathsResult(
        max_drawdown_per_path=np.array([max_drawdown_p95]),
        breach_per_path=np.array([False]),
        max_drawdown_p95=max_drawdown_p95,
        breach_probability=breach_probability,
        seed=1,
        n_paths=1,
        block_size=5,
    )


def make_mc_symbol_result_fake(
    *, symbol: str = "US500", max_drawdown_p95: float = 1_000.0, breach_probability: float = 0.01
) -> McSymbolResult:
    return McSymbolResult(
        symbol=symbol,
        provenance=_BUNDLE_PROVENANCE,
        reshuffle=_mc_paths_result_fake(),
        block_bootstrap=_mc_paths_result_fake(
            max_drawdown_p95=max_drawdown_p95, breach_probability=breach_probability
        ),
    )


def make_mc_portfolio_result_fake(*, symbol: str = "US500") -> McPortfolioResult:
    return McPortfolioResult(
        provenance_by_symbol={symbol: _BUNDLE_PROVENANCE}, block_bootstrap=_mc_paths_result_fake()
    )


def make_prop_sim_result_fake(
    *,
    p_pass: float = 0.7,
    expected_attempts: float = 1.5,
    p_daily_breach_funded_month: float = 0.01,
    median_funded_survival_months: float = 8.0,
    payout_p25_12m: float = 100.0,
) -> PropSimResult:
    return PropSimResult(
        candidate_id="A",
        config_version="genesis-validation-j/1",
        seed=1,
        n_paths=100,
        p_pass=p_pass,
        expected_attempts=expected_attempts,
        expected_attempts_p50=expected_attempts,
        expected_attempts_p90=expected_attempts,
        p_daily_breach_funded_month=p_daily_breach_funded_month,
        median_funded_survival_months=median_funded_survival_months,
        payout_p25_12m=payout_p25_12m,
        n_paths_never_funded=10,
        n_paths_funded_breached_total=10,
        n_paths_funded_survived_horizon=70,
        total_challenge_cost_paid=300.0,
        breach_evaluation_basis=BreachEvaluationBasis.CLOSE_TO_CLOSE_PROXY,
        bias_direction=BiasDirection.UNDERESTIMATES_BREACH,
    )


def make_candidate_validation_bundle(
    *,
    candidate_id: str = "A",
    symbols: tuple[str, ...] = ("US500",),
    candidate_config: Mapping[str, object] | None = None,
    wfa_by_symbol: Mapping[str, WfaResult] | None = None,
    dsr_pbo_by_symbol: Mapping[str, DsrPboResult] | None = None,
    sensitivity_by_symbol: Mapping[str, SensitivityResult] | None = None,
    mc_symbol_by_symbol: Mapping[str, McSymbolResult] | None = None,
    prop_sim_result: PropSimResult | None = None,
) -> CandidateValidationBundle:
    """`CandidateValidationBundle` determinista con `candidate_config` inyectable (T10, Q5).

    Patrón `_bundle` de `tests/validation/test_verdict.py`, reutilizable desde
    `test_verdict_ledger.py` (integración con `TrialLedger`).
    """
    return CandidateValidationBundle(
        candidate_id=candidate_id,
        wfa_results_by_symbol=wfa_by_symbol or {s: make_wfa_result_fake(symbol=s) for s in symbols},
        dsr_pbo_results_by_symbol=dsr_pbo_by_symbol
        or {s: make_dsr_pbo_result_fake(symbol=s) for s in symbols},
        sensitivity_results_by_symbol=sensitivity_by_symbol
        or {s: make_sensitivity_result_fake(symbol=s) for s in symbols},
        mc_symbol_results_by_symbol=mc_symbol_by_symbol
        or {s: make_mc_symbol_result_fake(symbol=s) for s in symbols},
        mc_portfolio_result=make_mc_portfolio_result_fake(symbol=symbols[0]),
        prop_sim_result=(
            prop_sim_result if prop_sim_result is not None else make_prop_sim_result_fake()
        ),
        candidate_config=candidate_config,
    )
