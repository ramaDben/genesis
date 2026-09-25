"""Test de propiedad: determinismo total del WFA (R54)."""

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
from genesis.validation.wfa import WfaResult, run_wfa
from genesis.validation.window_config import WfaWindowConfig

pytestmark = pytest.mark.unit


def _entries_as_tuples(ledger) -> list[tuple]:  # type: ignore[no-untyped-def]
    """Representación comparable (bit-idéntica) de las entradas de un `Ledger`."""
    return [(entry.provenance, entry.payload) for entry in ledger.entries]


@settings(
    max_examples=3, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_wfa_deterministic(
    seed: int,
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R54: mismo seed+frame+config -> WfaResult bit-idéntico entre dos invocaciones."""

    def _run() -> WfaResult:
        return run_wfa(
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
            seed=seed,
        )

    result1 = _run()
    result2 = _run()

    assert result1.wfe == result2.wfe
    assert result1.n_windows == result2.n_windows
    for window1, window2 in zip(result1.windows, result2.windows, strict=True):
        assert window1.winning_combo == window2.winning_combo
        assert window1.winning_signal_config == window2.winning_signal_config
        assert window1.dsr_is == window2.dsr_is
        assert window1.window_identity_hash == window2.window_identity_hash

    assert _entries_as_tuples(result1.oos_ledger_cosido) == _entries_as_tuples(
        result2.oos_ledger_cosido
    )
