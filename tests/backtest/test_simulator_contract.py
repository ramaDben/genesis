"""Tests del puerto `RiskLevelsProvider` y la construcción de `Simulator` (R20, R21, R40)."""

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.risk_profile import RiskProfile
from genesis.backtest.simulator import RiskLevelsProvider, Simulator
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeCandidateNoRisk, FakeRiskCandidate

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=1.0, min_lot=0.01, max_lot=10.0)
_UNSET = object()


def _build_kwargs(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
    *,
    symbol: str = "US500",
    costs_config: object = _UNSET,
) -> dict:
    return {
        "symbol": symbol,
        "firm_profile": firm_profile_fixture,
        "risk_profile": risk_profile_fixture,
        "figure": symbol_figure_fixture,
        "funnel_config": _FUNNEL_CONFIG,
        "costs_config": costs_config_fixture if costs_config is _UNSET else costs_config,
        "news_events": [],
        "tick_store": None,
        "starting_balance": 100_000.0,
        "dataset_hash": "test-dataset-hash",
    }


def test_risk_levels_provider_es_runtime_checkable() -> None:
    assert isinstance(FakeRiskCandidate(), RiskLevelsProvider) is True
    assert isinstance(FakeCandidateNoRisk(), RiskLevelsProvider) is False


def test_simulator_lanza_backtest_config_error_si_candidato_no_implementa_risk_levels(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    kwargs = _build_kwargs(
        firm_profile_fixture, risk_profile_fixture, symbol_figure_fixture, costs_config_fixture
    )
    with pytest.raises(BacktestConfigError):
        Simulator(FakeCandidateNoRisk(), **kwargs)


def test_simulator_construye_correctamente_con_candidato_valido(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    kwargs = _build_kwargs(
        firm_profile_fixture, risk_profile_fixture, symbol_figure_fixture, costs_config_fixture
    )
    simulator = Simulator(FakeRiskCandidate(), **kwargs)
    assert simulator is not None


def test_simulator_lanza_backtest_config_error_si_costs_config_invalido(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    kwargs = _build_kwargs(
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
        costs_config=None,  # type: ignore[arg-type]
    )
    with pytest.raises(BacktestConfigError):
        Simulator(FakeRiskCandidate(), **kwargs)


def test_simulator_lanza_backtest_config_error_si_symbol_fuera_de_sessions(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    kwargs = _build_kwargs(
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
        symbol="NOPE",
    )
    with pytest.raises(BacktestConfigError):
        Simulator(FakeRiskCandidate(), **kwargs)
