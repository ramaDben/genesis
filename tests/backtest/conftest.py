"""Fixtures compartidas de la suite `tests/backtest/` (capa 3: backtest, R51).

Reutiliza `load_firm_profile()`/`load_exit_geometry()`/`load_costs_config()` y el
`SymbolFigure` fake de `tests/data/fakes.py`; no duplica su construcción (R51).
"""

from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig, load_costs_config
from genesis.backtest.exit_geometry import ExitGeometry, load_exit_geometry
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.symbols import SymbolFigure
from tests.data.fakes import _default_symbol_figure

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_m1_path() -> Path:
    """Ruta al fixture CSV de velas M1 sintético con ruptura de rango (Candidato B)."""
    return _FIXTURES_DIR / "sample_m1.csv"


@pytest.fixture
def sample_m1_frame(sample_m1_path: Path) -> pd.DataFrame:
    """Frame crudo M1 determinista con ruptura de rango, listo para `iter_bars` (R51)."""
    return pd.read_csv(sample_m1_path, parse_dates=["timestamp"])


@pytest.fixture
def firm_profile_fixture() -> FirmProfile:
    """Ficha de firma por defecto (`load_firm_profile()`), sin duplicar su construcción."""
    return load_firm_profile()


@pytest.fixture
def exit_geometry_fixture() -> ExitGeometry:
    """Geometría de salida por defecto (`load_exit_geometry()`)."""
    return load_exit_geometry()


@pytest.fixture
def symbol_figure_fixture() -> SymbolFigure:
    """Ficha extendida de símbolo por defecto, reutilizando `tests/data/fakes.py`."""
    return _default_symbol_figure("US500")


@pytest.fixture
def costs_config_fixture() -> CostsConfig:
    """Configuración de costos por defecto (`load_costs_config()`)."""
    return load_costs_config()


@pytest.fixture
def tick_store_fixture(tmp_path: Path) -> RawParquetStore:
    """`RawParquetStore` vacío en `tmp_path`; los tests pueblan chunks con `build_tick_chunk`."""
    return RawParquetStore(tmp_path / "raw")
