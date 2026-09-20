"""Test de volumen realista de `run_verdict` con 3+ candidatos y ensemble (R113).

Marcado `pytest.mark.slow`: ejerce `run_verdict` con `n_paths` más realista
(varios cientos) y 3 candidatos sintéticos con series diarias diversas
(2 de baja correlación entre sí + 1 claramente débil), separado de la suite
rápida por defecto.
"""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from genesis.backtest.ledger import ExhaustionPolicy, FillRecord, Ledger, RunProvenance
from genesis.data.profile import FirmProfile
from genesis.strategy.contract import Direction
from genesis.validation import (
    CandidateValidationBundle,
    VerdictKind,
    load_prop_economics_profile,
    run_prop_sim,
    run_verdict,
)
from genesis.validation.dsr_pbo import CscvResult, DsrPboResult
from genesis.validation.montecarlo import McPathsResult, McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import PropSimConfig
from genesis.validation.sensitivity import CostStressOutcome, PerturbationOutcome, SensitivityResult
from genesis.validation.wfa import WfaResult

pytestmark = [pytest.mark.slow, pytest.mark.timeout(120)]

_REALISTIC_CONFIG = PropSimConfig(
    n_paths=500,
    seed=2024,
    horizon_months=6,
    trading_days_per_month=10,
    path_horizon_trading_days=200,
)
_STARTING_BALANCE = 100_000.0
_TRADES_PER_DAY = 100
_N_DAYS = 30


def _daily_ledger(daily_values: list, *, symbol: str = "US500") -> Ledger:
    """Ledger con `_TRADES_PER_DAY` trades/día (G1 trivial) sumando `daily_values[día]`."""
    provenance = RunProvenance(
        candidate_id="slow",
        config_version="genesis-backtest/1",
        dataset_hash="slow-hash",
        firm_profile_hash="slow-hash",
        exit_geometry_hash="slow-hash",
        house_rule_hash="slow-hash",
        exhaustion_policy=ExhaustionPolicy.RECORD_AND_CONTINUE,
    )
    base_day = date(2024, 1, 1)
    ledger = Ledger(provenance=provenance, entries=[])
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
                    candidate_id="slow",
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
                    candidate_id="slow",
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


def _synthetic_daily_series(seed: int, *, mean: float = 60.0, scale: float = 100.0) -> list:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, scale, size=_N_DAYS).tolist()


def _synthetic_dsr_pbo_result(symbol: str) -> DsrPboResult:
    return DsrPboResult(
        candidate_id="slow",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        dsr=0.98,
        n_trials_signal_total=45,
        pbo=0.1,
        cscv=CscvResult(pbo=0.1, n_splits=4, n_combinations=6, logit_by_combination=[0.1] * 6),
    )


def _synthetic_sensitivity_result(symbol: str) -> SensitivityResult:
    return SensitivityResult(
        candidate_id="slow",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        baseline_profit_factor=1.4,
        perturbations=[
            PerturbationOutcome(
                axis="n_minutes",
                direction=1,
                perturbed_value=10.0,
                profit_factor=1.3,
                relative_drop=0.1,
                is_cliff=False,
            )
        ],
        cost_stress=[
            CostStressOutcome(multiplier=1.5, profit_factor=1.5),
            CostStressOutcome(multiplier=2.0, profit_factor=1.4),
        ],
        has_cliff=False,
    )


def _synthetic_mc_paths_result() -> McPathsResult:
    return McPathsResult(
        max_drawdown_per_path=np.array([1_000.0]),
        breach_per_path=np.array([False]),
        max_drawdown_p95=1_000.0,
        breach_probability=0.01,
        seed=1,
        n_paths=1,
        block_size=5,
    )


def _build_candidate_bundle(
    candidate_id: str,
    daily_values: list,
    firm_profile: FirmProfile,
) -> CandidateValidationBundle:
    ledger = _daily_ledger(daily_values)
    oos_ledgers_by_symbol = {"US500": ledger}
    wfa_result = WfaResult(
        candidate_id=candidate_id,
        symbol="US500",
        config_version="genesis-validation/1",
        windows=[],
        oos_ledger_cosido=ledger,
        wfe=0.6,
        n_windows=5,
        n_trials_signal_total=45,
        n_trials_execution_total=135,
        seed=1,
    )
    prop_sim_result = run_prop_sim(
        oos_ledgers_by_symbol,
        _STARTING_BALANCE,
        firm_profile,
        load_prop_economics_profile(),
        _REALISTIC_CONFIG,
        candidate_id,
    )
    return CandidateValidationBundle(
        candidate_id=candidate_id,
        wfa_results_by_symbol={"US500": wfa_result},
        dsr_pbo_results_by_symbol={"US500": _synthetic_dsr_pbo_result("US500")},
        sensitivity_results_by_symbol={"US500": _synthetic_sensitivity_result("US500")},
        mc_symbol_results_by_symbol={
            "US500": McSymbolResult(
                symbol="US500",
                provenance=ledger.provenance,
                reshuffle=_synthetic_mc_paths_result(),
                block_bootstrap=_synthetic_mc_paths_result(),
            )
        },
        mc_portfolio_result=McPortfolioResult(
            provenance_by_symbol={"US500": ledger.provenance},
            block_bootstrap=_synthetic_mc_paths_result(),
        ),
        prop_sim_result=prop_sim_result,
    )


def test_run_verdict_volumen_realista_3_candidatos_con_ensemble(
    firm_profile_fixture: FirmProfile,
) -> None:
    candidates = {
        "A": _build_candidate_bundle("A", _synthetic_daily_series(1), firm_profile_fixture),
        "B": _build_candidate_bundle("B", _synthetic_daily_series(2), firm_profile_fixture),
        "C": _build_candidate_bundle(
            "C",
            _synthetic_daily_series(3, mean=-40.0),
            firm_profile_fixture,
        ),
    }

    result = run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile_fixture,
        load_prop_economics_profile(),
        _REALISTIC_CONFIG,
    )

    assert result.n_candidatos_torneo == 3
    assert result.verdict in set(VerdictKind)
    assert len(result.candidate_summaries) == 3
