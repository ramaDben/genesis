"""Builders de `Ledger` sintético con `FillRecord` entrada/salida deterministas (R53).

Usados por los tests de `_extract_exit_returns` (T5) y de `montecarlo.py` (T9/T10):
producen ledgers cuyo delta de `equity_after` por trade de salida es conocido de
antemano por el propio test (input/output concreto), sin pasar por el `Simulator`
real.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from genesis.backtest.ledger import FillRecord, Ledger, RunProvenance
from genesis.strategy.contract import Direction

_TEST_PROVENANCE = RunProvenance(
    candidate_id="B",
    config_version="genesis-backtest/1",
    dataset_hash="test-dataset-hash",
    firm_profile_hash="test-firm-profile-hash",
    risk_profile_hash="test-risk-profile-hash",
)


def build_ledger(
    deltas: Sequence[float],
    *,
    symbol: str = "US500",
    starting_equity: float = 100_000.0,
) -> Ledger:
    """`Ledger` con un par entrada/salida por cada delta de `deltas`, en orden.

    El delta de `equity_after` entre la entrada y la salida de cada par es
    exactamente el valor correspondiente de `deltas` (contrato exacto usado por los
    tests de `_extract_exit_returns`).
    """
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    equity = starting_equity
    timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    for delta in deltas:
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=timestamp,
                price=100.0,
                direction=Direction.LONG,
                is_exit=False,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
        timestamp += timedelta(minutes=1)
        equity += delta
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=timestamp,
                price=100.0,
                direction=Direction.LONG,
                is_exit=True,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
        timestamp += timedelta(minutes=1)
    return ledger


def build_entry_only_ledger(n: int, *, symbol: str = "US500") -> Ledger:
    """`Ledger` con `n` `FillRecord` de solo entrada (ningún `is_exit=True`)."""
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    equity = 100_000.0
    for _ in range(n):
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=timestamp,
                price=100.0,
                direction=Direction.LONG,
                is_exit=False,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
        timestamp += timedelta(minutes=1)
    return ledger


def build_empty_ledger(*, symbol: str = "US500") -> Ledger:
    """`Ledger` sin ninguna entrada (provenance válida, `entries=[]`)."""
    del symbol
    return Ledger(provenance=_TEST_PROVENANCE, entries=[])


def build_ledger_with_daily_trades(
    daily_deltas: Sequence[tuple[date, float]],
    *,
    symbol: str = "US500",
    starting_equity: float = 100_000.0,
) -> Ledger:
    """`Ledger` con un par entrada/salida por cada `(trading_day, delta)` de `daily_deltas`.

    El `FillRecord` de salida de cada par se marca con `timestamp_utc` a las 20:00
    UTC del `trading_day` correspondiente (dentro de la sesión de cualquier índice
    del universo B); usado por los tests de canasta por día de `monte_carlo_portfolio`
    (R43, R46).
    """
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    equity = starting_equity
    for trading_day, delta in daily_deltas:
        entry_time = datetime(
            trading_day.year, trading_day.month, trading_day.day, 14, 30, tzinfo=UTC
        )
        exit_time = datetime(
            trading_day.year, trading_day.month, trading_day.day, 20, 0, tzinfo=UTC
        )
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=entry_time,
                price=100.0,
                direction=Direction.LONG,
                is_exit=False,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
        equity += delta
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=exit_time,
                price=100.0,
                direction=Direction.LONG,
                is_exit=True,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
    return ledger
