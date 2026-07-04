"""Tests unitarios de la API pública re-exportada por `genesis.data.__init__` (R47)."""

import pytest

from genesis.data import AccountScopeError, DayBoundaryError, QualityError
from genesis.data.errors import GenesisDataError

pytestmark = pytest.mark.unit


def test_public_exceptions_are_importable_from_genesis_data() -> None:
    for exc_class in (AccountScopeError, DayBoundaryError, QualityError):
        assert issubclass(exc_class, GenesisDataError)
