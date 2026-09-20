"""Geometría de salida (`ExitGeometry`), capa 2 (Change #109).

Reemplaza al contenedor de riesgo previo (`risk_profile.py`, eliminado): la mitad
"restricción de la casa" migró a `genesis.data.house_rule.HouseRule` (capa 1); esto
es lo que queda, la parte que **el genoma gobierna, sin cotas** (`design.md` §1.4).
No tiene valores por defecto: un genoma que omita una clave del trailing debe fallar
en el compilador (`schema.py`), no heredar un número en silencio por la puerta de
este contenedor.

Por qué vive en capa 2 y no en capa 3
-------------------------------------
La tesis del Change #109 es que la geometría de salida **es un parámetro de la
estrategia** (y la restricción de la casa es de la firma). Si el genoma la gobierna,
el value object es un artefacto de estrategia y pertenece acá.

Tenerlo en capa 3 obligaba a `genome/compiler.py` —capa 2, que **construye** la
instancia— a importar `genesis.backtest` en tiempo de ejecución, cerrando un ciclo
real entre paquetes: `genesis.backtest` ya depende de `genesis.strategy`
(`simulator.py`, `ledger.py`, `exit_policy.py`, `clock.py`). El truco de
`TYPE_CHECKING` que usa `factories.py` no servía ahí, porque una clase importada
sólo para chequeo de tipos no se puede instanciar.

Lo que **no** baja de capa 3: `load_exit_geometry`, su `CONFIG_VERSION` y el recurso
empaquetado `exit_geometry.json` siguen en `genesis.backtest.exit_geometry`. Cargar
una ficha de configuración es mecanismo de backtest, no de estrategia, y dejarlo allá
mantiene `BacktestConfigError` como el error que ve quien carga.
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from genesis.strategy.errors import ExitGeometryConfigError


class ExitGeometrySource(StrEnum):
    """Procedencia del valor efectivo de la geometría (no es un parámetro, D8)."""

    GENOME = "genome"
    CONFIG = "config"


@dataclass(frozen=True, slots=True)
class ExitGeometry:
    """Geometría de salida Chandelier: campos posicionales y obligatorios, sin `= valor`.

    `__post_init__` conserva exactamente las dos guardas de estado imposible que
    tenía el contenedor de riesgo previo (`trailing_lookback >= 1`, `trailing_atr_mult > 0.0`) y
    ninguna más: la frontera es *imposible* vs *indeseable*, y lo indeseable lo
    deciden los gates, no este contenedor (R9).
    """

    trailing_lookback: int
    trailing_atr_mult: float
    source: ExitGeometrySource

    def __post_init__(self) -> None:
        if self.trailing_lookback < 1:
            raise ExitGeometryConfigError(
                f"trailing_lookback debe ser >= 1, recibido: {self.trailing_lookback!r}"
            )
        if self.trailing_atr_mult <= 0.0:
            raise ExitGeometryConfigError(
                f"trailing_atr_mult debe ser > 0.0, recibido: {self.trailing_atr_mult!r}"
            )


def exit_geometry_hash(geometry: ExitGeometry) -> str:
    """Hash `sha256` canónico de la geometría sobre JSON ordenado (R4, R14).

    `source` es procedencia, no parámetro, y **no** entra en el hash: dos
    geometrías con el mismo `trailing_lookback`/`trailing_atr_mult` producen el
    mismo hash sin importar si vinieron del genoma o de la config.
    """
    canonical = {
        "trailing_atr_mult": geometry.trailing_atr_mult,
        "trailing_lookback": geometry.trailing_lookback,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
