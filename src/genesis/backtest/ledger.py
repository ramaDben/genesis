"""Registro append-only y reconstrucción pura de equity (R42–R47, ADR-G9).

`LedgerEntry.payload` es un tipo suma (`RejectionRecord | FillRecord | BreachEvent`,
ADR-G9) que resuelve la pregunta abierta del spec §9 sin campos opcionales ambiguos.
`RunProvenance` es una única instancia compartida por todas las entradas de un run
(ADR-G9): satisface R45 ("cada entrada con `candidate_id`/`config_version`/hashes")
sin duplicar bytes.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from genesis.strategy.contract import Direction
from genesis.strategy.inspector import InspectorVerdict

CONFIG_VERSION: str = "genesis-backtest/1"
"""Versión del esquema de configuración de la capa 3, patrón `metadata.CONFIG_VERSION`."""


class BreachKind(StrEnum):
    """Tipo de infracción detectada en línea por el simulador (R43).

    Exactamente 4 miembros: ampliar esta enumeración es un cambio de alcance que
    requiere un Change nuevo (no relajar el gate de forma silenciosa).
    """

    DAILY = "daily"
    TOTAL = "total"
    NEWS = "news"
    WEEKEND = "weekend"


@dataclass(frozen=True, slots=True)
class BreachEvent:
    """Evento de infracción de riesgo detectado en línea (R44).

    `account_exhausted` solo es `True` para `kind=TOTAL` (R31): es el único breach
    terminal; `DAILY`/`NEWS`/`WEEKEND` son continuables (R29).
    """

    kind: BreachKind
    trading_day: date
    timestamp_utc: datetime
    magnitude: float
    threshold: float
    account_exhausted: bool = False


@dataclass(frozen=True, slots=True)
class RejectionRecord:
    """Decisión pre-trade del embudo de viabilidad de la capa 2 (Inspector)."""

    candidate_id: str
    symbol: str
    intent_time: datetime
    verdict: InspectorVerdict


@dataclass(frozen=True, slots=True)
class FillRecord:
    """Fill ejecutado, de entrada o de salida, ya con costos aplicados."""

    candidate_id: str
    symbol: str
    timestamp_utc: datetime
    price: float
    direction: Direction
    is_exit: bool
    cost_applied: float
    equity_after: float


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """Ficha de reproducibilidad compartida por todas las entradas de un run (R45, ADR-G9)."""

    candidate_id: str
    config_version: str
    dataset_hash: str
    firm_profile_hash: str
    risk_profile_hash: str


@dataclass(frozen=True, slots=True)
class TrailingStopMoved:
    """Evento de modificación efectiva de stop loss por trailing Chandelier (Change #97)."""

    position_id: str
    symbol: str
    timestamp_utc: datetime
    stop_previo: float
    stop_nuevo: float


Decision = RejectionRecord | FillRecord | BreachEvent | TrailingStopMoved
"""Tipo suma del `payload` de una entrada del ledger (ADR-G9, spec §9 pregunta abierta)."""


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """Entrada unificada del ledger: `provenance` compartida + `payload` tipo suma (R45)."""

    provenance: RunProvenance
    payload: Decision


@dataclass
class Ledger:
    """Contenedor append-only de `LedgerEntry` (ADR-G9)."""

    provenance: RunProvenance
    entries: list[LedgerEntry] = field(default_factory=list)

    def append(self, payload: Decision) -> None:
        """Agrega `payload` al final del ledger, envuelto con la `provenance` compartida."""
        self.entries.append(LedgerEntry(provenance=self.provenance, payload=payload))


def reconstruct_equity_series(
    entries: Sequence[LedgerEntry],
) -> dict[date, list[tuple[datetime, float]]]:
    """Reconstruye la serie de equity intradía por día, pura, desde el ledger (R46).

    Recorre exclusivamente `FillRecord.equity_after` en el orden en que aparecen en
    `entries`, agrupado por la fecha UTC de `timestamp_utc`; no depende de ningún
    estado del `Simulator` en ejecución — base del test de propiedad R47 (T12).
    """
    series: dict[date, list[tuple[datetime, float]]] = {}
    for entry in entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            day = payload.timestamp_utc.date()
            series.setdefault(day, []).append((payload.timestamp_utc, payload.equity_after))
    return series
