"""Tests de `ExitGeometry` (capa 3, Change #109).

Recibe, por redistribución declarada en `tasks.md` DT-3 (opción a), la mitad
"geometría" de los tests que vivían en `tests/backtest/test_risk_profile.py`: el
loader, las dos guardas de estado imposible sobre trailing y el criterio A23 de
sensibilidad del hash.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.exit_geometry import (
    ExitGeometry,
    ExitGeometrySource,
    exit_geometry_hash,
    load_exit_geometry,
)
from genesis.strategy.errors import ExitGeometryConfigError

pytestmark = pytest.mark.unit


def test_exit_geometry_es_frozen() -> None:
    geometry = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(geometry, "trailing_atr_mult", 1.0)  # noqa: B010


def test_u6b_exit_geometry_sin_argumentos_lanza_type_error() -> None:
    """Eval U6b: sin defaults -> construir sin argumentos es un `TypeError`."""
    with pytest.raises(TypeError):
        ExitGeometry(**{})  # type: ignore[missing-argument]


def test_u6b_json_sin_trailing_atr_mult_nombra_el_campo(tmp_path: Path) -> None:
    incomplete = tmp_path / "exit_geometry.json"
    incomplete.write_text(
        json.dumps(
            {
                "config_version": "genesis-backtest-exit-geometry/1",
                "trailing_lookback": 22,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError, match="trailing_atr_mult"):
        load_exit_geometry(incomplete)


def test_load_exit_geometry_config_incompleta_falta_lookback(tmp_path: Path) -> None:
    incomplete = tmp_path / "exit_geometry.json"
    incomplete.write_text(
        json.dumps(
            {
                "config_version": "genesis-backtest-exit-geometry/1",
                "trailing_atr_mult": 3.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError, match="trailing_lookback"):
        load_exit_geometry(incomplete)


def test_hallazgo3_load_exit_geometry_raiz_no_dict_lanza_backtest_config_error(
    tmp_path: Path,
) -> None:
    """Un JSON raíz que es una lista no debe escapar como `AttributeError` crudo."""
    path = tmp_path / "lista.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(BacktestConfigError):
        load_exit_geometry(path)


def test_load_exit_geometry_default_empaquetado() -> None:
    geometry = load_exit_geometry()
    assert geometry.trailing_lookback >= 1
    assert geometry.trailing_atr_mult > 0.0
    assert geometry.source == ExitGeometrySource.CONFIG


def test_u6_lookback_cero_lanza_exit_geometry_config_error() -> None:
    """U6, construcción directa: la guarda vive en capa 2 y lanza su error de capa 2.

    El contenedor se mudó a `genesis.strategy.exit_geometry` (§1.2), así que ya no
    puede lanzar `BacktestConfigError` sin reimportar capa 3. Quien carga desde
    configuración sí sigue viendo `BacktestConfigError` — ver el test de traducción.
    """
    with pytest.raises(ExitGeometryConfigError, match="trailing_lookback"):
        ExitGeometry(trailing_lookback=0, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG)


def test_u6_mult_cero_lanza_exit_geometry_config_error() -> None:
    with pytest.raises(ExitGeometryConfigError, match="trailing_atr_mult"):
        ExitGeometry(trailing_lookback=22, trailing_atr_mult=0.0, source=ExitGeometrySource.CONFIG)


def test_u6_load_traduce_el_error_de_capa_2_a_backtest_config_error(tmp_path: Path) -> None:
    """La costura entre capas: `load_exit_geometry` no deja escapar el error de capa 2.

    Es el punto exacto donde la mudanza del contenedor podría romper el contrato de
    capa 3 sin que ningún otro test se entere.
    """
    path = tmp_path / "exit_geometry.json"
    path.write_text(
        json.dumps(
            {
                "config_version": "genesis-backtest-exit-geometry/1",
                "trailing_lookback": 0,
                "trailing_atr_mult": 3.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError, match="trailing_lookback"):
        load_exit_geometry(path)


def test_u6_mult_alto_sin_cota_construye_y_conserva_el_valor() -> None:
    geometry = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=50.0, source=ExitGeometrySource.CONFIG
    )
    assert geometry.trailing_atr_mult == 50.0


def test_exit_geometry_hash_es_determinista() -> None:
    geometry = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )
    assert exit_geometry_hash(geometry) == exit_geometry_hash(geometry)


def test_criterio_a23_sensibilidad_hash_a_lookback_y_mult() -> None:
    """Criterio A23: mover `trailing_lookback` o `trailing_atr_mult` cambia el hash."""
    base = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )
    cambio_lookback = ExitGeometry(
        trailing_lookback=23, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )
    cambio_mult = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.5, source=ExitGeometrySource.CONFIG
    )
    identico = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )

    assert exit_geometry_hash(base) != exit_geometry_hash(cambio_lookback)
    assert exit_geometry_hash(base) != exit_geometry_hash(cambio_mult)
    assert exit_geometry_hash(cambio_lookback) != exit_geometry_hash(cambio_mult)
    assert exit_geometry_hash(base) == exit_geometry_hash(identico)


def test_exit_geometry_hash_no_depende_de_source() -> None:
    """`source` es procedencia, no parámetro: no debe entrar en el hash de geometría."""
    from_config = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.CONFIG
    )
    from_genome = ExitGeometry(
        trailing_lookback=22, trailing_atr_mult=3.0, source=ExitGeometrySource.GENOME
    )
    assert exit_geometry_hash(from_config) == exit_geometry_hash(from_genome)


def test_hallazgo_trailing_lookback_bool_no_se_cuela_como_entero(tmp_path: Path) -> None:
    """`bool` es subtipo de `int`: `true` no debe colarse silenciosamente como `1`."""
    path = tmp_path / "exit_geometry.json"
    path.write_text(
        json.dumps(
            {
                "config_version": "genesis-backtest-exit-geometry/1",
                "trailing_lookback": True,
                "trailing_atr_mult": 3.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError, match="trailing_lookback"):
        load_exit_geometry(path)


def test_hallazgo_trailing_lookback_float_no_entero_no_se_trunca(tmp_path: Path) -> None:
    """Un float no entero (`22.9`) no debe truncarse en silencio a `22`."""
    path = tmp_path / "exit_geometry.json"
    path.write_text(
        json.dumps(
            {
                "config_version": "genesis-backtest-exit-geometry/1",
                "trailing_lookback": 22.9,
                "trailing_atr_mult": 3.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError, match="trailing_lookback"):
        load_exit_geometry(path)


def test_no_hay_defaults_silenciosos_en_el_codigo_fuente() -> None:
    """Eval de no-regresión: sin `trailing_lookback: int = ` / `trailing_atr_mult: float = `.

    La ruta apunta a capa 2, que es donde el dataclass declara sus campos desde que
    `ExitGeometry` bajó de `genesis.backtest`. Leer el archivo viejo dejaba la
    aserción vacuamente verdadera: pasaba siempre, sin importar lo que hubiera en el
    archivo real, y el invariante quedaba sin red.
    """
    source = Path("src/genesis/strategy/exit_geometry.py").read_text(encoding="utf-8")

    # Guarda contra el test ciego: si los campos se mudan otra vez, esto falla
    # ruidoso en vez de dejar pasar las dos aserciones de abajo por vacuidad.
    assert "trailing_lookback: int" in source, (
        "trailing_lookback ya no se declara acá: reapuntá la ruta o esta prueba no protege nada"
    )
    assert "trailing_atr_mult: float" in source, (
        "trailing_atr_mult ya no se declara acá: reapuntá la ruta o esta prueba no protege nada"
    )

    assert "trailing_lookback: int = " not in source
    assert "trailing_atr_mult: float = " not in source
