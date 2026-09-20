"""Carga de `ExitGeometry` desde configuración empaquetada, capa 3 (Change #109).

El value object vive en capa 2 (`genesis.strategy.exit_geometry`): la geometría de
salida es un parámetro de la estrategia, y tenerlo acá obligaba a `genome/compiler.py`
a importar capa 3 en runtime, cerrando un ciclo real entre paquetes (§1.2).

Lo que se queda en capa 3 es el **mecanismo de carga**: leer el recurso empaquetado
`exit_geometry.json`, exigir su `config_version` y producir una geometría con
`source=CONFIG`. Ese fallback es del simulador, no del motor de estrategia.

`ExitGeometry`, `ExitGeometrySource` y `exit_geometry_hash` se re-exportan desde acá
para no romper a ningún consumidor que ya los importaba de `genesis.backtest`
(`backtest/__init__.py` los lista en `__all__`, R60).
"""

import json
from importlib import resources
from pathlib import Path

from genesis.backtest.errors import BacktestConfigError
from genesis.strategy.errors import ExitGeometryConfigError
from genesis.strategy.exit_geometry import (
    ExitGeometry,
    ExitGeometrySource,
    exit_geometry_hash,
)

__all__ = [
    "CONFIG_VERSION",
    "ExitGeometry",
    "ExitGeometrySource",
    "exit_geometry_hash",
    "load_exit_geometry",
]

CONFIG_VERSION: str = "genesis-backtest-exit-geometry/1"

_CONFIG_PACKAGE = "genesis.backtest"
_CONFIG_RESOURCE = "exit_geometry.json"


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

    Las guardas de estado imposible del contenedor viven en capa 2 y lanzan
    `ExitGeometryConfigError`; acá se traducen a `BacktestConfigError` para que el
    contrato de esta capa no cambie: quien carga una ficha sigue viendo el error de
    configuración de capa 3, sin enterarse de dónde vive el dataclass.
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
    except (
        AttributeError,
        ExitGeometryConfigError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        message = f"Geometría de salida inválida/incompleta en '{source}': {exc}"
        raise BacktestConfigError(message) from exc
