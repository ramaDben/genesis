"""Tests de la jerarquía de excepciones de `genesis.backtest` (R1–R4, R59)."""

import pytest

from genesis.backtest.errors import (
    BacktestConfigError,
    GenesisBacktestError,
    SessionBoundaryError,
)
from genesis.data.errors import GenesisDataError
from genesis.strategy.errors import GenesisStrategyError

pytestmark = pytest.mark.unit


def test_session_boundary_error_hereda_de_genesis_backtest_error() -> None:
    assert issubclass(SessionBoundaryError, GenesisBacktestError) is True


def test_backtest_config_error_hereda_de_genesis_backtest_error() -> None:
    assert issubclass(BacktestConfigError, GenesisBacktestError) is True


def test_genesis_backtest_error_no_hereda_de_genesis_strategy_error() -> None:
    assert not issubclass(GenesisBacktestError, GenesisStrategyError)


def test_genesis_backtest_error_no_hereda_de_genesis_data_error() -> None:
    assert not issubclass(GenesisBacktestError, GenesisDataError)


def test_mensaje_con_contexto_se_conserva_en_str() -> None:
    contexto = "symbol=US500 timestamp=2024-01-02T14:30:00Z candidate_id=B valor=10.5"
    err = BacktestConfigError(f"Config inválida: {contexto}")
    assert contexto in str(err)
