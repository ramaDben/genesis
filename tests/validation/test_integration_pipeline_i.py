"""Integración del pipeline de Issue I: `run_wfa` -> purged_cv/dsr_pbo/sensitivity (R53).

Patrón `tests/validation/test_integration_pipeline.py` (H): ejercita el flujo
real de extremo a extremo sobre fixtures sintéticas pequeñas (`wfa_result_fixture`/
`i_frame`/`i_window_config`), sin mocks de las capas internas, en segundos.
"""

import math

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.dsr_pbo import build_signal_trial_matrix, run_dsr_pbo
from genesis.validation.purged_cv import PurgedCvConfig, run_purged_cv
from genesis.validation.sensitivity import run_sensitivity
from genesis.validation.wfa import WfaResult
from genesis.validation.window_config import GridConfig, WfaWindowConfig

pytestmark = pytest.mark.integration


def test_pipeline_completo_purged_cv_dsr_pbo_sensitivity(
    wfa_result_fixture: WfaResult,
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    i_window_config: WfaWindowConfig,
    i_frame: pd.DataFrame,
) -> None:
    """R53: `run_wfa` (fixture) -> `run_purged_cv` + `build_signal_trial_matrix` +
    `run_dsr_pbo` + `run_sensitivity`, artefactos no vacíos y métricas finitas."""
    purged_result = run_purged_cv(wfa_result_fixture.oos_ledger_cosido, PurgedCvConfig(n_folds=2))
    assert len(purged_result.folds) == 2
    assert purged_result.total_trades > 0
    assert all(fold.test_trade_count > 0 for fold in purged_result.folds)

    small_grid = GridConfig(n_minutes_levels=(5, 15), atr_stop_frac_levels=(0.5, 1.0))
    trial_matrix = build_signal_trial_matrix(
        "B",
        "US500",
        i_frame,
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
        window_config=i_window_config,
        grid_config=small_grid,
    )
    assert trial_matrix.n_windows == wfa_result_fixture.n_windows
    assert len(trial_matrix.dsr_is_by_window) == trial_matrix.n_windows
    assert trial_matrix.dsr_is_by_window  # no vacío

    dsr_pbo_result = run_dsr_pbo(wfa_result_fixture, trial_matrix)
    assert math.isfinite(dsr_pbo_result.dsr)
    assert math.isfinite(dsr_pbo_result.pbo)
    assert dsr_pbo_result.cscv.n_combinations > 0

    sensitivity_result = run_sensitivity(
        wfa_result_fixture,
        i_frame,
        "US500",
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
    )
    assert len(sensitivity_result.perturbations) == 6
    assert len(sensitivity_result.cost_stress) == 2
    assert math.isfinite(sensitivity_result.baseline_profit_factor)
    for perturbation in sensitivity_result.perturbations:
        assert math.isfinite(perturbation.profit_factor)
