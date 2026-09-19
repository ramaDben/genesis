"""Tests de la API pública re-exportada por `genesis.backtest.__init__` (R60)."""

import pytest

import genesis.backtest as backtest_pkg

pytestmark = pytest.mark.unit

_EXPECTED_ALL = {
    "GenesisBacktestError",
    "SessionBoundaryError",
    "BacktestConfigError",
    "CONFIG_VERSION",
    "SimulationClock",
    "ExitGeometry",
    "ExitGeometrySource",
    "load_exit_geometry",
    "exit_geometry_hash",
    "ExhaustionPolicy",
    "iter_ticks",
    "Simulator",
    "run_backtest",
    "RiskLevelsProvider",
    "BreachKind",
    "BreachEvent",
    "Ledger",
    "reconstruct_equity_series",
}


def test_all_contiene_la_superficie_curada_minima() -> None:
    assert set(backtest_pkg.__all__) >= _EXPECTED_ALL


def test_todos_los_nombres_de_all_son_importables() -> None:
    for name in backtest_pkg.__all__:
        assert hasattr(backtest_pkg, name), f"'{name}' está en __all__ pero no es importable"


def test_helpers_privados_no_se_re_exportan() -> None:
    leaked_names = {"_day_window", "_resolve_fill", "_resolve_entry_fill"}
    assert not (leaked_names & set(backtest_pkg.__all__))
