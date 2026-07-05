"""Tests de `SimulationClock` — compone `BarClock`, no hereda (R5–R9)."""

from datetime import UTC, datetime

import pytest

from genesis.backtest.clock import SimulationClock
from genesis.strategy.clock import BarClock
from genesis.strategy.errors import LookaheadError
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_T0 = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
_T1 = datetime(2024, 1, 2, 14, 31, tzinfo=UTC)


def test_simulation_clock_no_hereda_de_bar_clock() -> None:
    assert not issubclass(SimulationClock, BarClock)


def test_advance_actualiza_trading_day() -> None:
    clock = SimulationClock()
    bar_t0 = make_annotated_bar(_T0)
    clock.advance(bar_t0)
    assert clock.trading_day == bar_t0.trading_day
    assert clock.current_time == _T0


def test_advance_con_barra_posterior_no_lanza() -> None:
    clock = SimulationClock()
    clock.advance(make_annotated_bar(_T0))
    bar_t1 = make_annotated_bar(_T1)
    clock.advance(bar_t1)
    assert clock.trading_day == bar_t1.trading_day


def test_advance_con_retroceso_lanza_lookahead_error() -> None:
    clock = SimulationClock()
    clock.advance(make_annotated_bar(_T1))
    with pytest.raises(LookaheadError):
        clock.advance(make_annotated_bar(_T0))


def test_require_con_timestamp_futuro_lanza_lookahead_error() -> None:
    clock = SimulationClock()
    clock.advance(make_annotated_bar(_T0))
    with pytest.raises(LookaheadError):
        clock.require(_T1)


def test_previous_day_close_balance_es_none_por_defecto_y_mutable() -> None:
    clock = SimulationClock()
    assert clock.previous_day_close_balance is None
    clock.previous_day_close_balance = 100_000.0
    assert clock.previous_day_close_balance == 100_000.0
