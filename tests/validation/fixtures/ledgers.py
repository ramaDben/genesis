"""Builders de `Ledger` sintético con `FillRecord` entrada/salida deterministas (R53).

Usados por los tests de `_extract_exit_returns` (T5) y de `montecarlo.py` (T9/T10):
producen ledgers cuyo delta de `equity_after` por trade de salida es conocido de
antemano por el propio test (input/output concreto), sin pasar por el `Simulator`
real. `build_ledger_with_trade_intervals` (Issue I) amplía el patrón con
`entry_timestamp`/`exit_timestamp` explícitos por trade, necesarios para los
tests de purga por solapamiento de horizonte de `purged_cv.py` (López de Prado,
*AFML* cap. 7).
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from genesis.backtest.ledger import (
    ExhaustionPolicy,
    FillRecord,
    Ledger,
    RejectionRecord,
    RunProvenance,
)
from genesis.strategy.contract import Direction
from genesis.strategy.inspector import InspectorVerdict, RejectionReason

_TEST_PROVENANCE = RunProvenance(
    candidate_id="B",
    config_version="genesis-backtest/1",
    dataset_hash="test-dataset-hash",
    firm_profile_hash="test-firm-profile-hash",
    exit_geometry_hash="test-exit-geometry-hash",
    house_rule_hash="test-house-rule-hash",
    exhaustion_policy=ExhaustionPolicy.HALT_ENTRIES,
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


def build_ledger_with_trade_intervals(
    intervals: Sequence[tuple[datetime, datetime, float]],
    *,
    symbol: str = "US500",
    starting_equity: float = 100_000.0,
) -> Ledger:
    """`Ledger` con un par entrada/salida por cada `(entry_timestamp, exit_timestamp, delta)`.

    A diferencia de `build_ledger` (timestamps secuenciales arbitrarios de 1 minuto),
    aquí el llamador fija el horizonte exacto de cada trade — usado por los tests de
    purga por solapamiento de horizonte + embargo de `purged_cv.py` (Issue I, R15,
    R20/R47, R50b). Los `intervals` se insertan en el orden dado (mismo patrón de
    pareado secuencial que `extract_trade_returns`, sin exigir orden cronológico de
    inserción).
    """
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    equity = starting_equity
    for entry_timestamp, exit_timestamp, delta in intervals:
        ledger.append(
            FillRecord(
                candidate_id="B",
                symbol=symbol,
                timestamp_utc=entry_timestamp,
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
                timestamp_utc=exit_timestamp,
                price=100.0,
                direction=Direction.LONG,
                is_exit=True,
                cost_applied=0.0,
                equity_after=equity,
            )
        )
    return ledger


def build_ledger_with_rejections(
    *,
    n_lot_size: int,
    n_other_reason: int = 0,
    other_reason: RejectionReason | None = None,
    n_entry_fills: int = 0,
    symbol: str = "US500",
) -> Ledger:
    """`Ledger` sintético con `RejectionRecord` (Q8) para tests de "evidencia de sizing".

    Genera, en este orden, `n_lot_size` `RejectionRecord` con
    `verdict.rejection_reason=LOT_SIZE_OUT_OF_BOUNDS`, luego `n_other_reason`
    `RejectionRecord` con `other_reason` (por defecto `INSUFFICIENT_RR` si
    `n_other_reason > 0` y `other_reason` no se especifica) y finalmente
    `n_entry_fills` `FillRecord(is_exit=False)` — insumo de A1-A4 y A7 (Change #51).
    Timestamps deterministas, secuenciales de 1 minuto desde 2024-01-02T14:30 UTC.
    """
    resolved_other_reason = (
        other_reason if other_reason is not None else RejectionReason.INSUFFICIENT_RR
    )
    ledger = Ledger(provenance=_TEST_PROVENANCE, entries=[])
    timestamp = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    equity = 100_000.0
    for _ in range(n_lot_size):
        ledger.append(
            RejectionRecord(
                candidate_id="B",
                symbol=symbol,
                intent_time=timestamp,
                verdict=InspectorVerdict(
                    authorized=False, rejection_reason=RejectionReason.LOT_SIZE_OUT_OF_BOUNDS
                ),
            )
        )
        timestamp += timedelta(minutes=1)
    for _ in range(n_other_reason):
        ledger.append(
            RejectionRecord(
                candidate_id="B",
                symbol=symbol,
                intent_time=timestamp,
                verdict=InspectorVerdict(authorized=False, rejection_reason=resolved_other_reason),
            )
        )
        timestamp += timedelta(minutes=1)
    for _ in range(n_entry_fills):
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
