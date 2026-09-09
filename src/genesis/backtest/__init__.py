"""Capa 3 — backtest: simulador event-driven M1, costos, ledger, métricas."""

from genesis.backtest.clock import SimulationClock
from genesis.backtest.errors import BacktestConfigError, GenesisBacktestError, SessionBoundaryError
from genesis.backtest.ledger import (
    CONFIG_VERSION,
    BreachEvent,
    BreachKind,
    Ledger,
    TrailingStopMoved,
    reconstruct_equity_series,
)
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile, load_risk_profile
from genesis.backtest.simulator import RiskLevelsProvider, Simulator, run_backtest
from genesis.backtest.ticks import iter_ticks

__all__ = [
    "CONFIG_VERSION",
    "BacktestConfigError",
    "BreachEvent",
    "BreachKind",
    "GenesisBacktestError",
    "Ledger",
    "MaxLossLimitKind",
    "RiskLevelsProvider",
    "RiskProfile",
    "SessionBoundaryError",
    "SimulationClock",
    "Simulator",
    "TrailingStopMoved",
    "iter_ticks",
    "load_risk_profile",
    "reconstruct_equity_series",
    "run_backtest",
]
