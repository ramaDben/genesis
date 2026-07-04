"""`BarClock` — reloj de vista incremental forward-only (PA-4).

Guard mínimo de disciplina forward-only, desacoplado del diseño del simulador real
(Issue G): este Change entrega solo el objeto de vista incremental suficiente para
que el test de propiedad central del spec §9 sea ejecutable (ADR-C3).
"""

from datetime import datetime

from genesis.data.store import AnnotatedBar
from genesis.strategy.errors import LookaheadError


class BarClock:
    """Reloj de vista incremental forward-only. Guard mínimo de `LookaheadError` (PA-4).

    Lo alimenta bar-a-bar el CONSUMIDOR (simulador de Issue G, o el harness de test de
    este Change) vía `advance`; nunca el candidato. Superficie cerrada de 3 miembros
    (`current_time`, `advance`, `require`) en este Change — sujeta a EXTENSIÓN (no
    ruptura) en Issue G (ADR-C3): no expone `__getitem__`, `seek`, índice absoluto ni
    acceso a barras futuras (misma disciplina que `store.iter_bars`).
    """

    def __init__(self) -> None:
        self._current_time: datetime | None = None

    @property
    def current_time(self) -> datetime | None:
        """`t_actual` vigente; `None` antes de la primera barra."""
        return self._current_time

    def advance(self, bar: AnnotatedBar) -> None:
        """Avanza el reloj a `bar.timestamp_utc`.

        Lanza `LookaheadError` si `bar.timestamp_utc` retrocede estrictamente respecto
        al `current_time` vigente (R11). Un `timestamp_utc` igual al vigente se
        permite (re-lectura idempotente de la misma barra).
        """
        if self._current_time is not None and bar.timestamp_utc < self._current_time:
            message = (
                f"BarClock.advance: retroceso detectado. bar.timestamp_utc="
                f"{bar.timestamp_utc!r} es anterior al current_time vigente "
                f"{self._current_time!r} (el reloj nunca retrocede)."
            )
            raise LookaheadError(message)
        self._current_time = bar.timestamp_utc

    def require(self, timestamp: datetime) -> None:
        """Lanza `LookaheadError` si `timestamp` es posterior al `current_time` vigente.

        También lanza si `current_time is None` (ningún timestamp es válido antes de
        la primera barra). No lanza si `timestamp <= current_time` (R40).
        """
        if self._current_time is None:
            message = (
                f"BarClock.require: no hay current_time vigente (ninguna barra "
                f"procesada aún); timestamp solicitado={timestamp!r}."
            )
            raise LookaheadError(message)
        if timestamp > self._current_time:
            message = (
                f"BarClock.require: lookahead detectado. timestamp solicitado="
                f"{timestamp!r} es posterior al current_time vigente "
                f"{self._current_time!r}."
            )
            raise LookaheadError(message)
