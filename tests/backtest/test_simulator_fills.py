"""Tabla golden del motor de fills intrabar `_resolve_fill`/`_resolve_entry_fill` (R32–R36)."""

from datetime import UTC, datetime

import pytest

from genesis.backtest.simulator import OpenPosition, _resolve_fill
from genesis.backtest.ticks import TickRow
from genesis.strategy.contract import Direction
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_ENTRY_TIME = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
_BAR_TIME = datetime(2024, 1, 2, 14, 31, tzinfo=UTC)


def _position(
    *,
    direction: Direction = Direction.LONG,
    entry_price: float = 100.0,
    stop_loss: float = 90.0,
    take_profit: float = 110.0,
) -> OpenPosition:
    return OpenPosition(
        candidate_id="B",
        symbol="US500",
        direction=direction,
        entry_time=_ENTRY_TIME,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        sizing_hint=0.1,
    )


def test_caso_1_sl_primero_sin_gap_long() -> None:
    """R32: SL y TP ambos dentro del rango de la vela → gana SL (peor caso)."""
    position = _position(stop_loss=90.0, take_profit=110.0)
    bar = make_annotated_bar(_BAR_TIME, open_=100.0, high=115.0, low=85.0, close=95.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(90.0)
    assert fill.timestamp_utc == _BAR_TIME


def test_caso_2_solo_tp_en_rango_sin_gap_long() -> None:
    """R32 (regla 4): solo TP dentro de `[low, high]` → fill al nivel de TP."""
    position = _position(stop_loss=50.0, take_profit=110.0)
    bar = make_annotated_bar(_BAR_TIME, open_=100.0, high=112.0, low=98.0, close=105.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(110.0)


def test_caso_3_gap_desfavorable_fill_a_bar_open_long() -> None:
    """R33: `bar.open` ya está más allá del SL en dirección adversa → fill a `bar.open`."""
    position = _position(stop_loss=90.0, take_profit=110.0)
    bar = make_annotated_bar(_BAR_TIME, open_=85.0, high=88.0, low=80.0, close=82.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(85.0)


def test_caso_4_gap_favorable_fill_a_take_profit_long() -> None:
    """R34: `bar.open` ya está más allá del TP en dirección favorable → cap conservador a TP."""
    position = _position(stop_loss=90.0, take_profit=110.0)
    bar = make_annotated_bar(_BAR_TIME, open_=115.0, high=120.0, low=113.0, close=118.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(110.0)


def test_caso_5_fill_por_tick_real_dentro_de_la_ventana() -> None:
    """R35: con cobertura de ticks, el primer tick que toca SL/TP determina el fill."""
    position = _position(stop_loss=90.0, take_profit=110.0)
    bar = make_annotated_bar(_BAR_TIME, open_=100.0, high=112.0, low=88.0, close=105.0)
    ticks = [
        TickRow(
            timestamp_utc=datetime(2024, 1, 2, 14, 30, 20, tzinfo=UTC),
            bid=99.0,
            ask=99.2,
            last=99.0,
        ),
        TickRow(
            timestamp_utc=datetime(2024, 1, 2, 14, 30, 40, tzinfo=UTC),
            bid=110.0,
            ask=110.2,
            last=110.0,
        ),
        TickRow(
            timestamp_utc=datetime(2024, 1, 2, 14, 30, 50, tzinfo=UTC),
            bid=89.0,
            ask=89.2,
            last=89.0,
        ),
    ]
    fill = _resolve_fill(position, bar, ticks, coverage=True)
    assert fill is not None
    assert fill.price == pytest.approx(110.0)
    assert fill.timestamp_utc == datetime(2024, 1, 2, 14, 30, 40, tzinfo=UTC)


def test_caso_6_ninguno_dentro_de_rango_no_hay_fill() -> None:
    """Regla 4c: ni SL ni TP dentro de `[low, high]` y sin gap → no hay fill (`None`)."""
    position = _position(stop_loss=50.0, take_profit=200.0)
    bar = make_annotated_bar(_BAR_TIME, open_=100.0, high=105.0, low=95.0, close=101.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is None


def test_caso_7_vela_unica_entrada_y_salida_en_el_mismo_bar() -> None:
    """Pregunta abierta §9: posición con `entry_price=bar.open` cerrada en el mismo bar."""
    bar = make_annotated_bar(_BAR_TIME, open_=100.0, high=101.0, low=89.0, close=95.0)
    position = _position(entry_price=bar.open, stop_loss=90.0, take_profit=110.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(90.0)


def test_caso_8_gap_desfavorable_short() -> None:
    """R33 en dirección SHORT: `bar.open` más allá del SL adverso → fill a `bar.open`."""
    position = _position(direction=Direction.SHORT, stop_loss=110.0, take_profit=90.0)
    bar = make_annotated_bar(_BAR_TIME, open_=115.0, high=118.0, low=112.0, close=116.0)
    fill = _resolve_fill(position, bar, [], coverage=False)
    assert fill is not None
    assert fill.price == pytest.approx(115.0)
