"""Tests para el motor de política de salida `exit_policy.py` (Change #97).

Criterios de aceptación verificados:
- A1: Monotonía en largos (no decreciente).
- A2: Monotonía en cortos (no creciente).
- A3: El piso del stop inicial (no retroceso ante movimientos adversos).
- A9: Sin calentamiento / sin ATR no hay trailing y no se levanta excepción.
- A14: Un salto brusco de ATR no afloja el stop efectivo (ratchet post-recálculo).
"""

from itertools import pairwise

import hypothesis.strategies as st
from hypothesis import given

from genesis.backtest.exit_policy import TrailingState, _TrailingState, nivel, ratchet
from genesis.strategy.common.rolling_extreme import RollingExtreme
from genesis.strategy.contract import Direction


def test_nivel_calculo_basico() -> None:
    """Verifica cálculo exacto de fórmula Chandelier (R1, R2)."""
    # LONG: high - k * atr = 100 - 3 * 2 = 94
    assert nivel(Direction.LONG, extreme=100.0, atr=2.0, atr_mult=3.0) == 94.0
    # SHORT: low + k * atr = 100 + 3 * 2 = 106
    assert nivel(Direction.SHORT, extreme=100.0, atr=2.0, atr_mult=3.0) == 106.0


def test_criterio_a9_sin_calentamiento_sin_trailing() -> None:
    """Criterio A9 / R11: Sin calentamiento no hay trailing y no hay excepción."""
    # Sin ATR
    assert nivel(Direction.LONG, extreme=100.0, atr=None, atr_mult=3.0) is None
    assert ratchet(stop_previo=90.0, nivel=None, direction=Direction.LONG) == 90.0

    # Sin extremo (buffer vacío)
    assert nivel(Direction.LONG, extreme=None, atr=2.0, atr_mult=3.0) is None
    assert ratchet(stop_previo=90.0, nivel=None, direction=Direction.LONG) == 90.0

    # TrailingState con buffer vacío
    state = _TrailingState(rolling_extreme=RollingExtreme(lookback=22), current_stop=90.0)
    assert state.nivel(Direction.LONG, atr=None, atr_mult=3.0) is None
    assert state.update_stop(Direction.LONG, atr=None, atr_mult=3.0) == 90.0
    assert state.update_stop(Direction.LONG, atr=2.0, atr_mult=3.0) == 90.0


def test_criterio_a3_piso_stop_inicial() -> None:
    """Criterio A3: El stop inicial es el piso absoluto, serie adversa no afloja."""
    initial_stop_long = 95.0
    state_long = TrailingState(
        rolling_extreme=RollingExtreme(lookback=5),
        current_stop=initial_stop_long,
    )

    # Serie en contra: máximos decrecientes [99..95] con ATR=2.0, k=3.0 -> nivel = max - 6
    for h in [99.0, 98.0, 97.0, 96.0, 95.0]:
        state_long.rolling_extreme.update(h)
        stop = state_long.update_stop(Direction.LONG, atr=2.0, atr_mult=3.0)
        assert stop == initial_stop_long

    initial_stop_short = 105.0
    state_short = TrailingState(
        rolling_extreme=RollingExtreme(lookback=5),
        current_stop=initial_stop_short,
    )

    # Serie en contra: mínimos crecientes [101..105] con ATR=2.0, k=3.0 -> nivel = min + 6
    for low in [101.0, 102.0, 103.0, 104.0, 105.0]:
        state_short.rolling_extreme.update(low)
        stop = state_short.update_stop(Direction.SHORT, atr=2.0, atr_mult=3.0)
        assert stop == initial_stop_short


def test_criterio_a14_salto_atr_no_afloja_stop() -> None:
    """Criterio A14 / Q-B: Un salto brusco de ATR sobre posición ganadora no afloja el stop.

    Verifica que el ratchet se aplica DESPUÉS del recálculo.
    """
    initial_stop = 90.0
    state = _TrailingState(rolling_extreme=RollingExtreme(lookback=5), current_stop=initial_stop)

    # La posición gana terreno: high llega a 110.0 con ATR normal = 2.0 -> nivel = 110 - 3*2 = 104.0
    state.rolling_extreme.update(110.0)
    stop_ganador = state.update_stop(Direction.LONG, atr=2.0, atr_mult=3.0)
    assert stop_ganador == 104.0

    # Inyectamos una explosión de volatilidad: ATR sube abruptamente de 2.0 a 10.0
    # Nivel recalculado: 110 - 3*10 = 80.0 (se alejaría a 80.0)
    # Por ratchet post-recálculo: max(104.0, 80.0) = 104.0
    stop_tras_shock = state.update_stop(Direction.LONG, atr=10.0, atr_mult=3.0)
    assert stop_tras_shock == 104.0
    assert stop_tras_shock == stop_ganador

    # Equivalente en SHORT
    initial_stop_s = 110.0
    state_s = _TrailingState(
        rolling_extreme=RollingExtreme(lookback=5),
        current_stop=initial_stop_s,
    )

    # Posición corta gana terreno: low llega a 90.0 con ATR normal = 2.0 -> nivel = 90 + 3*2 = 96.0
    state_s.rolling_extreme.update(90.0)
    stop_ganador_s = state_s.update_stop(Direction.SHORT, atr=2.0, atr_mult=3.0)
    assert stop_ganador_s == 96.0

    # Explosión de volatilidad: ATR sube a 10.0 -> nivel = 90 + 3*10 = 120.0
    # Por ratchet: min(96.0, 120.0) = 96.0
    stop_tras_shock_s = state_s.update_stop(Direction.SHORT, atr=10.0, atr_mult=3.0)
    assert stop_tras_shock_s == 96.0
    assert stop_tras_shock_s == stop_ganador_s


@given(
    initial_stop=st.floats(
        min_value=1.0, max_value=10_000.0, allow_nan=False, allow_infinity=False
    ),
    highs=st.lists(
        st.floats(min_value=1.0, max_value=20_000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ),
    atrs=st.lists(
        st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ),
    lookback=st.integers(min_value=1, max_value=30),
    atr_mult=st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_criterio_a1_monotonia_en_largos_property(
    initial_stop: float,
    highs: list[float],
    atrs: list[float],
    lookback: int,
    atr_mult: float,
) -> None:
    """Criterio A1: La secuencia de stops efectivos de una posición larga es no decreciente."""
    state = _TrailingState(
        rolling_extreme=RollingExtreme(lookback=lookback),
        current_stop=initial_stop,
    )
    stops = [initial_stop]

    n = min(len(highs), len(atrs))
    for i in range(n):
        state.rolling_extreme.update(highs[i])
        new_stop = state.update_stop(Direction.LONG, atr=atrs[i], atr_mult=atr_mult)
        stops.append(new_stop)

    for prev, nxt in pairwise(stops):
        assert nxt >= prev


@given(
    initial_stop=st.floats(
        min_value=1.0, max_value=10_000.0, allow_nan=False, allow_infinity=False
    ),
    lows=st.lists(
        st.floats(min_value=1.0, max_value=20_000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ),
    atrs=st.lists(
        st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ),
    lookback=st.integers(min_value=1, max_value=30),
    atr_mult=st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_criterio_a2_monotonia_en_cortos_property(
    initial_stop: float,
    lows: list[float],
    atrs: list[float],
    lookback: int,
    atr_mult: float,
) -> None:
    """Criterio A2: La secuencia de stops efectivos de una posición corta es no creciente."""
    state = _TrailingState(
        rolling_extreme=RollingExtreme(lookback=lookback),
        current_stop=initial_stop,
    )
    stops = [initial_stop]

    n = min(len(lows), len(atrs))
    for i in range(n):
        state.rolling_extreme.update(lows[i])
        new_stop = state.update_stop(Direction.SHORT, atr=atrs[i], atr_mult=atr_mult)
        stops.append(new_stop)

    for prev, nxt in pairwise(stops):
        assert nxt <= prev
