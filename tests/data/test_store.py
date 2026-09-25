"""Tests unitarios de `genesis.data.store` (lectura normalizada UTC, forward-only)."""

import inspect
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from genesis.data.errors import GenesisDataError
from genesis.data.profile import load_firm_profile
from genesis.data.sessions import session_window
from genesis.data.store import (
    AnnotatedBar,
    ChunkWindow,
    DayBoundaryError,
    Granularity,
    iter_bars,
    plan_chunks,
)

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


def test_iter_bars_resuelve_la_ventana_de_sesion_una_vez_por_dia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R14 del Change #46: `session_window` se consulta por día, nunca por barra.

    El bench ya lo confirmó sobre datos reales (464.974 → 173 llamadas), pero una
    medición no impide una regresión: quien reintroduzca la llamada por barra vería la
    suite en verde. Este test no.
    """
    profile = load_firm_profile()
    frame = _server_local_frame(
        [
            datetime(2024, 3, 1, 10, 0),
            datetime(2024, 3, 1, 11, 0),
            datetime(2024, 3, 1, 12, 0),
            datetime(2024, 3, 4, 10, 0),
            datetime(2024, 3, 4, 11, 0),
        ]
    )

    dias_consultados: list[date] = []
    original = session_window

    def espiar(symbol: str, session_date: date) -> tuple[datetime, datetime]:
        dias_consultados.append(session_date)
        return original(symbol, session_date)

    monkeypatch.setattr("genesis.data.store.session_window", espiar)

    bars = list(iter_bars(frame, "US500", profile))

    assert len(bars) == 5
    assert len(dias_consultados) == len(set(dias_consultados)), (
        "cada trading_day debe consultarse una sola vez"
    )
    assert len(dias_consultados) == len({bar.trading_day for bar in bars})


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


def test_plan_chunks_m1_splits_by_calendar_month() -> None:
    start = datetime(2024, 1, 15, tzinfo=UTC)
    end = datetime(2024, 3, 10, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert len(chunks) == 3
    assert chunks[0].start == start
    assert chunks[-1].end == end


def test_plan_chunks_ticks_splits_by_day() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.TICK)
    assert len(chunks) == 3


def test_plan_chunks_covers_range_without_gaps_or_overlaps() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 6, 30, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert chunks[0].start == start
    assert chunks[-1].end == end
    for prev, curr in pairwise(chunks):
        assert prev.end == curr.start


@given(
    start_offset_days=st.integers(min_value=0, max_value=400),
    span_days=st.integers(min_value=1, max_value=400),
)
def test_plan_chunks_property_covers_exact_range(start_offset_days: int, span_days: int) -> None:
    base = datetime(2023, 1, 1, tzinfo=UTC)
    start = base + timedelta(days=start_offset_days)
    end = start + timedelta(days=span_days)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert chunks[0].start == start
    assert chunks[-1].end == end
    for prev, curr in pairwise(chunks):
        assert prev.end == curr.start


def test_plan_chunks_start_equals_end_returns_single_empty_window() -> None:
    moment = datetime(2024, 5, 1, tzinfo=UTC)
    chunks = plan_chunks(moment, moment, Granularity.M1)
    assert chunks == [ChunkWindow(start=moment, end=moment)]
