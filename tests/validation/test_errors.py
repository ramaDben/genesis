"""Tests de la jerarquía de excepciones de `genesis.validation` (R1-R5, R64)."""

import pytest

from genesis.backtest.errors import GenesisBacktestError
from genesis.data.errors import GenesisDataError
from genesis.strategy.errors import GenesisStrategyError
from genesis.validation.errors import (
    GenesisValidationError,
    MonteCarloConfigError,
    WfaConfigError,
)

pytestmark = pytest.mark.unit


def test_wfa_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(WfaConfigError, GenesisValidationError) is True


def test_montecarlo_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(MonteCarloConfigError, GenesisValidationError) is True


def test_genesis_validation_error_no_hereda_de_genesis_backtest_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisBacktestError)


def test_genesis_validation_error_no_hereda_de_genesis_strategy_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisStrategyError)


def test_genesis_validation_error_no_hereda_de_genesis_data_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisDataError)


def test_mensaje_con_contexto_se_conserva_en_str_wfa() -> None:
    contexto = "candidate_id=B symbol=US500 window_index=2 valor=historia_insuficiente"
    err = WfaConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_mensaje_con_contexto_se_conserva_en_str_montecarlo() -> None:
    contexto = "candidate_id=B symbol=US500 n_paths=-1"
    err = MonteCarloConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)
