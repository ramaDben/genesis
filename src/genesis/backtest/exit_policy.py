"""Motor de política de salida de capa 3 — Trailing Chandelier con ratchet (Change #97).

Dominio puro: solo stdlib y contratos de estrategia (`Direction`).
Sin dependencias del orquestador `Simulator` ni de la capa de datos.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesis.strategy.common.rolling_extreme import RollingExtreme
from genesis.strategy.contract import Direction


def nivel(
    direction: Direction,
    extreme: float | None,
    atr: float | None,
    atr_mult: float,
) -> float | None:
    """Calcula el nivel Chandelier Stop (R1, R2).

    Retorna `None` si no hay observaciones de extremo (`extreme is None`) o si el ATR
    aún no está disponible/calentado (`atr is None`).

    Fórmulas normativas:
    - En largos (LONG): `extreme - atr_mult * atr`
    - En cortos (SHORT): `extreme + atr_mult * atr`
    """
    if extreme is None or atr is None:
        return None
    if direction is Direction.LONG:
        return extreme - atr_mult * atr
    return extreme + atr_mult * atr


def ratchet(stop_previo: float, nivel: float | None, direction: Direction) -> float:
    """Aplica el trinquete (ratchet) garantizando monotonía en ambas direcciones (R3, R4).

    El stop nunca se mueve en contra de la posición:
    - En largos (LONG): `max(stop_previo, nivel)` (no decreciente).
    - En cortos (SHORT): `min(stop_previo, nivel)` (no creciente).
    - Si `nivel is None`: conserva `stop_previo` (R11).
    """
    if nivel is None:
        return stop_previo
    if direction is Direction.LONG:
        return max(stop_previo, nivel)
    return min(stop_previo, nivel)


@dataclass(slots=True)
class _TrailingState:
    """Estado de trailing por posición (R5, §11.3).

    Contiene únicamente el `RollingExtreme` anclado en la apertura de la posición
    y el stop vigente.
    """

    rolling_extreme: RollingExtreme
    current_stop: float

    def nivel(
        self,
        direction: Direction,
        atr: float | None,
        atr_mult: float,
    ) -> float | None:
        """Calcula el nivel Chandelier con el extremo actual del buffer."""
        extreme = (
            self.rolling_extreme.max_value()
            if direction is Direction.LONG
            else self.rolling_extreme.min_value()
        )
        return nivel(direction, extreme, atr, atr_mult)

    def update_stop(
        self,
        direction: Direction,
        atr: float | None,
        atr_mult: float,
    ) -> float:
        """Calcula el nivel y aplica ratchet monótono actualizando `current_stop`."""
        target = self.nivel(direction, atr, atr_mult)
        self.current_stop = ratchet(self.current_stop, target, direction)
        return self.current_stop


TrailingState = _TrailingState
