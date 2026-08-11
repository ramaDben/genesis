"""Value objects puros de símbolos y su ficha extendida (capa 1: datos).

Este módulo no importa el SDK `MetaTrader5` ni ninguna otra dependencia de I/O: solo
define estructuras de datos inmutables consumidas por `mt5_export.py` (que sí toca el
SDK) y por `quality.py` (que las consume sin arrastrar esa dependencia).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolFigure:
    """Ficha extendida de un símbolo MT5, capturada en cada export (R10).

    Corresponde a los campos exigidos por el spec §4/§4.1: `tick_value`, `tick_size`,
    `volume_step`, `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short` y
    `swap_rollover_day`, más el símbolo convencional al que pertenece. `tick_value` y
    `tick_size` se persisten **crudos** tal como los reporta el terminal (`trade_tick_value`,
    `trade_tick_size`); la conversión punto→dinero es derivada y vive en `value_per_point`
    (Change #55): NO DEBE normalizarse antes de persistir.
    """

    symbol: str
    tick_value: float
    tick_size: float
    volume_step: float
    stops_level: int
    freeze_level: int
    digits: int
    swap_long: float
    swap_short: float
    swap_rollover_day: int

    @property
    def value_per_point(self) -> float:
        """Dinero por 1.0 punto de precio y por lote: `tick_value / tick_size`.

        Única implementación permitida de la conversión punto→dinero (invariante del diseño
        de Change #55): ningún consumidor de capa 3 debe multiplicar por `tick_value` crudo.
        """
        if self.tick_size <= 0:
            raise ValueError(
                f"tick_size no positivo para el símbolo {self.symbol!r}: "
                f"tick_value={self.tick_value!r}, tick_size={self.tick_size!r}"
            )
        return self.tick_value / self.tick_size


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    """Símbolo convencional junto con su ficha (opcional) y criterio de suficiencia.

    `min_full_sessions` es el umbral mínimo de sesiones de contado completas que
    `quality.py` usa como proxy de historia disponible (R24) — no es el gate G1 real.
    """

    symbol: str
    figure: SymbolFigure | None
    min_full_sessions: int
