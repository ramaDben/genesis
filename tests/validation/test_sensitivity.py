"""Tests de `sensitivity.py`: perturbación ±10%, stress de costos, acantilado (R36-R46, R52)."""

import math

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.risk_profile import RiskProfile
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.errors import SensitivityConfigError
from genesis.validation.sensitivity import (
    CostStressOutcome,
    PerturbationOutcome,
    SensitivityConfig,
    SensitivityResult,
    _relative_drop_and_cliff,
    run_sensitivity,
)
from genesis.validation.wfa import WfaResult


def test_sensitivity_config_defaults_validos() -> None:
    config = SensitivityConfig()
    assert config.perturbation_fraction == 0.10
    assert config.cost_stress_multipliers == (1.5, 2.0)
    assert config.cliff_pf_floor == 1.0
    assert config.cliff_relative_drop_threshold == 0.5


def test_sensitivity_config_multiplier_menor_o_igual_a_uno_lanza_error() -> None:
    with pytest.raises(SensitivityConfigError):
        SensitivityConfig(cost_stress_multipliers=(1.0, 2.0))


def test_sensitivity_config_relative_drop_threshold_fuera_de_rango_lanza_error() -> None:
    with pytest.raises(SensitivityConfigError):
        SensitivityConfig(cliff_relative_drop_threshold=0.0)
    with pytest.raises(SensitivityConfigError):
        SensitivityConfig(cliff_relative_drop_threshold=1.5)


def test_sensitivity_config_pf_floor_no_positivo_lanza_error() -> None:
    with pytest.raises(SensitivityConfigError):
        SensitivityConfig(cliff_pf_floor=0.0)


@pytest.mark.unit
def test_cliff_definition() -> None:
    """R52: `pf <= cliff_pf_floor` o `relative_drop >= threshold` -> `is_cliff=True`."""
    config = SensitivityConfig()

    # Caso 1: profit_factor <= cliff_pf_floor (1.0).
    relative_drop, is_cliff = _relative_drop_and_cliff(2.0, 0.8, config)
    assert is_cliff is True

    # Caso 2: relative_drop >= cliff_relative_drop_threshold (0.5), PF aún > floor.
    relative_drop, is_cliff = _relative_drop_and_cliff(2.0, 0.9, config)
    assert relative_drop >= 0.5
    assert is_cliff is True

    # Caso 3: degradación moderada (relative_drop == 0.2), sin acantilado.
    relative_drop, is_cliff = _relative_drop_and_cliff(2.0, 1.6, config)
    assert relative_drop == pytest.approx(0.2)
    assert is_cliff is False


def test_relative_drop_baseline_cero_retorna_cero() -> None:
    """R40: `relative_drop = 0.0` si `pf_ganador == 0.0` (evita división por cero)."""
    relative_drop, _is_cliff = _relative_drop_and_cliff(0.0, 0.0, SensitivityConfig())
    assert relative_drop == 0.0


@pytest.mark.unit
def test_empty_windows_raises(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    i_frame: pd.DataFrame,
) -> None:
    """R3a: `wfa_result.windows` vacío -> `SensitivityConfigError`."""
    empty_wfa_result = WfaResult(
        candidate_id="B",
        symbol="US500",
        config_version="genesis-validation/1",
        windows=(),
        oos_ledger_cosido=None,  # ty: ignore[invalid-argument-type]
        wfe=0.0,
        n_windows=0,
        n_trials_signal_total=0,
        n_trials_execution_total=0,
        seed=0,
    )
    with pytest.raises(SensitivityConfigError):
        run_sensitivity(
            empty_wfa_result,
            i_frame,
            "US500",
            firm_profile_fixture,
            risk_profile_fixture,
            symbol_figure_fixture,
            funnel_config_fixture,
            costs_config_fixture,
            [],
            tick_store_fixture,
            None,
            100_000.0,
        )


def test_outcome_counts(
    wfa_result_fixture: WfaResult,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    i_frame: pd.DataFrame,
) -> None:
    """R39/R41/R42: 6 `PerturbationOutcome` (3 ejes x 2 direcciones) + 2 `CostStressOutcome`."""
    result = run_sensitivity(
        wfa_result_fixture,
        i_frame,
        "US500",
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        funnel_config_fixture,
        costs_config_fixture,
        [],
        tick_store_fixture,
        None,
        100_000.0,
    )

    assert isinstance(result, SensitivityResult)
    assert len(result.perturbations) == 6
    assert {p.axis for p in result.perturbations} == {"n_minutes", "atr_stop_frac", "risk_pct"}
    assert {p.direction for p in result.perturbations} == {-1, 1}
    assert all(isinstance(p, PerturbationOutcome) for p in result.perturbations)
    assert math.isfinite(result.baseline_profit_factor)
    for perturbation in result.perturbations:
        assert math.isfinite(perturbation.profit_factor)
        assert math.isfinite(perturbation.relative_drop)

    assert len(result.cost_stress) == 2
    assert {c.multiplier for c in result.cost_stress} == {1.5, 2.0}
    assert all(isinstance(c, CostStressOutcome) for c in result.cost_stress)
    for cost_outcome in result.cost_stress:
        assert math.isfinite(cost_outcome.profit_factor)

    assert result.has_cliff == any(p.is_cliff for p in result.perturbations)
    assert result.candidate_id == wfa_result_fixture.candidate_id
    assert result.symbol == "US500"


def test_determinism(
    wfa_result_fixture: WfaResult,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    i_frame: pd.DataFrame,
) -> None:
    """R49: dos invocaciones independientes -> `SensitivityResult` bit-idéntico."""

    def _run() -> SensitivityResult:
        return run_sensitivity(
            wfa_result_fixture,
            i_frame,
            "US500",
            firm_profile_fixture,
            risk_profile_fixture,
            symbol_figure_fixture,
            funnel_config_fixture,
            costs_config_fixture,
            [],
            tick_store_fixture,
            None,
            100_000.0,
        )

    result1 = _run()
    result2 = _run()
    assert result1 == result2


def test_run_sensitivity_rg_evals() -> None:
    """R37/R41/R43/R46/R63: presencia/ausencia normativa de patrones en el código fuente."""
    import genesis.validation.sensitivity as module

    with open(module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "def run_sensitivity" in content
    assert "stress=" in content
    assert "volume_proxy" not in content
    assert "proxy_volumen" not in content
    assert "import scipy" not in content
    assert "import statsmodels" not in content
    assert "import matplotlib" not in content
    assert "import quantstats" not in content
    assert "multiprocessing" not in content
    assert "concurrent.futures" not in content
