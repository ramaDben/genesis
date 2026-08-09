"""Tests de `verdict.py`: bundle, gates G/C/P/T1/T2, veredicto, tearsheet/manifest (R57-R113)."""

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import genesis.validation.verdict as verdict_module
from genesis.backtest.ledger import BreachEvent, BreachKind, FillRecord, Ledger, RunProvenance
from genesis.backtest.metrics import IntentAuthorizationCounts
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile
from genesis.data.profile import FirmProfile
from genesis.strategy.contract import Direction
from genesis.strategy.inspector import RejectionReason
from genesis.validation._dsr import deflated_sharpe_ratio as real_dsr
from genesis.validation.dsr_pbo import CscvResult, DsrPboResult
from genesis.validation.errors import VerdictConfigError
from genesis.validation.montecarlo import McPathsResult, McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import (
    PhaseSpec,
    PropEconomicsProfile,
    PropSimConfig,
    PropSimResult,
    load_prop_economics_profile,
)
from genesis.validation.purged_cv import PurgedCvConfig, PurgedCvResult, PurgedFold
from genesis.validation.sensitivity import CostStressOutcome, PerturbationOutcome, SensitivityResult
from genesis.validation.verdict import (
    CandidateValidationBundle,
    VerdictKind,
    _build_symbol_gate_outcome,
    _compute_t1,
    _compute_t2,
    _evaluate_p1_to_p5,
    _is_sizing_evidence_insufficient,
    _pairwise_correlation,
    build_candidate_gate_summary,
    manifest_json_to_verdict_summary,
    render_tearsheet,
    run_verdict,
    verdict_result_to_manifest_json,
    write_verdict_artifacts,
)
from genesis.validation.wfa import WfaResult
from tests.validation.fixtures.ledgers import (
    build_ledger,
    build_ledger_with_daily_trades,
    build_ledger_with_rejections,
)

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
    wfa_by_symbol: Mapping[str, WfaResult] | None = None,
    dsr_pbo_by_symbol: Mapping[str, DsrPboResult] | None = None,
    sensitivity_by_symbol: Mapping[str, SensitivityResult] | None = None,
    mc_symbol_by_symbol: Mapping[str, McSymbolResult] | None = None,
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


# --- Change #51 (R2/R3/R4): señal de "evidencia de sizing ausente" ---


def test_sizing_evidence_insufficient_true_en_rechazo_total() -> None:
    """A2: rechazo total (24 `LOT_SIZE_OUT_OF_BOUNDS`, 0 fills) → señal activa."""
    ledger = build_ledger_with_rejections(n_lot_size=24)
    outcome = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome.sizing_evidence_insufficient is True
    assert outcome.g1_pass is False
    assert outcome.trades_oos_total == 0
    assert outcome.intents_total == 24
    assert outcome.intents_authorized == 0
    assert outcome.rejections_by_reason == {"lot_size_out_of_bounds": 24}


def test_sizing_evidence_insufficient_false_sin_intents() -> None:
    """A3: sin señal de entrada (0 rechazos, 0 fills) distinto de "sin evidencia por sizing"."""
    ledger = build_ledger_with_rejections(n_lot_size=0)
    outcome = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome.sizing_evidence_insufficient is False
    assert outcome.intents_total == 0


def test_sizing_evidence_insufficient_false_en_rechazo_parcial() -> None:
    """A4: rechazo parcial (20 rechazos, 4 fills) no dispara la señal: el umbral es total."""
    ledger = build_ledger_with_rejections(n_lot_size=20, n_entry_fills=4)
    outcome = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome.sizing_evidence_insufficient is False


def test_sizing_evidence_insufficient_false_si_motivo_dominante_no_es_lot_size() -> None:
    """Rechazo total, pero el motivo dominante es otro: la señal no se dispara."""
    ledger = build_ledger_with_rejections(
        n_lot_size=5, n_other_reason=10, other_reason=RejectionReason.NEWS_WINDOW
    )
    outcome = _build_symbol_gate_outcome(
        "US500",
        _wfa_result(ledger=ledger),
        _dsr_pbo_result(),
        _sensitivity_result(),
        _mc_symbol_result(),
        _risk_profile(),
        _STARTING_BALANCE,
    )
    assert outcome.sizing_evidence_insufficient is False


@given(
    n_lot_size=st.integers(min_value=0, max_value=200),
    n_other=st.integers(min_value=0, max_value=200),
    n_fills=st.integers(min_value=0, max_value=200),
)
def test_property_sizing_evidence_insufficient(n_lot_size: int, n_other: int, n_fills: int) -> None:
    """A7: `sizing_evidence_insufficient` ssi `n_fills==0`, `n_lot_size>0` y motivo dominante."""
    counts = IntentAuthorizationCounts(
        intents_authorized=n_fills,
        intents_total=n_fills + n_lot_size + n_other,
        rejections_by_reason=(
            {"lot_size_out_of_bounds": n_lot_size, "insufficient_rr": n_other}
            if n_other > 0
            else {"lot_size_out_of_bounds": n_lot_size}
        )
        if n_lot_size > 0
        else ({"insufficient_rr": n_other} if n_other > 0 else {}),
    )

    result = _is_sizing_evidence_insufficient(counts)

    expected = n_fills == 0 and n_lot_size > 0 and n_lot_size >= n_other
    assert result is expected


def test_symbols_with_insufficient_sizing_evidence_agrega_por_candidato() -> None:
    """Eval propio de T3.1: un símbolo con rechazo total, otro normal."""
    bundle = _bundle(
        symbols=("US500", "NAS100"),
        wfa_by_symbol={
            "US500": _wfa_result(
                symbol="US500", ledger=build_ledger_with_rejections(n_lot_size=24)
            ),
            "NAS100": _wfa_result(symbol="NAS100"),
        },
    )
    summary_before_field = build_candidate_gate_summary(bundle, _risk_profile(), _STARTING_BALANCE)

    assert summary_before_field.symbols_with_insufficient_sizing_evidence == frozenset({"US500"})
    assert summary_before_field.passes_g_c_p == (
        summary_before_field.c1_pass
        and summary_before_field.c2_pass
        and summary_before_field.p1_pass
        and summary_before_field.p2_pass
        and summary_before_field.p3_pass
        and summary_before_field.p4_pass
        and summary_before_field.p5_pass
        and summary_before_field.p6_pass
    )


def test_señal_sizing_en_tearsheet_y_manifest(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """A5 + A6: la señal llega a ambos artefactos y `VerdictKind` sigue con 4 miembros."""
    bundle = _go_quality_bundle("A", seed=3)
    degraded_bundle = _bundle(
        candidate_id="A",
        wfa_by_symbol={"US500": _wfa_result(ledger=build_ledger_with_rejections(n_lot_size=24))},
        dsr_pbo_by_symbol=bundle.dsr_pbo_results_by_symbol,
        sensitivity_by_symbol=bundle.sensitivity_results_by_symbol,
        mc_symbol_by_symbol=bundle.mc_symbol_results_by_symbol,
        prop_sim_result=bundle.prop_sim_result,
    )
    result = run_verdict(
        {"A": degraded_bundle},
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    tearsheet = render_tearsheet(result)
    manifest_raw = verdict_result_to_manifest_json(result, **_MANIFEST_KWARGS)
    manifest = manifest_json_to_verdict_summary(manifest_raw)

    assert "Símbolos sin evidencia de sizing" in tearsheet
    assert "US500" in tearsheet
    candidates_payload = cast("dict[str, Any]", manifest["candidates"])
    assert candidates_payload["A"]["symbols_with_insufficient_sizing_evidence"] == ["US500"]
    assert (
        candidates_payload["A"]["symbol_gate_outcomes"]["US500"]["sizing_evidence_insufficient"]
        is True
    )
    assert len(VerdictKind) == 4
    assert {member.value for member in VerdictKind} == {"go", "go-ensemble", "go-parcial", "no-go"}


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


def test_p3_umbral_daily_breach_estrictamente_menor_0_02() -> None:
    """R70: `p3_pass = p_daily_breach_funded_month < 0.02` (estricto, `==0.02` DEBE fallar)."""
    result_pass = _prop_sim_result(p_daily_breach_funded_month=0.0199)
    result_fail_at_boundary = _prop_sim_result(p_daily_breach_funded_month=0.02)

    _p1, _p2, p3_pass_ok, _p4, _p5 = _evaluate_p1_to_p5(result_pass)
    _p1, _p2, p3_pass_boundary, _p4, _p5 = _evaluate_p1_to_p5(result_fail_at_boundary)

    assert p3_pass_ok is True
    assert p3_pass_boundary is False


def test_p5_umbral_payout_estrictamente_mayor_a_cero() -> None:
    """R70: `p5_pass = payout_p25_12m > 0.0` (estricto, `==0.0` DEBE fallar)."""
    result_pass = _prop_sim_result(payout_p25_12m=0.01)
    result_fail_at_boundary = _prop_sim_result(payout_p25_12m=0.0)

    _p1, _p2, _p3, _p4, p5_pass_ok = _evaluate_p1_to_p5(result_pass)
    _p1, _p2, _p3, _p4, p5_pass_boundary = _evaluate_p1_to_p5(result_fail_at_boundary)

    assert p5_pass_ok is True
    assert p5_pass_boundary is False


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


# --- B3: T2 (ensemble por correlación + vol-inversa, R79-R90) ---

_FAST_ENSEMBLE_CONFIG = PropSimConfig(
    n_paths=20, seed=555, horizon_months=1, trading_days_per_month=5, path_horizon_trading_days=30
)


_TRADES_PER_DAY = 100
"""Suficientes trades/día (x4 días >= 300) para que G1 pase trivialmente (R64)."""


def _daily_ledger(daily_values: list, *, symbol: str = "US500") -> Ledger:
    """Ledger con `_TRADES_PER_DAY` trades por día, sumando exactamente `daily_values[día]`.

    Distribuye cada total diario en muchos trades pequeños (en vez de 1 solo trade
    por día) para que `G1` (>=300 trades OOS) pase trivialmente sin alterar el total
    diario usado por `_build_daily_basket` (suma por día, R15).
    """
    base_day = date(2024, 1, 1)
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    equity = _STARTING_BALANCE
    for day_index, total in enumerate(daily_values):
        per_trade = float(total) / _TRADES_PER_DAY
        day = base_day + timedelta(days=day_index)
        for trade_index in range(_TRADES_PER_DAY):
            entry_time = datetime(day.year, day.month, day.day, 8, 0, tzinfo=UTC) + timedelta(
                seconds=trade_index * 2
            )
            exit_time = entry_time + timedelta(seconds=1)
            ledger.append(
                FillRecord(
                    candidate_id="A",
                    symbol=symbol,
                    timestamp_utc=entry_time,
                    price=100.0,
                    direction=Direction.LONG,
                    is_exit=False,
                    cost_applied=0.0,
                    equity_after=equity,
                )
            )
            equity += per_trade
            ledger.append(
                FillRecord(
                    candidate_id="A",
                    symbol=symbol,
                    timestamp_utc=exit_time,
                    price=100.0,
                    direction=Direction.LONG,
                    is_exit=True,
                    cost_applied=0.0,
                    equity_after=equity,
                )
            )
    return ledger


def _candidate_with_daily_series(
    candidate_id: str, daily_values: list
) -> CandidateValidationBundle:
    ledger = _daily_ledger(daily_values)
    return _bundle(candidate_id=candidate_id, wfa_by_symbol={"US500": _wfa_result(ledger=ledger)})


# Series con PF>=1.3 individualmente (gate G3) y correlación baja entre sí (<0.3, R80);
# encontradas por búsqueda numérica (no analíticas): profit_factor(_LOW_CORR_A)~=3.95,
# profit_factor(_LOW_CORR_B)~=1.32, corrcoef~=0.016.
_LOW_CORR_A = [
    54.558419206478604,
    102.16181435011583,
    53.043707618338715,
    -110.31572316043608,
    110.53558666731178,
    64.63745723640113,
    -33.69532353602852,
    78.1118104196353,
    56.457239618607574,
    49.4132496655526,
]
_LOW_CORR_B = [
    22.84222413157968,
    74.67129866124469,
    -53.6454087001667,
    3.7090052006947225,
    -28.211931267997826,
    79.88462126346275,
    23.9722107481659,
    -9.245675096508862,
    -58.190846235684205,
    -5.7192240618870684,
]


def test_pairwise_correlation_simetria() -> None:
    bundle_a = _candidate_with_daily_series("A", _LOW_CORR_A)
    bundle_b = _candidate_with_daily_series("B", _LOW_CORR_B)

    corr_ab = _pairwise_correlation(bundle_a, bundle_b)
    corr_ba = _pairwise_correlation(bundle_b, bundle_a)

    assert corr_ab == pytest.approx(corr_ba)


def test_pairwise_correlation_menos_de_2_dias_comunes_lanza() -> None:
    bundle_a = _candidate_with_daily_series("A", [10.0])
    bundle_b = _candidate_with_daily_series(
        "B", [20.0]
    )  # 1 solo día común (mismo trading_day base)
    with pytest.raises(VerdictConfigError):
        _pairwise_correlation(bundle_a, bundle_b)


def test_t2_elegible_par_baja_correlacion(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {
        "A": _candidate_with_daily_series("A", _LOW_CORR_A),
        "B": _candidate_with_daily_series("B", _LOW_CORR_B),
    }
    summaries = {
        cid: build_candidate_gate_summary(bundle, risk_profile_fixture, _STARTING_BALANCE)
        for cid, bundle in candidates.items()
    }

    ensemble = _compute_t2(
        candidates,
        summaries,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert ensemble is not None
    assert set(ensemble.member_candidate_ids) == {"A", "B"}
    assert sum(ensemble.weights.values()) == pytest.approx(1.0)


def test_t2_no_elegible_par_alta_correlacion(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {
        "A": _candidate_with_daily_series("A", _LOW_CORR_A),
        "B": _candidate_with_daily_series("B", _LOW_CORR_A),  # idéntica -> correlación 1.0
    }
    summaries = {
        cid: build_candidate_gate_summary(bundle, risk_profile_fixture, _STARTING_BALANCE)
        for cid, bundle in candidates.items()
    }

    ensemble = _compute_t2(
        candidates,
        summaries,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert ensemble is None


def test_t2_ningun_candidato_pasa_g_c_p_retorna_none(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {
        "A": _bundle(candidate_id="A", prop_sim_result=_prop_sim_result(p_pass=0.1)),
        "B": _bundle(candidate_id="B", prop_sim_result=_prop_sim_result(p_pass=0.1)),
    }
    summaries = {
        cid: build_candidate_gate_summary(bundle, risk_profile_fixture, _STARTING_BALANCE)
        for cid, bundle in candidates.items()
    }

    ensemble = _compute_t2(
        candidates,
        summaries,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert ensemble is None


@given(order=st.permutations(["A", "B"]))
@settings(
    max_examples=5, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_t2_order_invariant(
    order: tuple,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
) -> None:
    """R87: permutar el orden de inserción de `candidates` no cambia `weights`."""
    base_candidates = {
        "A": _candidate_with_daily_series("A", _LOW_CORR_A),
        "B": _candidate_with_daily_series("B", _LOW_CORR_B),
    }
    reordered_candidates = {cid: base_candidates[cid] for cid in order}
    summaries = {
        cid: build_candidate_gate_summary(bundle, risk_profile_fixture, _STARTING_BALANCE)
        for cid, bundle in reordered_candidates.items()
    }

    ensemble = _compute_t2(
        reordered_candidates,
        summaries,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert ensemble is not None
    reference_std_a = np.std(np.array(_LOW_CORR_A))
    reference_std_b = np.std(np.array(_LOW_CORR_B))
    inv_a, inv_b = 1.0 / reference_std_a, 1.0 / reference_std_b
    expected_weight_a = inv_a / (inv_a + inv_b)
    expected_weight_b = inv_b / (inv_a + inv_b)
    assert ensemble.weights["A"] == pytest.approx(expected_weight_a)
    assert ensemble.weights["B"] == pytest.approx(expected_weight_b)


# --- B4: veredicto de torneo (R91-R95bis) ---


def _strong_daily_series(seed: int, n: int = 20) -> list:
    """Serie diaria positiva de alto Sharpe (DSR robusto a deflación, seeds documentales)."""
    rng = np.random.default_rng(seed)
    return rng.normal(50.0, 8.0, size=n).tolist()


def _go_quality_bundle(candidate_id: str, seed: int) -> CandidateValidationBundle:
    """Candidato con G/C/P completamente en verde y T1 robusto (DSR alto, R91 rama GO)."""
    ledger = _daily_ledger(_strong_daily_series(seed))
    return _bundle(candidate_id=candidate_id, wfa_by_symbol={"US500": _wfa_result(ledger=ledger)})


def _bad_bundle(candidate_id: str) -> CandidateValidationBundle:
    """Candidato que falla todos los gates G/C/P (R91 rama NO_GO)."""
    return _bundle(
        candidate_id=candidate_id,
        wfa_by_symbol={"US500": _wfa_result(wfe=0.01, ledger=build_ledger([-1.0] * 400))},
        dsr_pbo_by_symbol={"US500": _dsr_pbo_result(dsr=0.1, pbo=0.9)},
        prop_sim_result=_prop_sim_result(p_pass=0.01, median_funded_survival_months=0.5),
    )


def _partial_bundle(candidate_id: str, seed: int) -> CandidateValidationBundle:
    """Candidato con `0 < c1_fraction_passing < 0.60` y P1-P6+T1 válidos (R92 rama GO_PARCIAL).

    3 símbolos comparten el mismo ledger de alto Sharpe (T1 robusto); solo `US500`
    pasa G2 (`wfe`), `NAS100`/`US30` fallan G2 deliberadamente -> `c1_fraction_passing
    == 1/3`.
    """
    ledger = _daily_ledger(_strong_daily_series(seed))
    return _bundle(
        candidate_id=candidate_id,
        symbols=("US500", "NAS100", "US30"),
        wfa_by_symbol={
            "US500": _wfa_result(symbol="US500", wfe=0.6, ledger=ledger),
            "NAS100": _wfa_result(symbol="NAS100", wfe=0.1, ledger=ledger),
            "US30": _wfa_result(symbol="US30", wfe=0.1, ledger=ledger),
        },
    )


def test_verdict_kind_tiene_exactamente_4_miembros() -> None:
    assert len(VerdictKind) == 4
    assert {member.value for member in VerdictKind} == {"go", "go-ensemble", "go-parcial", "no-go"}


def test_verdict_rama_go(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {"A": _go_quality_bundle("A", seed=3)}

    result = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert result.verdict is VerdictKind.GO
    assert result.winning_candidate_id == "A"
    assert result.t1_dsr is not None
    assert result.t1_dsr >= 0.95


def test_verdict_rama_no_go(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {"A": _bad_bundle("A")}

    result = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert result.verdict is VerdictKind.NO_GO
    assert result.winning_candidate_id is None
    assert result.t1_dsr is None
    assert result.ensemble is None


def test_verdict_rama_go_parcial(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {"A": _partial_bundle("A", seed=3)}

    result = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert result.verdict is VerdictKind.GO_PARCIAL
    assert result.winning_candidate_id == "A"
    assert result.candidate_summaries["A"].c1_pass is False
    assert 0.0 < result.candidate_summaries["A"].c1_fraction_passing < 0.60


def _tiny_target_profile() -> PropEconomicsProfile:
    """Ficha con objetivo casi nulo: fondea casi de inmediato a cualquier escala de $ (test)."""
    return PropEconomicsProfile(
        name="TinyTarget",
        phases=(
            PhaseSpec(
                profit_target_pct=0.01,
                min_profitable_days=1,
                min_profit_per_day_pct=0.0001,
                max_calendar_days=None,
            ),
        ),
        challenge_cost_pct_of_balance=0.0,
        profit_split_pct=80.0,
        payout_cycle_days=2,
        max_lots=None,
        max_positions=None,
        consistency_rule_pct=None,
    )


_GO_ENSEMBLE_CONFIG = PropSimConfig(
    n_paths=20, seed=777, horizon_months=6, trading_days_per_month=5, path_horizon_trading_days=60
)


def test_verdict_rama_go_ensemble(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {
        "A": _candidate_with_daily_series("A", _LOW_CORR_A),
        "B": _candidate_with_daily_series("B", _LOW_CORR_B),
    }

    result = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        _tiny_target_profile(),
        _GO_ENSEMBLE_CONFIG,
    )

    assert result.verdict is VerdictKind.GO_ENSEMBLE
    assert result.ensemble is not None
    assert result.ensemble.passes_p_gates is True


def test_verdict_candidates_vacio_lanza(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    with pytest.raises(VerdictConfigError):
        run_verdict(
            {},
            _STARTING_BALANCE,
            firm_profile_fixture,
            risk_profile_fixture,
            load_prop_economics_profile(),
            _FAST_ENSEMBLE_CONFIG,
        )


def test_verdict_starting_balance_no_positivo_lanza(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {"A": _go_quality_bundle("A", seed=3)}
    with pytest.raises(VerdictConfigError):
        run_verdict(
            candidates,
            0.0,
            firm_profile_fixture,
            risk_profile_fixture,
            load_prop_economics_profile(),
            _FAST_ENSEMBLE_CONFIG,
        )


def test_verdict_determinismo(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    candidates = {"A": _go_quality_bundle("A", seed=3), "B": _go_quality_bundle("B", seed=4)}

    result1 = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )
    result2 = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert result1.verdict == result2.verdict
    assert result1.winning_candidate_id == result2.winning_candidate_id
    assert result1.t1_dsr == result2.t1_dsr
    assert result1.n_trials_deflactado == result2.n_trials_deflactado


@given(order=st.permutations(["A", "B", "C"]))
@settings(
    max_examples=6, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_verdict_order_invariance(
    order: tuple,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
) -> None:
    """R94/R95bis: permutar el orden de `candidates` no cambia `verdict`/`winning_candidate_id`."""
    base_candidates = {
        "A": _go_quality_bundle("A", seed=3),
        "B": _go_quality_bundle("B", seed=4),
        "C": _bad_bundle("C"),
    }
    reordered = {cid: base_candidates[cid] for cid in order}

    result = run_verdict(
        reordered,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )

    assert result.verdict is VerdictKind.GO
    assert result.winning_candidate_id == "A"  # mayor payout_p25_12m (empate) -> lexicográfico


def test_verdict_monotonia_degradar_dsr_nunca_mejora_passes_g_c_p(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R111: bajar `dsr` de un candidato pasante nunca mejora su `passes_g_c_p` (solo empeora)."""
    bundle = _go_quality_bundle("A", seed=3)
    summary_before = build_candidate_gate_summary(bundle, risk_profile_fixture, _STARTING_BALANCE)
    assert summary_before.passes_g_c_p is True

    degraded_bundle = _bundle(
        candidate_id="A",
        wfa_by_symbol=bundle.wfa_results_by_symbol,
        dsr_pbo_by_symbol={"US500": _dsr_pbo_result(dsr=0.1, pbo=0.1)},
    )
    summary_after = build_candidate_gate_summary(
        degraded_bundle, risk_profile_fixture, _STARTING_BALANCE
    )

    assert summary_after.passes_g_c_p is False


# --- B5: tearsheet + manifest + escritura (R96-R108) ---

_MANIFEST_KWARGS: dict[str, Any] = {
    "config_version": "genesis-validation-j/1",
    "dataset_hash_by_symbol": {"US500": "hash-us500"},
    "firm_profile_hash": "hash-firm",
    "risk_profile_hash": "hash-risk",
    "prop_economics_profile_hash_value": "hash-economics",
    "seeds": {"A": {"mc_seed": 1, "prop_sim_seed": 2}},
    "git_commit": "deadbeef",
}


def _go_result(firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile):
    candidates = {"A": _go_quality_bundle("A", seed=3)}
    return run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        risk_profile_fixture,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
    )


def test_tearsheet_manifest_parity(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    result = _go_result(firm_profile_fixture, risk_profile_fixture)

    tearsheet = render_tearsheet(result)
    manifest_raw = verdict_result_to_manifest_json(result, **_MANIFEST_KWARGS)
    manifest = manifest_json_to_verdict_summary(manifest_raw)

    assert result.verdict.value.upper() in tearsheet
    assert manifest["verdict"] == result.verdict.value
    assert manifest["winning_candidate_id"] == result.winning_candidate_id
    assert manifest["t1_dsr"] == pytest.approx(result.t1_dsr)
    assert f"{result.t1_dsr:.4f}" in tearsheet
    assert "P3" in tearsheet  # advertencia de cota inferior conservadora, siempre presente
    assert "placeholder" in tearsheet.lower()  # economics_confirmed=False por defecto


def test_manifest_roundtrip(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    result = _go_result(firm_profile_fixture, risk_profile_fixture)

    raw = verdict_result_to_manifest_json(result, **_MANIFEST_KWARGS)
    summary = manifest_json_to_verdict_summary(raw)

    assert summary["config_version"] == "genesis-validation-j/1"
    assert summary["n_candidatos_torneo"] == result.n_candidatos_torneo
    assert summary["economics_confirmed"] == result.economics_confirmed
    assert summary["git_commit"] == "deadbeef"


def test_write_verdict_artifacts_ambos_archivos_deterministas(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile, tmp_path
) -> None:
    result = _go_result(firm_profile_fixture, risk_profile_fixture)
    output_dir = tmp_path / "artifacts"

    manifest_path1, tearsheet_path1 = write_verdict_artifacts(
        result, output_dir, **_MANIFEST_KWARGS
    )
    manifest_bytes1 = manifest_path1.read_bytes()
    tearsheet_bytes1 = tearsheet_path1.read_bytes()

    manifest_path2, _tearsheet_path2 = write_verdict_artifacts(
        result, output_dir, **_MANIFEST_KWARGS
    )
    manifest_bytes2 = manifest_path2.read_bytes()

    assert manifest_path1 == output_dir / "manifest.json"
    assert tearsheet_path1 == output_dir / "tearsheet.md"
    assert len(manifest_bytes1) > 0
    assert len(tearsheet_bytes1) > 0
    assert manifest_bytes1 == manifest_bytes2  # determinista byte a byte


def test_purged_cv_summary_incluido_cuando_presente(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    result = _go_result(firm_profile_fixture, risk_profile_fixture)
    purged_cv_result = PurgedCvResult(
        candidate_id="A",
        symbol="US500",
        config=PurgedCvConfig(n_folds=2),
        folds=[
            PurgedFold(
                index=0,
                test_trade_count=3,
                train_trade_count=5,
                purged_trade_count=1,
                test_period=(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 5, tzinfo=UTC)),
            ),
            PurgedFold(
                index=1,
                test_trade_count=3,
                train_trade_count=5,
                purged_trade_count=2,
                test_period=(datetime(2024, 1, 6, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC)),
            ),
        ],
        total_trades=8,
        embargo_days_effective=1,
    )

    raw = verdict_result_to_manifest_json(
        result,
        **_MANIFEST_KWARGS,
        purged_cv_results_by_candidate={"A": {"US500": purged_cv_result}},
    )
    summary = manifest_json_to_verdict_summary(raw)

    assert "purged_cv_summary" in summary
    purged_cv_summary = cast("dict[str, Any]", summary["purged_cv_summary"])
    assert purged_cv_summary["A"]["US500"]["n_folds"] == 2
    assert purged_cv_summary["A"]["US500"]["total_trades"] == 8
    assert purged_cv_summary["A"]["US500"]["purged_trade_count_sum"] == 3


def test_render_tearsheet_no_hace_io(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    result = _go_result(firm_profile_fixture, risk_profile_fixture)
    tearsheet1 = render_tearsheet(result)
    tearsheet2 = render_tearsheet(result)
    assert tearsheet1 == tearsheet2
