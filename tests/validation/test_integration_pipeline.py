"""Integración del pipeline completo: `iter_bars` -> `run_wfa` -> `monte_carlo_*` (R58).

Patrón `tests/backtest/test_integration_pipeline.py`: ejercita el flujo real de
extremo a extremo sobre un fixture sintético pequeño, sin mocks de las capas
internas, con `WfaWindowConfig` reducido — corre en segundos.
"""

import math

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.house_rule import HouseRule
from genesis.data.profile import FirmProfile
from genesis.data.store import RawParquetStore, iter_bars
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.montecarlo import monte_carlo_portfolio, monte_carlo_symbol
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import WfaWindowConfig

pytestmark = pytest.mark.integration


def test_pipeline_completo_produce_resultados_no_vacios_y_metricas_finitas(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    house_rule_fixture: HouseRule,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R58: `iter_bars` -> `run_wfa` -> `monte_carlo_symbol` -> `monte_carlo_portfolio`."""
    bars = list(iter_bars(short_wfa_frame, "US500", firm_profile_fixture))
    assert len(bars) > 0

    wfa_result = run_wfa(
        "B",
        "US500",
        short_wfa_frame,
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
        window_config=reduced_window_config,
        seed=7,
    )
    assert wfa_result.n_windows >= 1
    assert len(wfa_result.oos_ledger_cosido.entries) > 0
    assert math.isfinite(wfa_result.wfe)

    symbol_result = monte_carlo_symbol(
        wfa_result.oos_ledger_cosido, house_rule_fixture, n_paths=100, seed=11
    )
    assert len(symbol_result.reshuffle.max_drawdown_per_path) == 100
    assert len(symbol_result.block_bootstrap.max_drawdown_per_path) == 100
    assert math.isfinite(symbol_result.reshuffle.max_drawdown_p95)
    assert math.isfinite(symbol_result.block_bootstrap.breach_probability)

    portfolio_result = monte_carlo_portfolio(
        {"US500": wfa_result.oos_ledger_cosido}, house_rule_fixture, n_paths=100, seed=13
    )
    assert len(portfolio_result.block_bootstrap.max_drawdown_per_path) == 100
    assert math.isfinite(portfolio_result.block_bootstrap.max_drawdown_p95)
    assert math.isfinite(portfolio_result.block_bootstrap.breach_probability)
