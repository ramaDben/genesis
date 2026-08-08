"""Tests unitarios de `BarClock` — guard mínimo forward-only (PA-4)."""

from datetime import UTC, datetime

import pytest

from genesis.data.store import AnnotatedBar
from genesis.strategy.clock import BarClock
from genesis.strategy.errors import LookaheadError

pytestmark = pytest.mark.unit


def _bar(timestamp_utc: datetime, *, close: float = 100.0) -> AnnotatedBar:
    return AnnotatedBar(
        timestamp_utc=timestamp_utc,
        open=close,
        high=close,
        low=close,
        close=close,
        tick_volume=10,
        trading_day=timestamp_utc.date(),
        in_session=True,
        session_open_utc=timestamp_utc,
        session_close_utc=timestamp_utc,
    )


_T0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
_T1 = datetime(2024, 1, 1, 0, 1, tzinfo=UTC)


def test_current_time_inicial_es_none() -> None:
    assert BarClock().current_time is None


def test_require_con_current_time_none_lanza_lookahead_error() -> None:
    clock = BarClock()
    with pytest.raises(LookaheadError):
        clock.require(_T0)


def test_advance_actualiza_current_time_a_timestamp_de_la_barra() -> None:
    clock = BarClock()
    clock.advance(_bar(_T0))
    assert clock.current_time == _T0


def test_require_no_lanza_si_timestamp_igual_a_current_time() -> None:
    clock = BarClock()
    clock.advance(_bar(_T0))
    clock.require(_T0)  # no debe lanzar


def test_require_no_lanza_si_timestamp_anterior_a_current_time() -> None:
    clock = BarClock()
    clock.advance(_bar(_T1))
    clock.require(_T0)  # no debe lanzar (t0 < t1)


def test_require_lanza_si_timestamp_posterior_a_current_time_con_ambos_en_mensaje() -> None:
    clock = BarClock()
    clock.advance(_bar(_T0))
    with pytest.raises(LookaheadError) as exc_info:
        clock.require(_T1)
    message = str(exc_info.value)
    assert repr(_T0) in message or str(_T0) in message or _T0.isoformat() in message
    assert repr(_T1) in message or str(_T1) in message or _T1.isoformat() in message


def test_advance_con_retroceso_estricto_lanza_lookahead_error() -> None:
    clock = BarClock()
    clock.advance(_bar(_T1))
    with pytest.raises(LookaheadError):
        clock.advance(_bar(_T0))


def test_advance_repetido_con_mismo_timestamp_no_lanza() -> None:
    clock = BarClock()
    clock.advance(_bar(_T0))
    clock.advance(_bar(_T0))  # re-lectura idempotente, no debe lanzar
    assert clock.current_time == _T0
