"""Lector de ticks forward-only propio sobre `RawParquetStore` (R15–R19, ADR-G6).

No añade métodos nuevos a `store.py`/`mt5_export.py` (capa 1 cerrada, R57): consume
exclusivamente `RawParquetStore.has_chunk`/`read_chunk`, ya públicos. La ausencia de
ticks para un `(symbol, trading_day)` es el caso normal (PA-2 de B), nunca una
excepción (R16); solo un chunk presente-pero-inválido lanza `BacktestConfigError`
(R17). `_day_window` y `has_sufficient_tick_coverage` comparten el mismo criterio de
borde de la ventana de cobertura `(T-60s, T]` (RI-G5, ADR-G8, Rg-3 §5.2).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import pandas as pd

from genesis.backtest.errors import BacktestConfigError
from genesis.data.mt5_export import ChunkWindow, Granularity, RawParquetStore
from genesis.data.store import AnnotatedBar

_REQUIRED_COLUMNS = ("bid", "ask", "last")
_COVERAGE_WINDOW = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class TickRow:
    """Fila de tick ya normalizada, forward-only (una vez emitida no se relee)."""

    timestamp_utc: datetime
    bid: float
    ask: float
    last: float


def _day_window(trading_day: date) -> ChunkWindow:
    """Construye el `ChunkWindow` del día completo `[00:00, 24:00)` UTC de `trading_day`."""
    start = datetime.combine(trading_day, time.min, tzinfo=UTC)
    return ChunkWindow(start=start, end=start + timedelta(days=1))


def _validate_tick_schema(frame: pd.DataFrame, *, symbol: str, trading_day: date) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        message = (
            f"Chunk de ticks inválido para symbol={symbol!r}, trading_day={trading_day!r}: "
            f"columnas faltantes {missing} (esperadas {_REQUIRED_COLUMNS})."
        )
        raise BacktestConfigError(message)
    for column in _REQUIRED_COLUMNS:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            message = (
                f"Chunk de ticks inválido para symbol={symbol!r}, trading_day={trading_day!r}: "
                f"columna '{column}' no es numérica (dtype={frame[column].dtype})."
            )
            raise BacktestConfigError(message)


def iter_ticks(
    store: RawParquetStore,
    symbol: str,
    trading_day: date,
) -> Iterator[TickRow]:
    """Lector forward-only de ticks del día (R15).

    Retorna secuencia vacía (nunca lanza) si no hay chunk persistido para
    `(symbol, trading_day)` (R16). Si el chunk existe pero su esquema es inválido
    (columnas `bid`/`ask`/`last` ausentes o mal tipadas), lanza `BacktestConfigError`
    (R17). Si es válido, emite `TickRow` ordenados por `timestamp_utc` ascendente.
    """
    window = _day_window(trading_day)
    if not store.has_chunk(symbol, Granularity.TICK, window):
        return

    frame = store.read_chunk(symbol, Granularity.TICK, window)
    _validate_tick_schema(frame, symbol=symbol, trading_day=trading_day)

    ordered = frame.sort_values("timestamp")
    for _, row in ordered.iterrows():
        raw_timestamp = row["timestamp"]
        timestamp_utc = (
            raw_timestamp.to_pydatetime()
            if hasattr(raw_timestamp, "to_pydatetime")
            else raw_timestamp
        )
        yield TickRow(
            timestamp_utc=timestamp_utc,
            bid=float(row["bid"]),
            ask=float(row["ask"]),
            last=float(row["last"]),
        )


def has_sufficient_tick_coverage(
    store: RawParquetStore,
    symbol: str,
    bar: AnnotatedBar,
    day_ticks: Sequence[TickRow],
) -> bool:
    """Criterio de dos niveles de cobertura suficiente de ticks para `bar` (R18, ADR-G8).

    `True` si y solo si `(a)` existe chunk de ticks persistido para el día de `bar` y
    `(b)` hay al menos un tick en la ventana semiabierta-izquierda/cerrada-derecha
    `(bar.timestamp_utc - 60s, bar.timestamp_utc]` (tolerancia cero, Rg-3 §5.2).
    """
    window = _day_window(bar.trading_day)
    if not store.has_chunk(symbol, Granularity.TICK, window):
        return False

    lower_bound = bar.timestamp_utc - _COVERAGE_WINDOW
    return any(lower_bound < tick.timestamp_utc <= bar.timestamp_utc for tick in day_ticks)
