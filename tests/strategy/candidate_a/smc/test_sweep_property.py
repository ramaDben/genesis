"""Property test de la FSM de sweep: ninguna transición fuera de los 5 estados (R103, R123)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.strategy.candidate_a.smc.fractals import Swing, SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityLevel
from genesis.strategy.candidate_a.smc.sweep import SweepState, SweepTracker, transition_sweep
from genesis.strategy.candidate_a.smc.timeframe import Timeframe
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)
_ATR_M1 = 1.0


@dataclass(frozen=True, slots=True)
class _Config:
    sweep_tolerance_atr: float
    sweep_window_k: int
    sweep_validity_m: int


def _level(direction: SwingDirection) -> LiquidityLevel:
    swing = Swing(
        timeframe=Timeframe.M1,
        direction=direction,
        price=100.0,
        pivot_time=_BASE,
        confirmed_time=_BASE,
    )
    return LiquidityLevel(
        level_id=1,
        timeframe=Timeframe.M1,
        direction=direction,
        price=100.0,
        member_swings=(swing,),
        mitigated=False,
    )


@given(
    direction=st.sampled_from([SwingDirection.HIGH, SwingDirection.LOW]),
    closes=st.lists(
        st.floats(min_value=95.0, max_value=105.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ),
    sweep_window_k=st.integers(min_value=1, max_value=10),
    sweep_validity_m=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=300, deadline=None)
def test_toda_transicion_produce_uno_de_los_5_estados(
    direction: SwingDirection,
    closes: list[float],
    sweep_window_k: int,
    sweep_validity_m: int,
) -> None:
    config = _Config(
        sweep_tolerance_atr=0.05, sweep_window_k=sweep_window_k, sweep_validity_m=sweep_validity_m
    )
    level = _level(direction)
    tracker = SweepTracker(
        level=level, state=SweepState.ARMADO, touch_time=None, swept_time=None, extreme_price=None
    )
    was_mitigado = False
    for index, close in enumerate(closes):
        bar = make_annotated_bar(
            _BASE + timedelta(minutes=index),
            close=close,
            high=close + 1.0,
            low=close - 1.0,
        )
        tracker = transition_sweep(tracker, bar, _ATR_M1, config)
        assert tracker.state in set(SweepState)
        if was_mitigado:
            # MITIGADO es terminal: nunca sale de ese estado.
            assert tracker.state == SweepState.MITIGADO
        was_mitigado = tracker.state == SweepState.MITIGADO
