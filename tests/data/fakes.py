"""Fakes deterministas reutilizables para la suite `tests/data/` (sin red ni SDK real)."""

from collections.abc import Sequence
from datetime import datetime

from genesis.data.calendar import EconomicEvent


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
