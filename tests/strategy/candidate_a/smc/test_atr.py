"""`IncrementalAtr` (T3.2, R106)."""

import pytest

from genesis.strategy.candidate_a.errors import SmcEngineStateError
from genesis.strategy.candidate_a.smc.atr import IncrementalAtr

pytestmark = pytest.mark.unit

# (high, low, close) fijas, período 3: TR = [2.0, 1.5, 2.5, 1.0, 3.0]
_BARS = [
    (101.0, 99.0, 100.0),
    (101.5, 100.0, 101.0),
    (102.5, 100.0, 101.5),
    (102.0, 101.0, 101.8),
    (104.0, 101.0, 103.0),
]


def test_value_antes_de_calentar_lanza_smc_engine_state_error() -> None:
    atr = IncrementalAtr(period=3)
    atr.update(*_BARS[0])
    with pytest.raises(SmcEngineStateError):
        atr.value()
    assert atr.is_warmed() is False


def test_atr_wilder_calentamiento_y_suavizado() -> None:
    atr = IncrementalAtr(period=3)
    for bar in _BARS[:3]:
        atr.update(*bar)
    assert atr.is_warmed() is True
    # Calentamiento: media simple de los 3 primeros TR = (2.0+1.5+2.5)/3 = 2.0
    warmup_value = atr.value()
    assert warmup_value == pytest.approx(2.0)

    # Suavizado Wilder: TR[3] = max(1.0, |102.0-101.5|, |101.0-101.5|) = 1.0
    atr.update(*_BARS[3])
    expected = ((warmup_value * 2) + 1.0) / 3
    assert atr.value() == pytest.approx(expected)


def test_atr_continuo_cross_dia_nunca_reseteado() -> None:
    atr = IncrementalAtr(period=3)
    for bar in _BARS:
        atr.update(*bar)
    value_before = atr.value()
    # Una barra adicional "de otro día" sigue suavizando el mismo estado, sin reset.
    atr.update(105.0, 103.0, 104.0)
    assert atr.value() != value_before
    assert atr.is_warmed() is True
