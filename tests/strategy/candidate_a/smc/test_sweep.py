"""`SweepState` + `transition_sweep` — traza golden de 5 estados (T3.5, R103, spec eval 3)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

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


def _eqh_level() -> LiquidityLevel:
    swing = Swing(
        timeframe=Timeframe.M1,
        direction=SwingDirection.HIGH,
        price=100.0,
        pivot_time=_BASE,
        confirmed_time=_BASE + timedelta(minutes=2),
    )
    return LiquidityLevel(
        level_id=1,
        timeframe=Timeframe.M1,
        direction=SwingDirection.HIGH,
        price=100.0,
        member_swings=(swing,),
        mitigated=False,
    )


def test_traza_armado_tocado_barrido_expirado_armado() -> None:
    config = _Config(sweep_tolerance_atr=0.05, sweep_window_k=5, sweep_validity_m=3)
    level = _eqh_level()
    tracker = SweepTracker(
        level=level, state=SweepState.ARMADO, touch_time=None, swept_time=None, extreme_price=None
    )
    trace = [tracker.state]

    # Bar 1: toque (high > 100.05), sin cierre de vuelta -> TOCADO.
    bar1 = make_annotated_bar(
        _BASE + timedelta(minutes=10), open_=100.0, high=100.10, low=99.9, close=100.2
    )
    tracker = transition_sweep(tracker, bar1, _ATR_M1, config)
    trace.append(tracker.state)
    assert tracker.state == SweepState.TOCADO

    # Bar 2: cierra de vuelta dentro del nivel (posición 2 <= sweep_window_k=5) -> BARRIDO.
    bar2 = make_annotated_bar(
        _BASE + timedelta(minutes=11), open_=100.1, high=100.15, low=99.85, close=99.9
    )
    tracker = transition_sweep(tracker, bar2, _ATR_M1, config)
    trace.append(tracker.state)
    assert tracker.state == SweepState.BARRIDO

    # Bars 3-4: siguen dentro (BARRIDO habilitado), sin mitigación.
    for minute in (12, 13):
        bar = make_annotated_bar(_BASE + timedelta(minutes=minute), close=99.8, high=99.9, low=99.7)
        tracker = transition_sweep(tracker, bar, _ATR_M1, config)
        trace.append(tracker.state)

    # Bar 5: sweep_validity_m=3 agotado -> EXPIRADO.
    bar5 = make_annotated_bar(_BASE + timedelta(minutes=14), close=99.8, high=99.9, low=99.7)
    tracker = transition_sweep(tracker, bar5, _ATR_M1, config)
    trace.append(tracker.state)
    assert tracker.state == SweepState.EXPIRADO

    # Bar 6: EXPIRADO -> ARMADO.
    bar6 = make_annotated_bar(_BASE + timedelta(minutes=15), close=99.8, high=99.9, low=99.7)
    tracker = transition_sweep(tracker, bar6, _ATR_M1, config)
    trace.append(tracker.state)
    assert tracker.state == SweepState.ARMADO

    deduped = [state for i, state in enumerate(trace) if i == 0 or state != trace[i - 1]]
    assert deduped == [
        SweepState.ARMADO,
        SweepState.TOCADO,
        SweepState.BARRIDO,
        SweepState.EXPIRADO,
        SweepState.ARMADO,
    ]


def test_mitigacion_desde_barrido_por_cierre_mas_alla() -> None:
    config = _Config(sweep_tolerance_atr=0.05, sweep_window_k=5, sweep_validity_m=30)
    level = _eqh_level()
    tracker = SweepTracker(
        level=level, state=SweepState.BARRIDO, touch_time=None, swept_time=None, extreme_price=100.1
    )
    bar = make_annotated_bar(_BASE, close=100.5, high=100.6, low=100.0)
    tracker = transition_sweep(tracker, bar, _ATR_M1, config)
    assert tracker.state == SweepState.MITIGADO


def test_mitigacion_desde_tocado_por_ventana_agotada_sin_cierre_de_vuelta() -> None:
    config = _Config(sweep_tolerance_atr=0.05, sweep_window_k=2, sweep_validity_m=30)
    level = _eqh_level()
    tracker = SweepTracker(
        level=level,
        state=SweepState.TOCADO,
        touch_time=_BASE,
        swept_time=None,
        extreme_price=100.1,
        bars_in_state=0,
    )
    bar = make_annotated_bar(_BASE + timedelta(minutes=1), close=100.5, high=100.6, low=100.2)
    tracker = transition_sweep(tracker, bar, _ATR_M1, config)
    assert tracker.state == SweepState.MITIGADO


def test_mitigado_es_terminal() -> None:
    config = _Config(sweep_tolerance_atr=0.05, sweep_window_k=5, sweep_validity_m=30)
    level = _eqh_level()
    tracker = SweepTracker(
        level=level,
        state=SweepState.MITIGADO,
        touch_time=None,
        swept_time=None,
        extreme_price=None,
    )
    bar = make_annotated_bar(_BASE, close=50.0, high=200.0, low=1.0)
    tracker = transition_sweep(tracker, bar, _ATR_M1, config)
    assert tracker.state == SweepState.MITIGADO
