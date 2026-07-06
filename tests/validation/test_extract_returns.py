"""Tests de `_extract_exit_returns` duplicado en `wfa.py`/`montecarlo.py` (R61, §1.6)."""

import pytest

from genesis.validation.montecarlo import _extract_exit_returns as mc_extract_exit_returns
from genesis.validation.wfa import _extract_exit_returns as wfa_extract_exit_returns
from tests.validation.fixtures.ledgers import (
    build_empty_ledger,
    build_entry_only_ledger,
    build_ledger,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("extract", [wfa_extract_exit_returns, mc_extract_exit_returns])
def test_extract_exit_returns_devuelve_deltas_esperados(extract) -> None:  # type: ignore[no-untyped-def]
    ledger = build_ledger([10.0, -5.0, 2.5])
    assert extract(ledger) == [10.0, -5.0, 2.5]


@pytest.mark.parametrize("extract", [wfa_extract_exit_returns, mc_extract_exit_returns])
def test_extract_exit_returns_solo_entradas_retorna_vacio(extract) -> None:  # type: ignore[no-untyped-def]
    ledger = build_entry_only_ledger(3)
    assert extract(ledger) == []


@pytest.mark.parametrize("extract", [wfa_extract_exit_returns, mc_extract_exit_returns])
def test_extract_exit_returns_ledger_vacio_retorna_vacio(extract) -> None:  # type: ignore[no-untyped-def]
    ledger = build_empty_ledger()
    assert extract(ledger) == []
