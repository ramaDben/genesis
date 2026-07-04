"""Tests unitarios de `genesis.data.store` (lectura normalizada UTC, forward-only)."""

import inspect
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from genesis.data.errors import GenesisDataError
from genesis.data.profile import load_firm_profile
from genesis.data.sessions import session_window
from genesis.data.store import AnnotatedBar, DayBoundaryError, iter_bars

pytestmark = pytest.mark.unit

_MODULE_PATH = Path(__file__).parents[2] / "src" / "genesis" / "data" / "store.py"


def _server_local_frame(timestamps: list[datetime]) -> pd.DataFrame:
    """Frame crudo con timestamps en hora local del servidor (naive, sin tz)."""
    n = len(timestamps)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "tick_volume": [10] * n,
        }
    )


def test_day_boundary_error_is_a_genesis_data_error() -> None:
    assert issubclass(DayBoundaryError, GenesisDataError)


def test_iter_bars_is_a_generator() -> None:
    profile = load_firm_profile()
    frame = _server_local_frame([datetime(2024, 3, 1, 14, 30)])
    result = iter_bars(frame, "US500", profile)
    assert inspect.isgenerator(result)


def test_iter_bars_emits_tz_aware_utc_timestamps() -> None:
    profile = load_firm_profile()
    frame = _server_local_frame([datetime(2024, 3, 1, 14, 30), datetime(2024, 3, 1, 14, 31)])
    bars = list(iter_bars(frame, "US500", profile))
    assert len(bars) == 2
    for bar in bars:
        assert isinstance(bar, AnnotatedBar)
        assert bar.timestamp_utc.tzinfo is not None
        offset = bar.timestamp_utc.utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0  # tz UTC


def test_iter_bars_trading_day_matches_daily_reset_time() -> None:
    profile = load_firm_profile()
    # server_tz por defecto = America/New_York = daily_reset_tz; con reset a medianoche,
    # trading_day coincide con la fecha local del servidor.
    frame = _server_local_frame([datetime(2024, 3, 1, 10, 0)])
    bar = next(iter_bars(frame, "US500", profile))
    assert bar.trading_day == date(2024, 3, 1)


def test_iter_bars_in_session_matches_session_window() -> None:
    profile = load_firm_profile()
    # 10:00 hora de Nueva York cae dentro de la sesión de contado de US500 (9:30-16:00).
    frame = _server_local_frame([datetime(2024, 3, 1, 10, 0), datetime(2024, 3, 1, 20, 0)])
    bars = list(iter_bars(frame, "US500", profile))
    open_utc, close_utc = session_window("US500", date(2024, 3, 1))
    assert bars[0].in_session == (open_utc <= bars[0].timestamp_utc <= close_utc)
    assert bars[0].in_session is True
    assert bars[1].in_session is False


def test_iter_bars_out_of_order_timestamps_raise_day_boundary_error() -> None:
    profile = load_firm_profile()
    # Segunda barra retrocede un día completo respecto a la primera: corte de día
    # inconsistente con daily_reset_time (regresión de trading_day).
    frame = _server_local_frame([datetime(2024, 3, 2, 10, 0), datetime(2024, 3, 1, 10, 0)])
    with pytest.raises(DayBoundaryError, match=r"US500|trading_day|día"):
        list(iter_bars(frame, "US500", profile))


def test_iter_bars_no_forward_only_escape_hatch_in_module() -> None:
    """R32/R33: sin __getitem__/seek/peek/LookaheadError en store.py."""
    source = _MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in ("__getitem__", "def seek", "def peek", "LookaheadError"):
        assert forbidden not in source


def test_iter_bars_monotonic_trading_day_across_full_day() -> None:
    profile = load_firm_profile()
    timestamps = [
        datetime(2024, 3, 1, 9, 30),
        datetime(2024, 3, 1, 12, 0),
        datetime(2024, 3, 1, 23, 59),
        datetime(2024, 3, 2, 0, 1),
    ]
    frame = _server_local_frame(timestamps)
    bars = list(iter_bars(frame, "US500", profile))
    trading_days = [bar.trading_day for bar in bars]
    assert trading_days == sorted(trading_days)
    assert trading_days[-1] == date(2024, 3, 2)
