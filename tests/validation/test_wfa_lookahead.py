"""Test de propiedad anti-lookahead a nivel de ventana WFA (R36, R37, R56)."""

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.profile import FirmProfile
from genesis.data.store import RawParquetStore
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import WfaWindowConfig

pytestmark = pytest.mark.unit


def _run_window0(
    frame: pd.DataFrame,
    *,
    firm_profile: FirmProfile,
    risk_profile: ExitGeometry,
    symbol_figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    dataset_store: RawParquetStore,
    window_config: WfaWindowConfig,
):
    result = run_wfa(
        "B",
        "US500",
        frame,
        firm_profile,
        risk_profile,
        symbol_figure,
        funnel_config,
        costs_config,
        [],
        dataset_store,
        None,
        100_000.0,
        window_config=window_config,
        seed=1,
    )
    return result.windows[0]


@settings(
    max_examples=5, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    mutate_own_oos=st.booleans(),
    price_shift=st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_wfa_anti_lookahead(
    mutate_own_oos: bool,
    price_shift: float,
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R36/R37: mutar barras posteriores al corte IS/OOS de la ventana 0 no cambia su selección.

    `reduced_window_config` (is=4, oos=2, step=2) sobre `short_wfa_frame` (10 días)
    produce 3 ventanas; la ventana 0 cubre IS=`days[0:4)`, OOS=`days[4:6)`. Este test
    muta barras del propio tramo OOS de la ventana 0 (`mutate_own_oos=True`) o de una
    ventana posterior (`k'>0`, `mutate_own_oos=False`) — en ambos casos, con
    `timestamp` posterior al corte IS/OOS de la ventana 0.
    """
    baseline_window0 = _run_window0(
        short_wfa_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=exit_geometry_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )

    mutated_frame = short_wfa_frame.copy(deep=True)
    # `reduced_window_config` fija OOS de la ventana 0 en days[4:6) del pre-pase de
    # planificación; usamos una máscara de fecha de calendario para no acoplarnos al
    # detalle interno de `row_span` (misma semántica que "posterior al corte de k").
    all_days = sorted(mutated_frame["timestamp"].dt.date.unique())
    cutoff_day = all_days[4]  # primer día del tramo OOS de la ventana 0 (is_window=4)
    # target_day: dentro del propio OOS de la ventana 0, o de la ventana k'=1 (posterior).
    target_day = all_days[4] if mutate_own_oos else all_days[6]
    assert target_day >= cutoff_day

    mask = mutated_frame["timestamp"].dt.date == target_day
    mutated_frame.loc[mask, ["open", "high", "low", "close"]] += price_shift

    mutated_window0 = _run_window0(
        mutated_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=exit_geometry_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )

    assert mutated_window0.winning_combo == baseline_window0.winning_combo
    assert mutated_window0.winning_signal_config == baseline_window0.winning_signal_config
    assert mutated_window0.dsr_is == baseline_window0.dsr_is
