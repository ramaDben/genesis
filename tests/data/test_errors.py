"""Tests unitarios de la jerarquía de excepciones de dominio de `genesis.data`."""

import pytest

from genesis.data.errors import GenesisDataError

pytestmark = pytest.mark.unit


def test_genesis_data_error_is_exception_subclass() -> None:
    assert issubclass(GenesisDataError, Exception)


def test_genesis_data_error_is_raisable_with_message() -> None:
    with pytest.raises(GenesisDataError, match="contexto de prueba"):
        raise GenesisDataError("contexto de prueba")
