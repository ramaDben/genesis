"""ATR-Wilder incremental (`IncrementalAtr`).

Módulo de dominio puro: solo stdlib + `genesis.strategy.common.errors`.
Promovido desde `candidate_a/smc/atr.py` para uso compartido por estrategias
y políticas de salida de capa 3 (Change #97).
"""

from __future__ import annotations

from genesis.strategy.common.errors import IncrementalAtrStateError


class IncrementalAtr:
    """ATR-Wilder(`period`) incremental, continuo cross-día (NUNCA reseteado).

    `value()` lanza `IncrementalAtrStateError` si se consulta antes del calentamiento;
    `is_warmed()` expone el estado sin lanzar.
    """

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError(f"period debe ser >= 1, recibido: {period!r}")
        self._period = period
        self._bars_seen = 0
        self._warmup_sum = 0.0
        self._value: float | None = None
        self._last_close: float | None = None

    def update(self, high: float, low: float, close: float) -> None:
        """Actualiza el ATR con una vela nueva (True Range de Wilder, media móvil)."""
        last = self._last_close
        true_range = (
            high - low if last is None else max(high - low, abs(high - last), abs(low - last))
        )
        self._last_close = close  # actualizado DESPUÉS de calcular TR (cruza día)

        if self._bars_seen < self._period:
            self._bars_seen += 1
            self._warmup_sum += true_range
            if self._bars_seen == self._period:
                self._value = self._warmup_sum / self._period  # media simple
            return

        current = self._value
        if current is None:
            message = (
                f"IncrementalAtr en fase de suavizado sin valor calentado "
                f"(bars_seen={self._bars_seen!r}, period={self._period!r}) — "
                "invariante interna violada."
            )
            raise IncrementalAtrStateError(message)
        self._value = ((current * (self._period - 1)) + true_range) / self._period

    def value(self) -> float:
        """Retorna el ATR vigente; lanza `IncrementalAtrStateError` antes del calentamiento."""
        if self._value is None:
            message = (
                f"IncrementalAtr.value() consultado antes del calentamiento "
                f"(bars_seen={self._bars_seen!r} < period={self._period!r})."
            )
            raise IncrementalAtrStateError(message)
        return self._value

    def is_warmed(self) -> bool:
        """`True` cuando `bars_seen >= period` y el valor está calentado."""
        return self._value is not None
