"""Test de volumen realista de `build_signal_trial_matrix` (R54, Rg-2).

Marcado `pytest.mark.slow`: ejerce el re-run más costoso de Issue I (9
configuraciones de señal x N ventanas, todas x 3 `risk_pct_levels`), separado
de la suite rápida por defecto. Usa una geometría de ventana "realista" a
escala mensual (`is=60`, `oos=30`, `step=30` días hábiles — ~3/1.5 meses
bursátiles) en vez de los defaults anuales de `WfaWindowConfig()`
(`is=252`/`oos=126`): el propósito de este test es acotar el costo
combinatorio 9×N×3 en volumen no-trivial (Rg-2), no reproducir exactamente la
escala anual de `wfa.py` (cuyo propio test `slow` de H ya cubre esa escala
para el grid IS/OOS completo, `tests/validation/test_slow_volume.py`) —
acotar aquí a 190 días hábiles mantiene el runtime dentro de un
`pytest.mark.timeout` razonable sin perder la propiedad de volumen relevante
para R54 (>= 4 ventanas, el mínimo de CSCV).
"""

import math

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.profile import FirmProfile
from genesis.data.store import RawParquetStore
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.dsr_pbo import build_signal_trial_matrix
from genesis.validation.window_config import GridConfig, WfaWindowConfig
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

pytestmark = [pytest.mark.slow, pytest.mark.timeout(180)]

_REALISTIC_WINDOW_CONFIG = WfaWindowConfig(
    is_window_trading_days=60, oos_window_trading_days=30, step_trading_days=30
)
_N_TRADING_DAYS = 190
"""`>= 60 + 30 + 3*30 = 180`: garantiza `n_windows >= 4` (precondición de CSCV, Rg-3)."""


def test_build_signal_trial_matrix_volumen_realista(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
) -> None:
    """R54: 9 configs x N ventanas x 3 `risk_pct`, `n_windows` esperado y DSR-IS finitos."""
    frame = generate_long_m1_frame("US500", n_trading_days=_N_TRADING_DAYS, seed=9)

    matrix = build_signal_trial_matrix(
        "B",
        "US500",
        frame,
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
        window_config=_REALISTIC_WINDOW_CONFIG,
        grid_config=GridConfig(),
    )

    assert matrix.n_windows >= 4
    assert len(matrix.signal_configs) == 9
    assert len(matrix.dsr_is_by_window) == matrix.n_windows
    for window_map in matrix.dsr_is_by_window:
        assert set(window_map) == set(matrix.signal_configs)
        assert any(math.isfinite(value) for value in window_map.values())
