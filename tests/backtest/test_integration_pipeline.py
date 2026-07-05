"""Integración del pipeline completo: `iter_bars` → `Simulator` → `ledger` → `metrics` (R55).

Patrón `tests/data/test_integration_export_quality.py`: ejercita el flujo real de
extremo a extremo sobre el dataset de muestra, sin mocks de las capas internas.
"""

import math

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.metrics import (
    max_concurrent_exposure,
    max_drawdown,
    min_distance_to_daily_limit,
    profit_factor,
    rejection_rate_by_reason,
    sharpe_pointwise,
    win_rate,
    worst_daily_floating_excursion,
)
from genesis.backtest.risk_profile import RiskProfile
from genesis.backtest.simulator import Simulator
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate

pytestmark = pytest.mark.integration

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0)


def test_pipeline_completo_produce_ledger_no_vacio_y_metricas_finitas(
    sample_m1_frame: pd.DataFrame,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R55: pipeline `iter_bars` → `Simulator.run` → `metrics` en segundos, sin mocks."""
    candidate = FakeRiskCandidate(entry_threshold=101.0, stop_loss=95.0, take_profit=105.0)
    simulator = Simulator(
        candidate,
        symbol="US500",
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        figure=symbol_figure_fixture,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config_fixture,
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
    )

    ledger = simulator.run(sample_m1_frame)

    assert len(ledger.entries) > 0

    finite_metrics = [
        profit_factor(ledger),
        sharpe_pointwise(ledger),
        max_drawdown(ledger),
        win_rate(ledger),
        worst_daily_floating_excursion(ledger),
        min_distance_to_daily_limit(ledger, firm_profile_fixture),
    ]
    for value in finite_metrics:
        assert math.isfinite(value), f"métrica no finita: {value!r}"

    assert isinstance(max_concurrent_exposure(ledger), int)
    for rate in rejection_rate_by_reason(ledger).values():
        assert math.isfinite(rate)
