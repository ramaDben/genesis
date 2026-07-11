"""`LiquidityLevel` + `LiquidityMap` — agrupación EQH/EQL y mitigación (T3.4, R102)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.strategy.candidate_a.smc.fractals import Swing, SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityMap
from genesis.strategy.candidate_a.smc.timeframe import Timeframe, to_m1_aggregated_bar
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)
_EQ_TOLERANCE_ATR = 0.15
_ATR = 1.0  # tolerancia efectiva: 0.15


def _swing(direction: SwingDirection, price: float, index: int) -> Swing:
    ts = _BASE + timedelta(minutes=index)
    return Swing(
        timeframe=Timeframe.M1,
        direction=direction,
        price=price,
        pivot_time=ts,
        confirmed_time=ts + timedelta(minutes=2),
    )


def test_dos_swings_dentro_de_tolerancia_forman_un_nivel() -> None:
    liquidity = LiquidityMap(_EQ_TOLERANCE_ATR)
    swing_1 = _swing(SwingDirection.HIGH, 100.0, 0)
    swing_2 = _swing(SwingDirection.HIGH, 100.10, 10)  # diff=0.10 <= 0.15

    liquidity.add_swing(swing_1, _ATR)
    liquidity.add_swing(swing_2, _ATR)

    levels = liquidity.active_levels(Timeframe.M1)
    assert len(levels) == 1
    level = levels[0]
    assert level.price == 100.10  # máximo del grupo (EQH)
    assert len(level.member_swings) == 2


def test_dos_swings_fuera_de_tolerancia_no_se_agrupan() -> None:
    liquidity = LiquidityMap(_EQ_TOLERANCE_ATR)
    swing_1 = _swing(SwingDirection.HIGH, 100.0, 0)
    swing_2 = _swing(SwingDirection.HIGH, 101.0, 10)  # diff=1.0 > 0.15

    liquidity.add_swing(swing_1, _ATR)
    liquidity.add_swing(swing_2, _ATR)

    levels = liquidity.active_levels(Timeframe.M1)
    assert len(levels) == 2


def test_eql_precio_del_nivel_es_el_minimo_del_grupo() -> None:
    liquidity = LiquidityMap(_EQ_TOLERANCE_ATR)
    swing_1 = _swing(SwingDirection.LOW, 100.0, 0)
    swing_2 = _swing(SwingDirection.LOW, 99.95, 10)

    liquidity.add_swing(swing_1, _ATR)
    liquidity.add_swing(swing_2, _ATR)

    levels = liquidity.active_levels(Timeframe.M1)
    assert len(levels) == 1
    assert levels[0].price == 99.95


def test_mitigacion_por_cierre_mas_alla_del_nivel() -> None:
    liquidity = LiquidityMap(_EQ_TOLERANCE_ATR)
    swing = _swing(SwingDirection.HIGH, 100.0, 0)
    liquidity.add_swing(swing, _ATR)
    assert len(liquidity.active_levels(Timeframe.M1)) == 1

    bar_within = to_m1_aggregated_bar(
        make_annotated_bar(_BASE + timedelta(minutes=5), close=99.5, high=99.9, low=99.0)
    )
    liquidity.apply_close(bar_within)
    assert len(liquidity.active_levels(Timeframe.M1)) == 1

    bar_beyond = to_m1_aggregated_bar(
        make_annotated_bar(_BASE + timedelta(minutes=6), close=100.5, high=100.6, low=100.0)
    )
    liquidity.apply_close(bar_beyond)
    assert liquidity.active_levels(Timeframe.M1) == []


def test_niveles_de_tf_distinto_no_se_agrupan_ni_se_mitigan_entre_si() -> None:
    liquidity = LiquidityMap(_EQ_TOLERANCE_ATR)
    swing_m1 = _swing(SwingDirection.HIGH, 100.0, 0)
    swing_m15 = Swing(
        timeframe=Timeframe.M15,
        direction=SwingDirection.HIGH,
        price=100.05,
        pivot_time=_BASE,
        confirmed_time=_BASE + timedelta(minutes=30),
    )
    liquidity.add_swing(swing_m1, _ATR)
    liquidity.add_swing(swing_m15, _ATR)

    assert len(liquidity.active_levels(Timeframe.M1)) == 1
    assert len(liquidity.active_levels(Timeframe.M15)) == 1
