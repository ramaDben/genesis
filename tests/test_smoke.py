"""Smoke test del esqueleto del paquete."""

import genesis
import genesis.backtest
import genesis.data
import genesis.strategy
import genesis.validation


def test_package_importable() -> None:
    assert genesis.__doc__ is not None
