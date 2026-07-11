"""Propiedad central de fractales: ningún `Swing` visible antes de `confirmed_time`.

Spec §9 / eval 2: `assert swing not in <swings visibles>` para todo índice
`< i + fractal_n`. Se verifica generando secuencias arbitrarias con `hypothesis` y
comprobando que cualquier `Swing` retornado por `FractalDetector.push` solo ocurre en
la vela de confirmación (ventana llena), nunca antes.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.strategy.candidate_a.smc.fractals import FractalDetector
from genesis.strategy.candidate_a.smc.timeframe import Timeframe, to_m1_aggregated_bar
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)
_FRACTAL_N = 2


def _agg_bars(highs: list[float]):
    bars = []
    for index, high in enumerate(highs):
        bar = make_annotated_bar(
            _BASE + timedelta(minutes=index), close=high - 0.5, high=high, low=high - 2.0
        )
        bars.append(to_m1_aggregated_bar(bar))
    return bars


@given(
    highs=st.lists(
        st.floats(min_value=90.0, max_value=110.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=25,
    ),
)
@settings(max_examples=300, deadline=None)
def test_swing_high_nunca_visible_antes_de_ventana_completa(highs: list[float]) -> None:
    bars = _agg_bars(highs)
    detector = FractalDetector(Timeframe.M1, _FRACTAL_N)

    for index, bar in enumerate(bars):
        swings = detector.push(bar)
        if swings:
            # Solo puede emitir a partir de la primera ventana llena.
            assert index >= 2 * _FRACTAL_N
            for swing in swings:
                pivot_index = index - _FRACTAL_N
                assert swing.pivot_time == bars[pivot_index].open_time
                assert swing.confirmed_time == bar.close_time


def test_ningun_swing_repetido_para_el_mismo_pivote() -> None:
    """Cada vela pivote se evalúa exactamente una vez (R100 estructural)."""
    highs = [100.0, 100.0, 105.0, 100.0, 100.0, 100.0, 100.0]
    bars = _agg_bars(highs)
    detector = FractalDetector(Timeframe.M1, _FRACTAL_N)
    all_swings = [swing for bar in bars for swing in detector.push(bar)]
    assert len(all_swings) == 1
