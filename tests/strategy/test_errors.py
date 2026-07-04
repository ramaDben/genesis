"""Tests unitarios de la jerarquía de excepciones de dominio de `genesis.strategy`."""

import pytest

from genesis.data.errors import GenesisDataError
from genesis.strategy.errors import (
    DuplicateCandidateError,
    GenesisStrategyError,
    InspectorConfigError,
    LookaheadError,
)

pytestmark = pytest.mark.unit


def test_genesis_strategy_error_is_exception_subclass() -> None:
    assert issubclass(GenesisStrategyError, Exception)


def test_genesis_strategy_error_is_not_subclass_of_genesis_data_error() -> None:
    assert not issubclass(GenesisStrategyError, GenesisDataError)


def test_lookahead_error_is_subclass_of_genesis_strategy_error() -> None:
    assert issubclass(LookaheadError, GenesisStrategyError)


def test_duplicate_candidate_error_is_subclass_of_genesis_strategy_error() -> None:
    assert issubclass(DuplicateCandidateError, GenesisStrategyError)


def test_inspector_config_error_is_subclass_of_genesis_strategy_error() -> None:
    assert issubclass(InspectorConfigError, GenesisStrategyError)


def test_genesis_strategy_error_is_raisable_with_message() -> None:
    with pytest.raises(GenesisStrategyError, match="contexto de prueba"):
        raise GenesisStrategyError("contexto de prueba")


def test_lookahead_error_message_conserva_contexto() -> None:
    with pytest.raises(LookaheadError, match=r"2024-01-01.*2024-01-02"):
        raise LookaheadError("solicitado=2024-01-01, t_actual=2024-01-02")
