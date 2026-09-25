"""Fakes deterministas reutilizables para la suite `tests/data/` (sin red ni SDK real)."""

from collections.abc import Sequence
from datetime import UTC, datetime

import pandas as pd

from genesis.data.calendar import EconomicEvent
from genesis.data.symbols import SymbolFigure


class FakeEconomicCalendarSource:
    """Fuente de calendario económico fake, sin red, para testear `news_windows`.

    Si `error` está definido, `fetch_events` lo lanza en vez de retornar `events`
    (permite testear la propagación de fallos de fuente, R16).
    """

    def __init__(
        self, events: Sequence[EconomicEvent] = (), *, error: Exception | None = None
    ) -> None:
        self._events = list(events)
        self._error = error
        self.fetch_events_calls = 0

    def fetch_events(self, start: datetime, end: datetime) -> list[EconomicEvent]:
        self.fetch_events_calls += 1
        if self._error is not None:
            raise self._error
        return list(self._events)


def _default_symbol_figure(
    symbol: str, *, tick_value: float = 1.0, tick_size: float = 1.0
) -> SymbolFigure:
    return SymbolFigure(
        symbol=symbol,
        tick_value=tick_value,
        tick_size=tick_size,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-1.0,
        swap_short=-1.0,
        swap_rollover_day=3,
    )


def _deterministic_m1_frame(symbol: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
    """Genera un frame M1 determinista (mismo símbolo/rango -> mismos valores) sin I/O."""
    timestamps = pd.date_range(date_from, date_to, freq="1min", tz=UTC, inclusive="left")
    if len(timestamps) == 0:
        timestamps = pd.DatetimeIndex([date_from], tz=UTC)
    base = float(len(symbol))
    closes = [base + (i % 7) * 0.1 for i in range(len(timestamps))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "tick_volume": [10] * len(timestamps),
        }
    )


def _deterministic_tick_frame(symbol: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
    """Genera un frame de ticks determinista (mismo símbolo/rango -> mismos valores)."""
    timestamps = pd.date_range(date_from, date_to, freq="1s", tz=UTC, inclusive="left")
    if len(timestamps) == 0:
        timestamps = pd.DatetimeIndex([date_from], tz=UTC)
    base = float(len(symbol))
    bids = [base + (i % 5) * 0.01 for i in range(len(timestamps))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "bid": bids,
            "ask": [b + 0.01 for b in bids],
        }
    )
