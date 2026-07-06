"""Tests del grid IS, selección DSR-IS, congelamiento OOS y WFE (R23-R35, R55)."""

import math

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.risk_profile import RiskProfile
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b import candidate as candidate_b_module
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.errors import WfaConfigError
from genesis.validation.wfa import WfaResult, run_wfa
from genesis.validation.window_config import GridConfig, WfaWindowConfig
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

pytestmark = pytest.mark.unit


def _run(
    frame: pd.DataFrame,
    *,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    symbol_figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    dataset_store: RawParquetStore,
    window_config: WfaWindowConfig,
    seed: int = 42,
) -> WfaResult:
    return run_wfa(
        "B",
        "US500",
        frame,
        firm_profile,
        risk_profile,
        symbol_figure,
        funnel_config,
        costs_config,
        [],
        dataset_store,
        None,
        100_000.0,
        window_config=window_config,
        seed=seed,
    )


def test_run_wfa_reporta_conteos_mecanicos_9_27(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    result = _run(
        short_wfa_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )
    assert result.n_windows >= 1
    for window in result.windows:
        assert window.n_trials_signal == 9
        assert window.n_trials_execution == 27
    assert result.n_trials_signal_total == result.n_windows * 9
    assert result.n_trials_execution_total == result.n_windows * 27


def test_run_wfa_wfe_finito_y_oos_cosido_no_vacio(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    result = _run(
        short_wfa_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )
    assert math.isfinite(result.wfe)
    assert len(result.oos_ledger_cosido.entries) > 0


def test_run_wfa_no_usa_load_candidate_b_config() -> None:
    """R24: `wfa.py` instancia `CandidateB` con kwargs directos, sin `load_candidate_b_config`."""
    import genesis.validation.wfa as wfa_module

    source = wfa_module.__file__
    with open(source, encoding="utf-8") as handle:
        content = handle.read()
    assert "CandidateB(" in content
    assert "load_candidate_b_config" not in content
    assert "multiprocessing" not in content
    assert "concurrent.futures" not in content


def test_run_wfa_cuenta_instancias_candidateb_por_ventana(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R55: ninguna ventana instancia más de 27 `CandidateB` en la fase de grid IS."""
    counts: list[int] = [0]
    original_init = candidate_b_module.CandidateB.__init__

    def _counting_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        counts[0] += 1
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(candidate_b_module.CandidateB, "__init__", _counting_init)

    result = _run(
        short_wfa_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )
    # 27 combos IS + 1 combo OOS congelado por ventana == 28.
    assert counts[0] == result.n_windows * 28


def test_run_wfa_ventana_inviable_lanza_wfa_config_error(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
) -> None:
    """R27: si las 9 configs de señal quedan bajo MIN_TRADES_IS, se lanza WfaConfigError."""
    tiny_window_config = WfaWindowConfig(
        is_window_trading_days=2, oos_window_trading_days=1, step_trading_days=1
    )
    frame = generate_long_m1_frame("US500", n_trading_days=4, seed=3)
    with pytest.raises(WfaConfigError):
        _run(
            frame,
            firm_profile=firm_profile_fixture,
            risk_profile=risk_profile_fixture,
            symbol_figure=symbol_figure_fixture,
            funnel_config=funnel_config_fixture,
            costs_config=costs_config_fixture,
            dataset_store=tick_store_fixture,
            window_config=tiny_window_config,
        )


def test_run_wfa_oos_cosido_no_contiene_trades_is(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R62: `oos_ledger_cosido` solo concatena `WindowResult.oos_ledger`, nunca runs IS."""
    result = _run(
        short_wfa_frame,
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        symbol_figure=symbol_figure_fixture,
        funnel_config=funnel_config_fixture,
        costs_config=costs_config_fixture,
        dataset_store=tick_store_fixture,
        window_config=reduced_window_config,
    )
    total_oos_entries = sum(len(window.oos_ledger.entries) for window in result.windows)
    assert len(result.oos_ledger_cosido.entries) == total_oos_entries


def test_grid_config_personalizado_respeta_presupuesto() -> None:
    grid = GridConfig()
    assert len(grid.execution_combos()) == 27
    assert len(grid.signal_configs()) == 9
