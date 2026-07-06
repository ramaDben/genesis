"""Fixtures compartidas de la suite `tests/validation/` (capa 4: validación, R53).

Reutiliza `load_firm_profile()`/`load_risk_profile()`/`load_costs_config()` y el
`SymbolFigure` fake de `tests/data/fakes.py` (patrón `tests/backtest/conftest.py`);
no duplica su construcción. Extensión Issue I (`design.md` §5.2): añade
`wfa_result_fixture` (garantiza `n_windows >= 4`, precondición de CSCV, Rg-3),
`oos_ledger_fixture` (trades con horizonte conocido, golden de purga+embargo y
anti-leakage) y `trial_matrix_fixture` (`SignalTrialMatrix` sintético, sin re-run,
para los tests puros de CSCV).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig, load_costs_config
from genesis.backtest.ledger import Ledger
from genesis.backtest.risk_profile import RiskProfile, load_risk_profile
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.dsr_pbo import SignalTrialMatrix
from genesis.validation.wfa import WfaResult, run_wfa
from genesis.validation.window_config import WfaWindowConfig
from tests.data.fakes import _default_symbol_figure
from tests.validation.fixtures.ledgers import build_ledger_with_trade_intervals
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


@pytest.fixture
def i_window_config() -> WfaWindowConfig:
    """`WfaWindowConfig` reducido que, junto a `i_frame`, produce `n_windows >= 4`.

    Precondición de CSCV (Rg-3, R2a): `S`/`n_splits` mínimo es `4`. Reutilizado por
    `wfa_result_fixture` y por los tests de `build_signal_trial_matrix` (T8) que
    necesitan reconstruir la misma geometría de ventanas sobre `i_frame`.
    """
    return WfaWindowConfig(is_window_trading_days=4, oos_window_trading_days=2, step_trading_days=2)


@pytest.fixture
def i_frame() -> pd.DataFrame:
    """Frame M1 sintético de 14 días hábiles: produce `n_windows == 5` con `i_window_config`."""
    return generate_long_m1_frame("US500", n_trading_days=14, seed=5)


@pytest.fixture
def wfa_result_fixture(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    i_window_config: WfaWindowConfig,
    i_frame: pd.DataFrame,
) -> WfaResult:
    """`WfaResult` con `n_windows >= 4` (precondición de CSCV, Rg-3), reutilizado por
    `test_dsr_pbo.py`/`test_sensitivity.py`/los tests de integración de Issue I.
    """
    result = run_wfa(
        "B",
        "US500",
        i_frame,
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
        window_config=i_window_config,
        seed=42,
    )
    assert result.n_windows >= 4, (
        f"wfa_result_fixture produjo n_windows={result.n_windows}, se requiere >= 4 "
        "(precondición de CSCV, Rg-3)."
    )
    return result


@pytest.fixture
def oos_ledger_fixture() -> Ledger:
    """`Ledger` OOS con 6 trades de 1 día, consecutivos, sin solape entre sí (Issue I).

    Horizonte conocido de antemano (usado por `test_purged_cv.py` para el golden de
    purga+embargo, R50b, y como base de la propiedad anti-leakage, R20/R47):
    trade `k` va de `día_k 08:00 UTC` a `día_k 20:00 UTC`, `k = 0..5`, `pnl_delta`
    alternante `+10.0`/`-5.0`.
    """
    base_day = datetime(2024, 1, 1, tzinfo=UTC)
    intervals = [
        (
            base_day + timedelta(days=k, hours=8),
            base_day + timedelta(days=k, hours=20),
            10.0 if k % 2 == 0 else -5.0,
        )
        for k in range(6)
    ]
    return build_ledger_with_trade_intervals(intervals)


@pytest.fixture
def trial_matrix_fixture() -> SignalTrialMatrix:
    """`SignalTrialMatrix` sintético (3 configs x 4 ventanas), sin ningún re-run de backtest.

    Usado por los tests puros de CSCV (`test_dsr_pbo.py`, R28/R48/R50a) — evita
    backtests reales (Rg-2). Mismos valores que el golden de
    `combinatorial_symmetric_cross_validation` (PBO calculado a mano, R50a).
    """
    config_a = (5, 0.5)
    config_b = (15, 1.0)
    config_c = (30, 1.5)
    dsr_is_by_window = [
        {config_a: 2.0, config_b: 1.0, config_c: 0.5},
        {config_a: 1.8, config_b: 1.2, config_c: 0.6},
        {config_a: 0.5, config_b: 2.0, config_c: 1.0},
        {config_a: 0.6, config_b: 1.8, config_c: 1.2},
    ]
    return SignalTrialMatrix(
        signal_configs=[config_a, config_b, config_c],
        n_windows=4,
        dsr_is_by_window=dsr_is_by_window,
    )
