"""Tests de `verdict.py`: bundle, gates G/C/P/T1/T2, veredicto, tearsheet/manifest (R57-R113)."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

import genesis.validation.verdict as verdict_module
from genesis.backtest.ledger import BreachEvent, BreachKind, Ledger, RunProvenance
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile
from genesis.validation._dsr import deflated_sharpe_ratio as real_dsr
from genesis.validation.dsr_pbo import CscvResult, DsrPboResult
from genesis.validation.errors import VerdictConfigError
from genesis.validation.montecarlo import McPathsResult, McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import PropSimResult
from genesis.validation.sensitivity import CostStressOutcome, PerturbationOutcome, SensitivityResult
from genesis.validation.verdict import (
    CandidateValidationBundle,
    _build_symbol_gate_outcome,
    _compute_t1,
    build_candidate_gate_summary,
)
from genesis.validation.wfa import WfaResult
from tests.validation.fixtures.ledgers import build_ledger, build_ledger_with_daily_trades

pytestmark = pytest.mark.unit

_STARTING_BALANCE = 100_000.0
_TEST_PROVENANCE = RunProvenance(
    candidate_id="A",
    config_version="genesis-backtest/1",
    dataset_hash="test-dataset-hash",
    firm_profile_hash="test-firm-profile-hash",
    risk_profile_hash="test-risk-profile-hash",
)


def _risk_profile(*, max_loss_limit_pct: float = 10.0) -> RiskProfile:
    return RiskProfile(
        max_loss_limit_pct=max_loss_limit_pct,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
    )


def _passing_ledger() -> Ledger:
    """400 trades de `+1.0` cada uno: G1 (>=300) y G3 (PF=inf) trivialmente en verde."""
    return build_ledger([1.0] * 400)


def _wfa_result(
    *, symbol: str = "US500", wfe: float = 0.6, ledger: Ledger | None = None
) -> WfaResult:
    return WfaResult(
        candidate_id="A",
        symbol=symbol,
        config_version="genesis-validation/1",
        windows=[],
        oos_ledger_cosido=ledger if ledger is not None else _passing_ledger(),
        wfe=wfe,
        n_windows=5,
        n_trials_signal_total=45,
        n_trials_execution_total=135,
        seed=1,
    )


def _dsr_pbo_result(*, symbol: str = "US500", dsr: float = 0.98, pbo: float = 0.1) -> DsrPboResult:
    return DsrPboResult(
        candidate_id="A",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        dsr=dsr,
        n_trials_signal_total=45,
        pbo=pbo,
        cscv=CscvResult(pbo=pbo, n_splits=4, n_combinations=6, logit_by_combination=[0.1] * 6),
    )


def _sensitivity_result(
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


def _mc_paths_result(
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


def _mc_symbol_result(
    *, symbol: str = "US500", max_drawdown_p95: float = 1_000.0, breach_probability: float = 0.01
) -> McSymbolResult:
    return McSymbolResult(
        symbol=symbol,
        provenance=_TEST_PROVENANCE,
        reshuffle=_mc_paths_result(),
        block_bootstrap=_mc_paths_result(
            max_drawdown_p95=max_drawdown_p95, breach_probability=breach_probability
        ),
    )


def _mc_portfolio_result() -> McPortfolioResult:
    return McPortfolioResult(
        provenance_by_symbol={"US500": _TEST_PROVENANCE}, block_bootstrap=_mc_paths_result()
    )


def _prop_sim_result(
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
    )


def _bundle(
    *,
    candidate_id: str = "A",
    symbols: tuple[str, ...] = ("US500",),
    wfa_by_symbol: dict | None = None,
    dsr_pbo_by_symbol: dict | None = None,
    sensitivity_by_symbol: dict | None = None,
    mc_symbol_by_symbol: dict | None = None,
    prop_sim_result: PropSimResult | None = None,
) -> CandidateValidationBundle:
    return CandidateValidationBundle(
        candidate_id=candidate_id,
        wfa_results_by_symbol=wfa_by_symbol or {s: _wfa_result(symbol=s) for s in symbols},
        dsr_pbo_results_by_symbol=dsr_pbo_by_symbol
        or {s: _dsr_pbo_result(symbol=s) for s in symbols},
        sensitivity_results_by_symbol=sensitivity_by_symbol
        or {s: _sensitivity_result(symbol=s) for s in symbols},
        mc_symbol_results_by_symbol=mc_symbol_by_symbol
        or {s: _mc_symbol_result(symbol=s) for s in symbols},
        mc_portfolio_result=_mc_portfolio_result(),
        prop_sim_result=prop_sim_result if prop_sim_result is not None else _prop_sim_result(),
    )


# --- R58: validación de bundle ---


def test_symbols_inconsistentes_lanza_verdict_config_error() -> None:
    with pytest.raises(VerdictConfigError):
        CandidateValidationBundle(
            candidate_id="A",
            wfa_results_by_symbol={"US500": _wfa_result(symbol="US500")},
            dsr_pbo_results_by_symbol={"NAS100": _dsr_pbo_result(symbol="NAS100")},
            sensitivity_results_by_symbol={"US500": _sensitivity_result(symbol="US500")},
            mc_symbol_results_by_symbol={"US500": _mc_symbol_result(symbol="US500")},
            mc_portfolio_result=_mc_portfolio_result(),
            prop_sim_result=_prop_sim_result(),
        )


def test_bundle_valido_no_lanza() -> None:
    bundle = _bundle()
    assert bundle.candidate_id == "A"


# --- R64: umbrales G1-G9 justo en el borde ---


def test_g1_umbral_300_trades() -> None:
    wfa_pass = _wfa_result(ledger=build_ledger([1.0] * 300))
    wfa_fail = _wfa_result(ledger=build_ledger([1.0] * 299))
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        wfa_pass,
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        wfa_fail,
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g1_pass is True
    assert outcome_fail.g1_pass is False


def test_g2_umbral_wfe_0_5() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(wfe=0.5),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(wfe=0.4999),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g2_pass is True
    assert outcome_fail.g2_pass is False


def test_g3_umbral_profit_factor_1_3() -> None:
    ledger_pass = build_ledger([130.0, -100.0] * 150)  # PF exacto 1.3, 300 trades
    ledger_fail = build_ledger([129.0, -100.0] * 150)  # PF 1.29
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger_pass),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger_fail),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g3_pass is True
    assert outcome_fail.g3_pass is False


def test_g4_umbral_dsr_0_95() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(dsr=0.95),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(dsr=0.9499),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g4_pass is True
    assert outcome_fail.g4_pass is False


def test_g5_umbral_pbo_0_25() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(pbo=0.2499),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(pbo=0.25),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g5_pass is True
    assert outcome_fail.g5_pass is False


def test_g6_umbral_maxdd_p95() -> None:
    # límite total = 10% * 100_000 = 10_000; 0.5 * limite = 5_000
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(max_drawdown_p95=5_000.0),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(max_drawdown_p95=5_000.01),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g6_pass is True
    assert outcome_fail.g6_pass is False


def test_g7_umbral_breach_probability_0_05() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(breach_probability=0.0499),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(breach_probability=0.05),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g7_pass is True
    assert outcome_fail.g7_pass is False


def test_g8_umbral_degradacion_030_y_cliff() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(has_cliff=False, max_relative_drop=0.2999),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail_drop = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(has_cliff=False, max_relative_drop=0.30),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail_cliff = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(has_cliff=True, max_relative_drop=0.01),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g8_pass is True
    assert outcome_fail_drop.g8_pass is False
    assert outcome_fail_cliff.g8_pass is False


def test_g9_umbral_pf_stress_1_15() -> None:
    outcome_pass = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(pf_stress_1_5x=1.15),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    outcome_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(pf_stress_1_5x=1.1499),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_pass.g9_pass is True
    assert outcome_fail.g9_pass is False


def test_all_pass_es_and_de_g1_g9() -> None:
    outcome = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome.all_pass is True

    outcome_one_fail = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(wfe=0.1),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome_one_fail.all_pass is False


# --- R62/R66: P6 sobre BreachEvent real ---


def _ledger_with_breach() -> Ledger:
    ledger = build_ledger([1.0] * 300)
    ledger.append(
        BreachEvent(
            kind=BreachKind.TOTAL,
            trading_day=datetime(2024, 1, 1, tzinfo=UTC).date(),
            timestamp_utc=datetime(2024, 1, 1, tzinfo=UTC),
            magnitude=1000.0,
            threshold=500.0,
            account_exhausted=True,
        )
    )
    return ledger


def test_p6_breach_marca_p6_pass_false_y_registra_violadores() -> None:
    bundle = _bundle(wfa_by_symbol={"US500": _wfa_result(ledger=_ledger_with_breach())})
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)

    assert summary.p6_pass is False
    assert "US500" in summary.p6_violating_symbols
    assert BreachKind.TOTAL in summary.p6_violating_symbols["US500"]


def test_p6_sin_breach_pasa() -> None:
    bundle = _bundle()
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)
    assert summary.p6_pass is True
    assert summary.p6_violating_symbols == {}


# --- C1/C2 y passes_g_c_p ---


def test_c1_fraction_passing_y_pass() -> None:
    bundle = _bundle(symbols=("US500", "NAS100", "US30"))
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)
    assert summary.c1_fraction_passing == pytest.approx(1.0)
    assert summary.c1_pass is True


def test_c2_min_pf_non_passing_es_inf_si_todos_pasan() -> None:
    bundle = _bundle()
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)
    assert summary.c2_min_pf_non_passing == float("inf")
    assert summary.c2_pass is True


def test_passes_g_c_p_true_en_caso_completamente_pasante() -> None:
    bundle = _bundle()
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)
    assert summary.passes_g_c_p is True


def test_passes_g_c_p_false_si_falla_p1() -> None:
    bundle = _bundle(prop_sim_result=_prop_sim_result(p_pass=0.1))
    summary = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)
    assert summary.p1_pass is False
    assert summary.passes_g_c_p is False


# --- B2: T1 (deflación de torneo, R71-R78) ---


def _winner_bundle_with_daily_pnl(
    daily_deltas: list, *, n_trials_signal_total_a: int = 45, n_trials_signal_total_b: int = 27
) -> CandidateValidationBundle:
    ledger_a = build_ledger_with_daily_trades(daily_deltas, symbol="US500")
    wfa_a = _wfa_result(symbol="US500", ledger=ledger_a)
    wfa_a = _replace_wfa_n_trials(wfa_a, n_trials_signal_total_a)
    wfa_b = _wfa_result(symbol="NAS100", ledger=_passing_ledger())
    wfa_b = _replace_wfa_n_trials(wfa_b, n_trials_signal_total_b)
    return _bundle(
        symbols=("US500", "NAS100"),
        wfa_by_symbol={"US500": wfa_a, "NAS100": wfa_b},
    )


def _replace_wfa_n_trials(wfa_result: WfaResult, n_trials_signal_total: int) -> WfaResult:
    return WfaResult(
        candidate_id=wfa_result.candidate_id,
        symbol=wfa_result.symbol,
        config_version=wfa_result.config_version,
        windows=wfa_result.windows,
        oos_ledger_cosido=wfa_result.oos_ledger_cosido,
        wfe=wfa_result.wfe,
        n_windows=wfa_result.n_windows,
        n_trials_signal_total=n_trials_signal_total,
        n_trials_execution_total=wfa_result.n_trials_execution_total,
        seed=wfa_result.seed,
    )


def test_t1_n_trials() -> None:
    base_day = date(2024, 1, 1)
    daily_deltas = [(base_day + timedelta(days=i), 100.0 + i) for i in range(10)]
    winner_bundle = _winner_bundle_with_daily_pnl(
        daily_deltas, n_trials_signal_total_a=45, n_trials_signal_total_b=27
    )
    candidates = {
        "A": winner_bundle,
        "B": _bundle(candidate_id="B"),
        "C": _bundle(candidate_id="C"),
    }

    t1 = _compute_t1("A", candidates)

    assert t1.n_trials_signal_total_ganador == 72
    assert t1.n_candidatos_torneo == 3
    assert t1.n_trials_deflactado == 72 + (3 - 1)


def test_t1_dsr_invoca_dsr_con_n_trials_deflactado(monkeypatch: pytest.MonkeyPatch) -> None:
    base_day = date(2024, 1, 1)
    daily_deltas = [(base_day + timedelta(days=i), 100.0 + i) for i in range(10)]
    winner_bundle = _winner_bundle_with_daily_pnl(daily_deltas)
    candidates = {"A": winner_bundle, "B": _bundle(candidate_id="B")}

    calls: list[int] = []

    def _spy(returns: list, n_trials: int) -> float:
        calls.append(n_trials)
        return real_dsr(returns, n_trials)

    monkeypatch.setattr(verdict_module, "deflated_sharpe_ratio", _spy)

    t1 = _compute_t1("A", candidates)

    assert t1.n_trials_deflactado in calls
    assert 1 in calls  # t1_dsr_pre_deflation invoca con n_trials=1
