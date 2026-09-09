"""Puerto de calendario económico y normalización pura de ventanas de noticias.

Insumo de `news_restrictions` (spec §1.3: bracketing prohibido alrededor de noticias de
alto impacto) y del filtro de entradas del Candidato B. La lógica de normalización
(`news_windows`) es 100% pura y no depende de la fuente concreta (R16, R19); la fuente de
producción de este Change es `CsvCalendarSource` (resolución del gate humano
DESIGN→APPLY, ver `design.md` §13).
"""

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from genesis.data.errors import GenesisDataError
from genesis.data.profile import FirmProfile


class CalendarError(GenesisDataError):
    """Fuente de calendario indisponible o evento sin timestamp UTC tz-aware (R16)."""


class ImpactLevel(StrEnum):
    """Nivel de impacto de un evento de calendario económico."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    """Evento de calendario económico ya normalizado a un timestamp UTC."""

    timestamp_utc: datetime
    currency: str
    impact: ImpactLevel
    title: str


@runtime_checkable
class EconomicCalendarSource(Protocol):
    """Puerto inyectable de obtención de eventos de calendario económico (R16, R34).

    Permite testear `news_windows` con una fuente fake, sin red ni dependencia externa.
    """

    def fetch_events(self, start: datetime, end: datetime) -> list[EconomicEvent]:
        """Retorna los eventos publicados en `[start, end]`.

        Lanza una excepción explícita (p. ej. `CalendarError`) si la fuente falla; una
        lista vacía es una respuesta legítima cuando no hubo eventos en el rango.
        """
        ...


SYMBOL_CURRENCIES: Mapping[str, frozenset[str]] = {
    "US500": frozenset({"USD"}),
    "NAS100": frozenset({"USD"}),
    "US30": frozenset({"USD"}),
    "GER40": frozenset({"EUR"}),
    "BTCUSDT": frozenset({"USD"}),
}
"""Divisas cuyos eventos de alto impacto afectan a cada símbolo convencional."""


def news_windows(
    events: Sequence[EconomicEvent],
    symbol: str,
    firm_profile: FirmProfile,
) -> list[tuple[datetime, datetime]]:
    """Produce las ventanas UTC prohibidas por bracketing para `symbol` (R18, R19).

    Función pura sobre la lista de eventos ya obtenida (sin I/O): por cada evento
    `ImpactLevel.HIGH` cuya divisa afecta a `symbol` (según `SYMBOL_CURRENCIES`), produce
    `(evento - firm_profile.news_bracket_before, evento + firm_profile.news_bracket_after)`.
    Eventos con impacto distinto de `HIGH` no generan ventana.

    Lanza `CalendarError` si algún evento trae un `timestamp_utc` naive (sin tzinfo).
    """
    relevant_currencies = SYMBOL_CURRENCIES.get(symbol, frozenset())
    windows: list[tuple[datetime, datetime]] = []
    for event in events:
        if event.timestamp_utc.tzinfo is None:
            message = f"Evento '{event.title}' sin timestamp UTC tz-aware: {event.timestamp_utc!r}."
            raise CalendarError(message)
        if event.impact is not ImpactLevel.HIGH:
            continue
        if event.currency not in relevant_currencies:
            continue
        windows.append(
            (
                event.timestamp_utc - firm_profile.news_bracket_before,
                event.timestamp_utc + firm_profile.news_bracket_after,
            )
        )
    return windows


class CsvCalendarSource:
    """Fuente de calendario económico de producción: CSV versionado en el repo.

    Decisión del gate humano DESIGN→APPLY (`design.md` §13): fuente reproducible, sin
    red en CI. Espera un CSV con columnas `timestamp_utc` (ISO 8601 con offset),
    `currency`, `impact` (`low`/`medium`/`high`) y `title`. El MCP `market-data` es el
    mecanismo manual para poblar/refrescar el CSV, fuera del alcance de este módulo.
    """

    def __init__(self, csv_path: Path) -> None:
        self._csv_path = csv_path

    def fetch_events(self, start: datetime, end: datetime) -> list[EconomicEvent]:
        """Lee el CSV y retorna los eventos cuyo `timestamp_utc` cae en `[start, end]`.

        Lanza `CalendarError` si el archivo no existe o una fila tiene un esquema
        inválido (columna faltante, timestamp no parseable).
        """
        try:
            with self._csv_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                events = [self._parse_row(row) for row in reader]
        except (OSError, csv.Error) as exc:
            message = f"No se pudo leer el calendario económico desde '{self._csv_path}': {exc}"
            raise CalendarError(message) from exc
        return [event for event in events if start <= event.timestamp_utc <= end]

    @staticmethod
    def _parse_row(row: Mapping[str, str]) -> EconomicEvent:
        try:
            timestamp_utc = datetime.fromisoformat(row["timestamp_utc"])
            if timestamp_utc.tzinfo is None:
                raise ValueError("timestamp_utc sin zona horaria")
            return EconomicEvent(
                timestamp_utc=timestamp_utc,
                currency=row["currency"],
                impact=ImpactLevel(row["impact"].lower()),
                title=row["title"],
            )
        except (KeyError, ValueError) as exc:
            message = f"Fila de calendario económico inválida: {row!r} ({exc})"
            raise CalendarError(message) from exc
