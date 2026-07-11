"""`Swing` + `FractalDetector`: fractales con doble timestamp (R98-R100).

Módulo de dominio puro: solo stdlib + `genesis.strategy.candidate_a.smc.timeframe`.
Base normativa citada (spec §3.3 del Change, fuente externa §4.1): un `Swing` se
confirma cuando la vela pivote tiene un extremo estrictamente más allá de `fractal_n`
velas a cada lado del mismo TF; `confirmed_time` es el cierre de la N-ésima vela
posterior. **R100 estructural**: `FractalDetector.push` solo retorna el `Swing` en la
vela de confirmación — ningún `Swing` con `confirmed_time` posterior al `current_time`
es jamás visible, por construcción (nunca por un chequeo posterior de timestamps).
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from genesis.strategy.candidate_a.smc.timeframe import AggregatedBar, Timeframe


class SwingDirection(StrEnum):
    """Dirección de un `Swing`: extremo alto (EQH candidato) o bajo (EQL candidato)."""

    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Swing:
    """Fractal confirmado con doble timestamp (`pivot_time`/`confirmed_time`, R98)."""

    timeframe: Timeframe
    direction: SwingDirection
    price: float
    pivot_time: datetime
    """Timestamp de la vela del extremo (la vela pivote del fractal)."""
    confirmed_time: datetime
    """Timestamp de cierre de la N-ésima vela posterior (instante de confirmación)."""


class FractalDetector:
    """Ventana deslizante de `2*fractal_n + 1` velas del mismo `Timeframe` (R99/R100).

    Cada vela pivote se evalúa exactamente una vez: cuando la ventana alcanza su
    tamaño completo con esa vela centrada, es decir, en el instante exacto de su
    confirmación. Ninguna vela se re-evalúa dos veces como pivote.
    """

    def __init__(self, timeframe: Timeframe, fractal_n: int) -> None:
        self._timeframe = timeframe
        self._fractal_n = fractal_n
        self._window: deque[AggregatedBar] = deque(maxlen=2 * fractal_n + 1)

    def push(self, agg_bar: AggregatedBar) -> list[Swing]:
        """Procesa una `AggregatedBar` del TF propio; retorna 0-2 `Swing` confirmados."""
        self._window.append(agg_bar)
        if len(self._window) < (self._window.maxlen or 0):
            return []

        bars = list(self._window)
        pivot_index = self._fractal_n
        pivot = bars[pivot_index]
        others = bars[:pivot_index] + bars[pivot_index + 1 :]

        swings: list[Swing] = []
        if others and all(pivot.high > other.high for other in others):
            swings.append(
                Swing(
                    timeframe=self._timeframe,
                    direction=SwingDirection.HIGH,
                    price=pivot.high,
                    pivot_time=pivot.open_time,
                    confirmed_time=bars[-1].close_time,
                )
            )
        if others and all(pivot.low < other.low for other in others):
            swings.append(
                Swing(
                    timeframe=self._timeframe,
                    direction=SwingDirection.LOW,
                    price=pivot.low,
                    pivot_time=pivot.open_time,
                    confirmed_time=bars[-1].close_time,
                )
            )
        return swings
