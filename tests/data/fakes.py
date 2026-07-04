"""Fakes deterministas reutilizables para la suite `tests/data/` (sin red ni SDK real)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from genesis.data.calendar import EconomicEvent
from genesis.data.symbols import SymbolFigure

# Valores documentados del SDK MetaTrader5 (`account_info().trade_mode`); se replican
# aquí como constantes puras para no requerir importar el SDK en tests unit/property.
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2


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


def _default_symbol_figure(symbol: str) -> SymbolFigure:
    return SymbolFigure(
        symbol=symbol,
        tick_value=1.0,
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


class FakeMt5Terminal:
    """Terminal MT5 fake, determinista, con contadores de llamadas (R50).

    `account_info().trade_mode` es parametrizable (`ACCOUNT_TRADE_MODE_DEMO`/`_REAL`) para
    testear el guard de cuenta (R3). Las descargas (`copy_rates_range`/`copy_ticks_range`)
    son puras respecto a `(symbol, date_from, date_to)`: dos instancias independientes con
    los mismos parámetros producen frames idénticos, necesarios para el eval de
    determinismo bit-idéntico del Parquet (R36).
    """

    def __init__(
        self,
        *,
        trade_mode: int = ACCOUNT_TRADE_MODE_DEMO,
        available_symbols: Sequence[str] = (),
        symbol_figures: dict[str, SymbolFigure] | None = None,
    ) -> None:
        self.trade_mode = trade_mode
        self.available_symbols = list(available_symbols)
        self.symbol_figures = symbol_figures or {}
        self.copy_rates_range_calls = 0
        self.copy_ticks_range_calls = 0
        self.call_log: list[tuple[object, ...]] = []

    def initialize(self, *args: object, **kwargs: object) -> bool:
        self.call_log.append(("initialize", args, kwargs))
        return True

    def shutdown(self) -> None:
        self.call_log.append(("shutdown",))

    def last_error(self) -> tuple[int, str]:
        return (0, "sin error (fake)")

    def account_info(self) -> object:
        return SimpleNamespace(trade_mode=self.trade_mode)

    def symbols_get(self, group: str | None = None) -> tuple[object, ...]:
        self.call_log.append(("symbols_get", group))
        return tuple(SimpleNamespace(name=name) for name in self.available_symbols)

    def symbol_info(self, symbol: str) -> object:
        return self.symbol_figures.get(symbol, _default_symbol_figure(symbol))

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: datetime, date_to: datetime
    ) -> object:
        self.copy_rates_range_calls += 1
        self.call_log.append(("copy_rates_range", symbol, date_from, date_to))
        return _deterministic_m1_frame(symbol, date_from, date_to)

    def copy_ticks_range(
        self, symbol: str, date_from: datetime, date_to: datetime, flags: int
    ) -> object:
        self.copy_ticks_range_calls += 1
        self.call_log.append(("copy_ticks_range", symbol, date_from, date_to))
        return _deterministic_tick_frame(symbol, date_from, date_to)
