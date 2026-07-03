"""Tests unitarios + property de `genesis.data.sessions` (tabla de sesiones, DST)."""

from datetime import UTC, date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from genesis.data.sessions import SESSIONS, session_window

pytestmark = pytest.mark.unit


def test_sessions_table_has_the_four_normative_rows() -> None:
    assert set(SESSIONS.keys()) == {"US500", "NAS100", "US30", "GER40"}


def test_sessions_table_market_timezones() -> None:
    assert SESSIONS["US500"].market_tz == "America/New_York"
    assert SESSIONS["NAS100"].market_tz == "America/New_York"
    assert SESSIONS["US30"].market_tz == "America/New_York"
    assert SESSIONS["GER40"].market_tz == "Europe/Berlin"


def test_session_window_unsupported_symbol_raises_key_error_with_context() -> None:
    with pytest.raises(KeyError) as exc_info:
        session_window("XAUUSD", date(2024, 3, 15))
    message = str(exc_info.value)
    assert "XAUUSD" in message
    for valid_symbol in ("US500", "NAS100", "US30", "GER40"):
        assert valid_symbol in message


def test_session_window_us500_edt() -> None:
    # 2024-07-15 está en horario de verano de EE. UU. (EDT, UTC-4).
    open_utc, close_utc = session_window("US500", date(2024, 7, 15))
    assert open_utc == datetime(2024, 7, 15, 13, 30, tzinfo=UTC)
    assert close_utc == datetime(2024, 7, 15, 20, 0, tzinfo=UTC)


def test_session_window_us500_est() -> None:
    # 2024-01-15 está en horario estándar de EE. UU. (EST, UTC-5).
    open_utc, close_utc = session_window("US500", date(2024, 1, 15))
    assert open_utc == datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
    assert close_utc == datetime(2024, 1, 15, 21, 0, tzinfo=UTC)


def test_session_window_ger40_cest() -> None:
    # 2024-07-15 está en horario de verano de Europa (CEST, UTC+2).
    open_utc, close_utc = session_window("GER40", date(2024, 7, 15))
    assert open_utc == datetime(2024, 7, 15, 7, 0, tzinfo=UTC)
    assert close_utc == datetime(2024, 7, 15, 15, 30, tzinfo=UTC)


def test_session_window_ger40_cet() -> None:
    # 2024-01-15 está en horario estándar de Europa (CET, UTC+1).
    open_utc, close_utc = session_window("GER40", date(2024, 1, 15))
    assert open_utc == datetime(2024, 1, 15, 8, 0, tzinfo=UTC)
    assert close_utc == datetime(2024, 1, 15, 16, 30, tzinfo=UTC)


def test_session_window_nas100_us30_mirror_us500() -> None:
    d = date(2024, 3, 20)
    assert session_window("NAS100", d) == session_window("US500", d)
    assert session_window("US30", d) == session_window("US500", d)


@given(
    day_ordinal=st.integers(
        min_value=date(2000, 1, 1).toordinal(), max_value=date(2035, 12, 31).toordinal()
    )
)
def test_session_window_is_deterministic_for_same_symbol_and_date(day_ordinal: int) -> None:
    session_date = date.fromordinal(day_ordinal)
    first = session_window("US500", session_date)
    second = session_window("US500", session_date)
    assert first == second
