"""Unit tests para RollingExtreme (Change #97, T1)."""

import pytest

from genesis.strategy.common.rolling_extreme import RollingExtreme

pytestmark = pytest.mark.unit


def test_rolling_extreme_lookback_invalido_lanza_value_error() -> None:
    with pytest.raises(ValueError, match="lookback debe ser >= 1"):
        RollingExtreme(lookback=0)
    with pytest.raises(ValueError, match="lookback debe ser >= 1"):
        RollingExtreme(lookback=-5)


def test_rolling_extreme_estado_inicial_vacio() -> None:
    extreme = RollingExtreme(lookback=5)
    assert extreme.lookback == 5
    assert extreme.count == 0
    assert extreme.is_empty is True
    assert extreme.max_value() is None
    assert extreme.min_value() is None


def test_rolling_extreme_actualizacion_y_calculo_extremos() -> None:
    extreme = RollingExtreme(lookback=3)

    extreme.update(100.0)
    assert extreme.count == 1
    assert extreme.is_empty is False
    assert extreme.max_value() == 100.0
    assert extreme.min_value() == 100.0

    extreme.update(110.0)
    assert extreme.count == 2
    assert extreme.max_value() == 110.0
    assert extreme.min_value() == 100.0

    extreme.update(95.0)
    assert extreme.count == 3
    assert extreme.max_value() == 110.0
    assert extreme.min_value() == 95.0


def test_rolling_extreme_desplaza_ventana_al_superar_lookback() -> None:
    extreme = RollingExtreme(lookback=3)
    extreme.update(10.0)
    extreme.update(20.0)
    extreme.update(30.0)
    assert extreme.max_value() == 30.0
    assert extreme.min_value() == 10.0

    # Al agregar 5.0, 10.0 sale de la ventana: [20.0, 30.0, 5.0]
    extreme.update(5.0)
    assert extreme.count == 3
    assert extreme.max_value() == 30.0
    assert extreme.min_value() == 5.0

    # Al agregar 25.0, 20.0 sale: [30.0, 5.0, 25.0]
    extreme.update(25.0)
    assert extreme.max_value() == 30.0
    assert extreme.min_value() == 5.0

    # Al agregar 1.0, 30.0 sale: [5.0, 25.0, 1.0]
    extreme.update(1.0)
    assert extreme.max_value() == 25.0
    assert extreme.min_value() == 1.0


def test_rolling_extreme_clear_resetea_buffer() -> None:
    extreme = RollingExtreme(lookback=5)
    extreme.update(50.0)
    extreme.update(60.0)
    assert extreme.count == 2

    extreme.clear()
    assert extreme.count == 0
    assert extreme.is_empty is True
    assert extreme.max_value() is None
    assert extreme.min_value() is None
