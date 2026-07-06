"""Tests de `_returns.py`: extracción compartida de trades OOS con horizonte (R7-R10, ADR-I1)."""

import pytest

from genesis.validation._returns import TradeReturn, extract_trade_returns
from genesis.validation.wfa import _extract_exit_returns as wfa_extract_exit_returns
from tests.validation.fixtures.ledgers import (
    build_empty_ledger,
    build_entry_only_ledger,
    build_ledger,
)

pytestmark = pytest.mark.unit


def test_extract_trade_returns_devuelve_horizonte_y_pnl_delta_esperados() -> None:
    """R7-R8: cada `TradeReturn` porta `entry_timestamp`/`exit_timestamp`/`pnl_delta`."""
    ledger = build_ledger([10.0, -5.0, 2.5])
    trades = extract_trade_returns(ledger)

    assert len(trades) == 3
    assert all(isinstance(trade, TradeReturn) for trade in trades)
    assert [trade.pnl_delta for trade in trades] == [10.0, -5.0, 2.5]
    for trade in trades:
        assert trade.entry_timestamp < trade.exit_timestamp


def test_extract_trade_returns_solo_entradas_retorna_vacio() -> None:
    """R8: sin ningún `is_exit=True`, no hay trade completo que emparejar."""
    ledger = build_entry_only_ledger(3)
    assert extract_trade_returns(ledger) == []


def test_extract_trade_returns_ledger_vacio_retorna_vacio() -> None:
    ledger = build_empty_ledger()
    assert extract_trade_returns(ledger) == []


def test_extract_trade_returns_equivalencia_con_wfa() -> None:
    """R21 (vía ADR-I1): la proyección `pnl_delta` coincide con `wfa._extract_exit_returns`.

    Garantiza que el DSR de gate (`dsr_pbo.deflated_sharpe_ratio_gate`) reproduzca
    exactamente el mismo DSR-IS que H ya computa sobre las mismas series.
    """
    ledger = build_ledger([10.0, -5.0, 8.0, -3.0, 12.0])
    projected = [trade.pnl_delta for trade in extract_trade_returns(ledger)]
    assert projected == wfa_extract_exit_returns(ledger)


def test_extract_trade_returns_preserva_orden_de_aparicion() -> None:
    """R8: no reordena por timestamp — el ledger es append-only forward-only."""
    ledger = build_ledger([1.0, 2.0, 3.0])
    trades = extract_trade_returns(ledger)
    exit_timestamps = [trade.exit_timestamp for trade in trades]
    assert exit_timestamps == sorted(exit_timestamps)
