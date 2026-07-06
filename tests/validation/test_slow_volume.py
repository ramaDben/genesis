"""Test de volumen realista del WFA completo: `WfaWindowConfig`/`GridConfig` por defecto (R59).

Marcado `pytest.mark.slow`: ejerce las 27 combinaciones de ejecución × N ventanas
sobre >=378 `trading_day` (`fixtures/long_m1_generator.py`), separado de la suite
rápida por defecto. `@pytest.mark.timeout(180)` sobrescribe el timeout global de
`pyproject.toml` (30s): un run completo con el grid/ventana normativos tarda del
orden de 20-30s en esta máquina de referencia (loop secuencial puro Python, R32).
"""

import math

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.risk_profile import RiskProfile
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import IS_WINDOW_TRADING_DAYS, OOS_WINDOW_TRADING_DAYS
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

pytestmark = [pytest.mark.slow, pytest.mark.timeout(180)]


def test_wfa_volumen_realista_grid_completo_y_ventana_por_defecto(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
) -> None:
    """R59: `WfaWindowConfig()`/`GridConfig()` por defecto sobre un frame de >=378 días."""
    n_trading_days = IS_WINDOW_TRADING_DAYS + OOS_WINDOW_TRADING_DAYS
    frame = generate_long_m1_frame("US500", n_trading_days=n_trading_days, seed=0)

    result = run_wfa(
        "B",
        "US500",
        frame,
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
        seed=0,
    )

    assert result.n_windows >= 1
    for window in result.windows:
        assert window.n_trials_signal == 9
        assert window.n_trials_execution == 27
    assert math.isfinite(result.wfe)
    assert len(result.oos_ledger_cosido.entries) > 0
