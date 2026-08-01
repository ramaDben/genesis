"""Contrato plugin `StrategyCandidate` (PA-3, `docs/SPEC_GENESIS_v1.4...md` §11.1).

Interfaz mínima que todo candidato de estrategia implementa, sin lógica de negocio
(spec §2.1/§2.5: aislamiento entre candidatos, ningún estado compartido). Este módulo
importa solo stdlib y `genesis.data.store.AnnotatedBar`: NO depende de
`genesis.strategy.inspector` ni de `genesis.strategy.common` (R7).

`AnnotatedBar.timestamp_utc` (`genesis.data.store`) **es** el `confirmed_time`
normativo del spec (§2.1): toda `AnnotatedBar` producida por `iter_bars` representa
una vela M1 ya cerrada, sin noción de "vela en curso" en esta capa.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from genesis.data.store import AnnotatedBar
from genesis.strategy.errors import DuplicateCandidateError

CONFIG_VERSION: str = "genesis-strategy/1"
"""Versión del esquema de configuración/contrato de la capa 2 (estrategia)."""


class Direction(StrEnum):
    """Dirección de una intención de entrada."""

    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class EntryIntent:
    """Intención de entrada mínima emitida por un candidato (spec §2.1).

    Exactamente los cuatro campos normativos: sin lotaje real, R:R ni timestamp — ese
    contexto pre-trade lo aporta el sitio de la llamada al Inspector (`inspector.py`).
    """

    direction: Direction
    sizing_hint: float
    candidate_id: str
    config_version: str


@runtime_checkable
class StrategyCandidate(Protocol):
    """Puerto inyectable que todo candidato de estrategia implementa (R1, R2).

    Patrón `genesis.data.calendar.EconomicCalendarSource` (único precedente de puerto
    inyectable del repo). `on_bar` recibe una `AnnotatedBar` ya cerrada (ver docstring
    del módulo) y retorna cero o más `EntryIntent`; el candidato NUNCA alimenta su
    propio reloj (`BarClock`), eso es responsabilidad del consumidor (Issue G).
    """

    candidate_id: str

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        """Procesa una barra ya cerrada y retorna las intenciones de entrada emitidas."""
        ...


CANDIDATE_REGISTRY: dict[str, type[StrategyCandidate]] = {}
"""Registro módulo-nivel letra → clase de candidato (solo mapeo, no estado de ejecución)."""


def register_candidate[CandidateT: StrategyCandidate](
    letter: str,
) -> Callable[[type[CandidateT]], type[CandidateT]]:
    """Decorador de clase: registra la clase decorada bajo `letter.upper()` (R5).

    Genérico acotado a `StrategyCandidate`: liga el tipo de retorno al de la clase
    decorada (el nombre decorado conserva su clase concreta y sigue siendo una forma de
    tipo válida) y garantiza que lo que entra a `CANDIDATE_REGISTRY` sea un
    `type[StrategyCandidate]`.

    Lanza `DuplicateCandidateError` con contexto (letra + clase ya registrada) si
    `letter` ya está registrada — ninguna colisión silenciosa.
    """
    normalized = letter.upper()

    def decorator(strategy_type: type[CandidateT]) -> type[CandidateT]:
        if normalized in CANDIDATE_REGISTRY:
            existing = CANDIDATE_REGISTRY[normalized]
            message = (
                f"La letra de candidato '{normalized}' ya está registrada por "
                f"'{existing.__qualname__}'; no se puede registrar '{strategy_type.__qualname__}'."
            )
            raise DuplicateCandidateError(message)
        CANDIDATE_REGISTRY[normalized] = strategy_type
        return strategy_type

    return decorator
