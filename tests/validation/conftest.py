"""Fixtures compartidas de la suite `tests/validation/` (capa 4: validación, R53).

Reutiliza `load_firm_profile()`/`load_risk_profile()`/`load_costs_config()` y el
`SymbolFigure` fake de `tests/data/fakes.py` (patrón `tests/backtest/conftest.py`);
no duplica su construcción.
"""

from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig, load_costs_config
from genesis.backtest.risk_profile import RiskProfile, load_risk_profile
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.window_config import WfaWindowConfig
from tests.data.fakes import _default_symbol_figure
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

_BACKTEST_FIXTURES_DIR = Path(__file__).parent.parent / "backtest" / "fixtures"


@pytest.fixture
def firm_profile_fixture() -> FirmProfile:
    """Ficha de firma por defecto (`load_firm_profile()`), sin duplicar su construcción."""
    return load_firm_profile()


@pytest.fixture
def risk_profile_fixture() -> RiskProfile:
    """Ficha de riesgo por defecto (`load_risk_profile()`)."""
    return load_risk_profile()


@pytest.fixture
def symbol_figure_fixture() -> SymbolFigure:
    """Ficha extendida de símbolo por defecto, reutilizando `tests/data/fakes.py`."""
    return _default_symbol_figure("US500")


@pytest.fixture
def costs_config_fixture() -> CostsConfig:
    """Configuración de costos por defecto (`load_costs_config()`)."""
    return load_costs_config()


@pytest.fixture
def funnel_config_fixture() -> InspectorFunnelConfig:
    """Embudo Inspector permisivo para datos sintéticos (decisión de fixture, no de producción).

    `lot_step_tolerance` amplio evita que el `sizing_hint` sin redondear del
    Candidato B (RI-E6, comportamiento heredado de Issue E) rechace la mayoría de
    las señales sintéticas por no caer exactamente en un múltiplo de
    `volume_step` — la fórmula/gate normativos de `inspect()` no se modifican, solo
    el parámetro de la ficha de test.
    """
    return InspectorFunnelConfig(
        min_rr=0.1, min_lot=0.01, max_lot=10_000.0, lot_step_tolerance=1_000.0
    )


@pytest.fixture
def tick_store_fixture(tmp_path: Path) -> RawParquetStore:
    """`RawParquetStore` vacío en `tmp_path`, reutilizado también como `dataset_store` (R23)."""
    return RawParquetStore(tmp_path / "raw")


@pytest.fixture
def reduced_window_config() -> WfaWindowConfig:
    """`WfaWindowConfig` reducido para tests rápidos de troceo/grid (is=4, oos=2, step=2)."""
    return WfaWindowConfig(is_window_trading_days=4, oos_window_trading_days=2, step_trading_days=2)


@pytest.fixture
def sample_m1_frame() -> pd.DataFrame:
    """Frame crudo M1 corto (`tests/backtest/fixtures/sample_m1.csv`), 1 solo día — solo troceo."""
    return pd.read_csv(_BACKTEST_FIXTURES_DIR / "sample_m1.csv", parse_dates=["timestamp"])


@pytest.fixture
def short_wfa_frame() -> pd.DataFrame:
    """Frame M1 sintético de 10 días hábiles (`reduced_window_config` necesita >= 6)."""
    return generate_long_m1_frame("US500", n_trading_days=10, seed=1)
