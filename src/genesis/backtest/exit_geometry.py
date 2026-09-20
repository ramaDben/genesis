"""Geometría de salida (`ExitGeometry`), capa 3 (Change #109).

Reemplaza al contenedor de riesgo previo (`risk_profile.py`, eliminado): la mitad
"restricción de la casa" migró a
`genesis.data.house_rule.HouseRule` (capa 1); esto es lo que queda, la parte que
**el genoma gobierna, sin cotas** (`design.md` §1.4). No tiene valores por defecto:
un genoma que omita una clave del trailing debe fallar en el compilador (`schema.py`),
no heredar un número en silencio por la puerta de este contenedor.
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path

from genesis.backtest.errors import BacktestConfigError

CONFIG_VERSION: str = "genesis-backtest-exit-geometry/1"

_CONFIG_PACKAGE = "genesis.backtest"
_CONFIG_RESOURCE = "exit_geometry.json"


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
            raise BacktestConfigError(
                f"trailing_lookback debe ser >= 1, recibido: {self.trailing_lookback!r}"
            )
        if self.trailing_atr_mult <= 0.0:
            raise BacktestConfigError(
                f"trailing_atr_mult debe ser > 0.0, recibido: {self.trailing_atr_mult!r}"
            )


def _parse_trailing_lookback(raw: object) -> int:
    """Coerción estricta: solo un `int` real es válido (sin truthiness de `bool`).

    `bool` es subtipo de `int` en Python, así que `True`/`False` pasarían el
    `isinstance(raw, int)` desnudo y se colarían como `1`/`0`; un float no entero
    (`22.9`) se truncaría en silencio a `22`. Ambos deben fallar, no colarse.
    """
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise TypeError(f"'trailing_lookback' debe ser un entero, recibido: {raw!r}")
    return raw


def load_exit_geometry(path: Path | None = None) -> ExitGeometry:
    """Carga `ExitGeometry` desde `path`, o desde el recurso empaquetado por defecto.

    `path=None` -> recurso empaquetado `genesis.backtest/exit_geometry.json`, con
    `source=CONFIG`. Exige `config_version == "genesis-backtest-exit-geometry/1"`.
    Lanza `BacktestConfigError` con el campo faltante en el mensaje ante
    configuración inválida o incompleta (fail-fast).
    """
    if path is not None:
        raw_text = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        resource = resources.files(_CONFIG_PACKAGE).joinpath(_CONFIG_RESOURCE)
        raw_text = resource.read_text(encoding="utf-8")
        source = f"{_CONFIG_PACKAGE}/{_CONFIG_RESOURCE}"

    try:
        payload = json.loads(raw_text)
        received_version = payload.get("config_version")
        if received_version != CONFIG_VERSION:
            message = (
                f"exit_geometry.json en '{source}' con config_version inválido: "
                f"esperado {CONFIG_VERSION!r}, recibido {received_version!r}"
            )
            raise BacktestConfigError(message)
        return ExitGeometry(
            trailing_lookback=_parse_trailing_lookback(payload["trailing_lookback"]),
            trailing_atr_mult=float(payload["trailing_atr_mult"]),
            source=ExitGeometrySource.CONFIG,
        )
    except BacktestConfigError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Geometría de salida inválida/incompleta en '{source}': {exc}"
        raise BacktestConfigError(message) from exc


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
