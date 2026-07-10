"""Tests de `prop_sim.py`: resampleo diario + máquina de estados + agregación (R15-R56)."""

from datetime import date

import numpy as np
import pytest

from genesis.validation.errors import PropSimConfigError
from genesis.validation.prop_sim import (
    PropSimConfig,
    _build_daily_basket,
    _default_block_size,
    _resample_daily_pnl_path,
)
from tests.validation.fixtures.ledgers import build_empty_ledger, build_ledger_with_daily_trades

pytestmark = pytest.mark.unit


def test_build_daily_basket_suma_por_dia_across_simbolos() -> None:
    day1, day2 = date(2024, 1, 1), date(2024, 1, 2)
    ledger_a = build_ledger_with_daily_trades([(day1, 10.0), (day2, -5.0)], symbol="US500")
    ledger_b = build_ledger_with_daily_trades([(day1, 3.0), (day2, 7.0)], symbol="NAS100")

    basket_days, daily_totals = _build_daily_basket({"US500": ledger_a, "NAS100": ledger_b})

    assert basket_days == [day1, day2]
    assert daily_totals[day1] == pytest.approx(13.0)
    assert daily_totals[day2] == pytest.approx(2.0)


def test_build_daily_basket_vacio_si_ledgers_sin_trades() -> None:
    basket_days, daily_totals = _build_daily_basket(
        {"US500": build_empty_ledger(), "NAS100": build_empty_ledger()}
    )
    assert basket_days == []
    assert daily_totals == {}


def test_default_block_size_formula() -> None:
    assert _default_block_size(1) == 5  # clip inferior
    assert _default_block_size(1_000_000) == 60  # clip superior
    assert _default_block_size(1000) == 10  # round(1000 ** (1/3)) == 10


def test_resample_daily_pnl_path_produce_exactamente_target_len() -> None:
    basket_days = [date(2024, 1, d) for d in range(1, 11)]
    daily_totals = {day: float(index) for index, day in enumerate(basket_days)}
    rng = np.random.default_rng(42)

    path = _resample_daily_pnl_path(basket_days, daily_totals, block_size=3, rng=rng, target_len=25)

    assert len(path) == 25
    assert all(value in daily_totals.values() for value in path)


def test_resample_daily_pnl_path_es_determinista_con_mismo_seed() -> None:
    basket_days = [date(2024, 1, d) for d in range(1, 11)]
    daily_totals = {day: float(index) for index, day in enumerate(basket_days)}

    path1 = _resample_daily_pnl_path(
        basket_days, daily_totals, block_size=3, rng=np.random.default_rng(7), target_len=20
    )
    path2 = _resample_daily_pnl_path(
        basket_days, daily_totals, block_size=3, rng=np.random.default_rng(7), target_len=20
    )

    assert np.array_equal(path1, path2)


def test_prop_sim_config_defaults() -> None:
    config = PropSimConfig(n_paths=100, seed=1)
    assert config.max_attempts == 10
    assert config.horizon_months == 12
    assert config.trading_days_per_month == 21
    assert config.path_horizon_trading_days == 750
    assert config.block_size is None


def test_prop_sim_config_n_paths_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=0, seed=1)


def test_prop_sim_config_max_attempts_invalido_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, max_attempts=0)


def test_prop_sim_config_horizon_months_invalido_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, horizon_months=0)


def test_prop_sim_config_path_horizon_insuficiente_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(
            n_paths=10,
            seed=1,
            horizon_months=12,
            trading_days_per_month=21,
            path_horizon_trading_days=10,
        )


def test_prop_sim_config_block_size_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, block_size=0)
