"""`SimulationClock` — compone `BarClock` de la capa 2, no hereda (ADR-G1, R5–R9).

Preserva intacta la superficie de 3 miembros de `BarClock` ya certificada por el test
de propiedad de la capa 2 (sin riesgo de override accidental del guard forward-only) y
añade el estado propio de ejecución del simulador: `trading_day` y
`previous_day_close_balance`.
"""

from datetime import date, datetime

from genesis.data.store import AnnotatedBar
from genesis.strategy.clock import BarClock


class SimulationClock:
    """Reloj de simulación: compone `BarClock` y añade estado propio de ejecución (R5).

    `previous_day_close_balance` es un atributo público mutable actualizado por el
    consumidor del loop (`Simulator`, T8/T9) al cruzar `daily_reset_time` — nunca se
    lee de `FirmProfile` ni del contrato de la casa/geometría de salida (R7/R14).
    No expone `window(n)` ni `peek_confirmed(t)` (R8).
    """

    def __init__(self) -> None:
        self._bar_clock: BarClock = BarClock()
        self._trading_day: date | None = None
        self.previous_day_close_balance: float | None = None

    @property
    def current_time(self) -> datetime | None:
        """`t_actual` vigente, delegado al `BarClock` interno (R5)."""
        return self._bar_clock.current_time

    @property
    def trading_day(self) -> date | None:
        """Día de trading vigente, estado propio de `SimulationClock` (R6)."""
        return self._trading_day

    def advance(self, bar: AnnotatedBar) -> None:
        """Avanza el reloj a `bar` (R5/R6/R9).

        Delega primero a `BarClock.advance(bar)` (que puede lanzar `LookaheadError`
        sin reimplementación); solo si no lanzó, actualiza `_trading_day` con el de la
        barra procesada — delegación transparente al guard ya certificado en la capa 2.
        """
        self._bar_clock.advance(bar)
        self._trading_day = bar.trading_day

    def require(self, timestamp: datetime) -> None:
        """Lanza `LookaheadError` si `timestamp` es posterior al `current_time` vigente (R5)."""
        self._bar_clock.require(timestamp)
