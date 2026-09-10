"""Extremo rodante (`RollingExtreme`) para políticas de trailing y análisis técnico.

Mantiene un buffer acotado a las últimas `lookback` observaciones sin mirar hacia
atrás en el tiempo (forward-only). Módulo de dominio puro: solo stdlib.
"""

from __future__ import annotations

from collections import deque


class RollingExtreme:
    """Calcula el máximo y mínimo de una ventana rodante de hasta `lookback` valores.

    Alineado a R5/R6 del spec del Change #97: solo consume valores efectivamente
    alimentados mediante `update(val)` y acota el historial a `maxlen=lookback`.
    """

    def __init__(self, lookback: int) -> None:
        if lookback < 1:
            raise ValueError(f"lookback debe ser >= 1, recibido: {lookback!r}")
        self._lookback = lookback
        self._values: deque[float] = deque(maxlen=lookback)

    @property
    def lookback(self) -> int:
        return self._lookback

    @property
    def count(self) -> int:
        return len(self._values)

    @property
    def is_empty(self) -> bool:
        return len(self._values) == 0

    def update(self, value: float) -> None:
        """Alimenta un valor nuevo al buffer rodante."""
        self._values.append(value)

    def max_value(self) -> float | None:
        """Retorna el máximo de la ventana rodante, o `None` si está vacía."""
        return max(self._values) if self._values else None

    def min_value(self) -> float | None:
        """Retorna el mínimo de la ventana rodante, o `None` si está vacía."""
        return min(self._values) if self._values else None

    def clear(self) -> None:
        """Limpia el buffer de observaciones."""
        self._values.clear()
