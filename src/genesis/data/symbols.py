"""Value objects puros de símbolos y su ficha extendida (capa 1: datos).

Este módulo no importa el SDK `MetaTrader5` ni ninguna otra dependencia de I/O: solo
define estructuras de datos inmutables consumidas por `mt5_export.py` (que sí toca el
SDK) y por `quality.py` (que las consume sin arrastrar esa dependencia).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolFigure:
    """Ficha extendida de un símbolo MT5, capturada en cada export (R10).

    Corresponde a los campos exigidos por el spec §4/§4.1: `tick_value`, `volume_step`,
    `stops_level`, `freeze_level`, `digits`, `swap_long`, `swap_short` y
    `swap_rollover_day`, más el símbolo convencional al que pertenece.
    """

    symbol: str
    tick_value: float
    volume_step: float
    stops_level: int
    freeze_level: int
    digits: int
    swap_long: float
    swap_short: float
    swap_rollover_day: int


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    """Símbolo convencional junto con su ficha (opcional) y criterio de suficiencia.

    `min_full_sessions` es el umbral mínimo de sesiones de contado completas que
    `quality.py` usa como proxy de historia disponible (R24) — no es el gate G1 real.
    """

    symbol: str
    figure: SymbolFigure | None
    min_full_sessions: int
