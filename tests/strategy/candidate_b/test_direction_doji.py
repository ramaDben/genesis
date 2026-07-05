"""Reset diario + filtro de sesión + dirección de referencia (doji), T5 (R55.1/.3/.4, R56)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import Direction
from tests.strategy.candidate_b.conftest import BASE_TIME, BASE_TRADING_DAY
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit


def _candidate(figure: SymbolFigure, *, n_minutes: int = 15) -> CandidateB:  # ty: ignore[invalid-type-form]
    return CandidateB(
        figure=figure,
        reference_balance=100_000.0,
        n_minutes=n_minutes,
        risk_pct=0.00375,
    )


def test_primera_barra_doji_dentro_de_tolerancia_no_fija_direccion(
    us500_figure: SymbolFigure,
) -> None:
    candidate = _candidate(us500_figure)
    bar = make_annotated_bar(
        BASE_TIME, open_=4500.00, close=4500.003, high=4500.01, low=4499.99, in_session=True
    )
    candidate.on_bar(bar)
    assert candidate._reference_direction is None


def test_primera_barra_close_supera_epsilon_fija_long(us500_figure: SymbolFigure) -> None:
    candidate = _candidate(us500_figure)
    bar = make_annotated_bar(
        BASE_TIME, open_=4500.00, close=4500.01, high=4500.02, low=4499.99, in_session=True
    )
    candidate.on_bar(bar)
    assert candidate._reference_direction is Direction.LONG


def test_barra_fuera_de_sesion_no_muta_estado(us500_figure: SymbolFigure) -> None:
    candidate = _candidate(us500_figure)
    bar = make_annotated_bar(
        BASE_TIME, open_=4500.00, close=4500.50, high=4500.60, low=4499.90, in_session=False
    )
    result = candidate.on_bar(bar)
    assert result == []
    assert candidate._range_high is None
    assert candidate._range_low is None
    assert candidate._reference_direction is None
    assert candidate._minute_index == 0


def test_cambio_de_trading_day_resetea_rango_flag_y_minute_index(
    us500_figure: SymbolFigure,
) -> None:
    candidate = _candidate(us500_figure, n_minutes=1)
    day1_bar = make_annotated_bar(
        BASE_TIME,
        open_=4500.00,
        close=4500.50,
        high=4500.60,
        low=4499.90,
        trading_day=BASE_TRADING_DAY,
        in_session=True,
    )
    candidate.on_bar(day1_bar)
    assert candidate._minute_index == 1

    day2 = BASE_TRADING_DAY + timedelta(days=1)
    day2_time = datetime(day2.year, day2.month, day2.day, 14, 30, tzinfo=UTC)
    day2_bar = make_annotated_bar(
        day2_time,
        open_=4501.00,
        close=4501.10,
        high=4501.20,
        low=4500.90,
        trading_day=day2,
        in_session=True,
    )
    candidate.on_bar(day2_bar)
    assert candidate._current_trading_day == day2
    assert candidate._signal_emitted_today is False


def test_sesion_con_doji_en_primera_barra_no_emite_senal_en_toda_la_sesion(
    us500_figure: SymbolFigure,
) -> None:
    candidate = _candidate(us500_figure, n_minutes=1)
    doji_bar = make_annotated_bar(
        BASE_TIME, open_=4500.00, close=4500.001, high=4500.01, low=4499.99, in_session=True
    )
    candidate.on_bar(doji_bar)

    breakout_bar = make_annotated_bar(
        BASE_TIME + timedelta(minutes=1),
        open_=4500.00,
        close=4600.00,
        high=4600.10,
        low=4499.90,
        in_session=True,
    )
    result = candidate.on_bar(breakout_bar)
    assert result == []
