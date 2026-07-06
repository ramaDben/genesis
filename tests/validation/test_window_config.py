"""Tests de geometría de ventanas y presupuesto de grid (R6, R7, R12, R13)."""

import pytest

from genesis.validation.errors import WfaConfigError
from genesis.validation.window_config import (
    IS_WINDOW_TRADING_DAYS,
    OOS_WINDOW_TRADING_DAYS,
    STEP_TRADING_DAYS,
    GridConfig,
    WfaWindowConfig,
    window_identity_hash,
)

pytestmark = pytest.mark.unit


def test_constantes_de_geometria_normativas() -> None:
    assert IS_WINDOW_TRADING_DAYS == 252
    assert OOS_WINDOW_TRADING_DAYS == 126
    assert STEP_TRADING_DAYS == 126


def test_wfa_window_config_defaults_usan_las_constantes() -> None:
    config = WfaWindowConfig()
    assert config.is_window_trading_days == IS_WINDOW_TRADING_DAYS
    assert config.oos_window_trading_days == OOS_WINDOW_TRADING_DAYS
    assert config.step_trading_days == STEP_TRADING_DAYS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"is_window_trading_days": 0},
        {"oos_window_trading_days": -1},
        {"step_trading_days": 0},
    ],
)
def test_wfa_window_config_no_positivo_lanza_wfa_config_error(kwargs: dict[str, int]) -> None:
    with pytest.raises(WfaConfigError):
        WfaWindowConfig(**kwargs)


def test_grid_config_defaults_cumplen_presupuesto_27_9() -> None:
    grid = GridConfig()
    assert len(grid.execution_combos()) == 27
    assert len(grid.signal_configs()) == 9


def test_grid_config_mas_de_9_senal_lanza_wfa_config_error() -> None:
    with pytest.raises(WfaConfigError):
        GridConfig(n_minutes_levels=(1, 2, 3, 4))


def test_grid_config_mas_de_27_ejecucion_lanza_wfa_config_error() -> None:
    with pytest.raises(WfaConfigError):
        GridConfig(risk_pct_levels=(0.001, 0.002, 0.003, 0.004))


def test_window_identity_hash_determinista() -> None:
    args = ("B", "US500", "hash_is", "hash_oos", "grid_hash", "genesis-validation/1")
    assert window_identity_hash(*args) == window_identity_hash(*args)


def test_window_identity_hash_cambia_con_un_solo_argumento_distinto() -> None:
    base = ("B", "US500", "hash_is", "hash_oos", "grid_hash", "genesis-validation/1")
    changed = ("B", "US500", "hash_is_2", "hash_oos", "grid_hash", "genesis-validation/1")
    assert window_identity_hash(*base) != window_identity_hash(*changed)
