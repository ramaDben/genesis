"""`Swing` + `FractalDetector` — confirmación determinista (T3.3, R98-R100, spec eval 2)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.strategy.candidate_a.smc.fractals import FractalDetector, SwingDirection
from genesis.strategy.candidate_a.smc.timeframe import Timeframe, to_m1_aggregated_bar
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)
_FRACTAL_N = 2


def _agg_bars(highs: list[float], lows: list[float]):
    bars = []
    for index, (high, low) in enumerate(zip(highs, lows, strict=True)):
        bar = make_annotated_bar(
            _BASE + timedelta(minutes=index), close=(high + low) / 2, high=high, low=low
        )
        bars.append(to_m1_aggregated_bar(bar))
    return bars


def test_swing_high_no_visible_antes_de_i_mas_fractal_n() -> None:
    # Pivote (índice 4) más alto que las fractal_n=2 velas a cada lado.
    highs = [100.0, 100.0, 100.0, 100.0, 105.0, 100.0, 100.0, 100.0, 100.0]
    lows = [h - 1.0 for h in highs]
    bars = _agg_bars(highs, lows)
    detector = FractalDetector(Timeframe.M1, _FRACTAL_N)

    swings_by_index: list[list] = []
    for bar in bars:
        swings_by_index.append(detector.push(bar))

    # No visible antes del índice 4+2=6 (inclusive).
    for index in range(6):
        assert swings_by_index[index] == []

    confirmed = swings_by_index[6]
    assert len(confirmed) == 1
    swing = confirmed[0]
    assert swing.direction == SwingDirection.HIGH
    assert swing.price == 105.0
    assert swing.pivot_time == bars[4].open_time
    assert swing.confirmed_time == bars[6].close_time


def test_swing_low_simetrico() -> None:
    lows = [100.0, 100.0, 100.0, 100.0, 95.0, 100.0, 100.0, 100.0, 100.0]
    highs = [low + 1.0 for low in lows]
    bars = _agg_bars(highs, lows)
    detector = FractalDetector(Timeframe.M1, _FRACTAL_N)

    swings_by_index = [detector.push(bar) for bar in bars]
    for index in range(6):
        assert swings_by_index[index] == []
    confirmed = swings_by_index[6]
    assert len(confirmed) == 1
    swing = confirmed[0]
    assert swing.direction == SwingDirection.LOW
    assert swing.price == 95.0


def test_pivote_no_estrictamente_extremo_no_confirma_swing() -> None:
    highs = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    lows = [h - 1.0 for h in highs]
    bars = _agg_bars(highs, lows)
    detector = FractalDetector(Timeframe.M1, _FRACTAL_N)
    all_swings = [swing for bar in bars for swing in detector.push(bar)]
    assert all_swings == []
