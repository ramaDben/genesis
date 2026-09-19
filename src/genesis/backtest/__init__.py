"""Capa 3 — backtest: simulador event-driven M1, costos, ledger, métricas."""

from genesis.backtest.clock import SimulationClock
from genesis.backtest.errors import BacktestConfigError, GenesisBacktestError, SessionBoundaryError
from genesis.backtest.exit_geometry import (
    ExitGeometry,
    ExitGeometrySource,
    exit_geometry_hash,
    load_exit_geometry,
)
from genesis.backtest.ledger import (
    CONFIG_VERSION,
    BreachEvent,
    BreachKind,
    ExhaustionPolicy,
    Ledger,
    TrailingStopMoved,
    reconstruct_equity_series,
)
from genesis.backtest.simulator import RiskLevelsProvider, Simulator, run_backtest
from genesis.backtest.ticks import iter_ticks

__all__ = [
    "CONFIG_VERSION",
    "BacktestConfigError",
    "BreachEvent",
    "BreachKind",
    "ExhaustionPolicy",
    "ExitGeometry",
    "ExitGeometrySource",
    "GenesisBacktestError",
    "Ledger",
    "RiskLevelsProvider",
    "SessionBoundaryError",
    "SimulationClock",
    "Simulator",
    "TrailingStopMoved",
    "exit_geometry_hash",
    "iter_ticks",
    "load_exit_geometry",
    "reconstruct_equity_series",
    "run_backtest",
]
