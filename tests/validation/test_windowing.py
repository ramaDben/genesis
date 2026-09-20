"""Tests de `_windowing.py`: geometría de ventanas reutilizable (ADR-I2, R25)."""

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation._windowing import (
    iter_is_oos_bounds,
    plan_trading_days,
    slice_frame_by_day_range,
    slice_frame_by_days,
)
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import WfaWindowConfig

pytestmark = pytest.mark.unit


def test_plan_trading_days_e_iter_is_oos_bounds_reproducen_geometria_de_wfa(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R25: misma geometría de ventanas IS/OOS que `run_wfa`, sin importar `wfa._*`."""
    result = run_wfa(
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
        seed=1,
    )
    assert result.n_windows >= 1

    days, _row_span = plan_trading_days(short_wfa_frame, "US500", firm_profile_fixture)
    bounds = list(iter_is_oos_bounds(len(days), reduced_window_config))
    assert len(bounds) == result.n_windows

    for (k, is_start, is_end, oos_end), window in zip(bounds, result.windows, strict=True):
        assert k == window.index
        is_range = (days[is_start], days[is_end - 1])
        oos_range = (days[is_end], days[oos_end - 1])
        assert is_range == window.is_trading_day_range
        assert oos_range == window.oos_trading_day_range


def test_slice_frame_by_days_reproduce_span_posicional(
    firm_profile_fixture: FirmProfile,
    short_wfa_frame: pd.DataFrame,
) -> None:
    days, row_span = plan_trading_days(short_wfa_frame, "US500", firm_profile_fixture)
    sliced = slice_frame_by_days(short_wfa_frame, row_span, days[:2])
    first_position = row_span[days[0]][0]
    last_position = row_span[days[1]][1]
    expected = short_wfa_frame.iloc[first_position : last_position + 1]
    pd.testing.assert_frame_equal(sliced, expected)


def test_slice_frame_by_day_range_equivale_a_plan_mas_slice(
    firm_profile_fixture: FirmProfile,
    short_wfa_frame: pd.DataFrame,
) -> None:
    days, row_span = plan_trading_days(short_wfa_frame, "US500", firm_profile_fixture)
    day_range = (days[1], days[3])
    expected = slice_frame_by_days(short_wfa_frame, row_span, days[1:4])

    sliced = slice_frame_by_day_range(short_wfa_frame, "US500", firm_profile_fixture, day_range)
    pd.testing.assert_frame_equal(sliced, expected)


def test_windowing_no_importa_simbolos_privados_de_wfa() -> None:
    """R25: `_windowing.py` no importa ningún símbolo con prefijo `_` de `wfa.py`."""
    import genesis.validation._windowing as windowing_module

    with open(windowing_module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "from genesis.validation.wfa import" not in content
    assert "from .wfa import" not in content
