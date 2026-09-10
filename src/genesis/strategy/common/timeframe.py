"""`Timeframe` + agregación M1→TF (`BarAggregator`), R97.

Módulo de dominio puro: solo stdlib + `genesis.data.store.AnnotatedBar` (capa 1).
Promovido desde `candidate_a/smc/timeframe.py` a `strategy/common/timeframe.py` (Change #97).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from genesis.data.store import AnnotatedBar


class Timeframe(StrEnum):
    """Marco temporal de una vela agregada."""

    M1 = "M1"
    M15 = "M15"
    H1 = "H1"


@dataclass(frozen=True, slots=True)
class AggregatedBar:
    """Vela agregada de un `Timeframe`, emitida solo cuando su última M1 cierra."""

    timeframe: Timeframe
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    open_time: datetime
    """Timestamp de la primera M1 componente (ancla de apertura del TF)."""
    close_time: datetime
    """Timestamp de la última M1 componente == cierre/confirmación del TF."""


def to_m1_aggregated_bar(bar: AnnotatedBar) -> AggregatedBar:
    """Envuelve una `AnnotatedBar` M1 como `AggregatedBar(timeframe=M1)` trivial.

    M1 es la unidad base: no requiere agregación (`BarAggregator` solo agrega M15/H1),
    pero `FractalDetector`/`LiquidityMap` operan de forma genérica sobre `AggregatedBar`
    para cualquier `Timeframe`, incluido M1.
    """
    return AggregatedBar(
        timeframe=Timeframe.M1,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        tick_volume=bar.tick_volume,
        open_time=bar.timestamp_utc,
        close_time=bar.timestamp_utc,
    )


_ANCHOR_MINUTES: dict[Timeframe, int] = {
    Timeframe.M15: 15,
    Timeframe.H1: 60,
}
"""Minutos del ancla de cada TF agregado (R97): M15 cierra en minuto 14/29/44/59 del
reloj de pared UTC (`minute % 15 == 14`); H1 cierra en minuto 59 (`minute % 60 == 59`)."""


class _Accumulator:
    """Acumulador mutable interno de una `AggregatedBar` en construcción."""

    __slots__ = ("close", "high", "low", "open", "open_time", "tick_volume")

    def __init__(self, bar: AnnotatedBar) -> None:
        self.open_time = bar.timestamp_utc
        self.open = bar.open
        self.high = bar.high
        self.low = bar.low
        self.close = bar.close
        self.tick_volume = bar.tick_volume

    def extend(self, bar: AnnotatedBar) -> None:
        self.high = max(self.high, bar.high)
        self.low = min(self.low, bar.low)
        self.close = bar.close
        self.tick_volume += bar.tick_volume

    def to_aggregated_bar(self, timeframe: Timeframe, close_time: datetime) -> AggregatedBar:
        return AggregatedBar(
            timeframe=timeframe,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            tick_volume=self.tick_volume,
            open_time=self.open_time,
            close_time=close_time,
        )


class BarAggregator:
    """Acumula M1 y emite una `AggregatedBar` de M15/H1 solo cuando su última M1 cierra.

    Nunca pide series nativas M15/H1 (R97): la agregación se construye enteramente a
    partir del flujo M1, alineada al ancla estándar de reloj de pared UTC.
    """

    def __init__(self) -> None:
        self._accumulators: dict[Timeframe, _Accumulator | None] = {
            Timeframe.M15: None,
            Timeframe.H1: None,
        }

    def push(self, bar: AnnotatedBar) -> list[AggregatedBar]:
        """Procesa una M1 y retorna las `AggregatedBar` que cierran en esta barra (0-2)."""
        emitted: list[AggregatedBar] = []
        for timeframe, anchor_minutes in _ANCHOR_MINUTES.items():
            accumulator = self._accumulators[timeframe]
            if accumulator is None:
                accumulator = _Accumulator(bar)
            else:
                accumulator.extend(bar)

            closes_here = bar.timestamp_utc.minute % anchor_minutes == anchor_minutes - 1
            if closes_here:
                emitted.append(accumulator.to_aggregated_bar(timeframe, bar.timestamp_utc))
                accumulator = None

            self._accumulators[timeframe] = accumulator
        return emitted
