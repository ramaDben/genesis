"""Capa 2 — estrategia: contrato plugin, Inspector compartido, candidatos A/B/C."""

from genesis.strategy.clock import BarClock
from genesis.strategy.contract import (
    CANDIDATE_REGISTRY,
    CONFIG_VERSION,
    Direction,
    EntryIntent,
    StrategyCandidate,
    register_candidate,
)
from genesis.strategy.errors import GenesisStrategyError, LookaheadError
from genesis.strategy.inspector import (
    InspectorFunnelConfig,
    InspectorVerdict,
    RejectionReason,
    inspect,
)

__all__ = [
    "CANDIDATE_REGISTRY",
    "CONFIG_VERSION",
    "BarClock",
    "Direction",
    "EntryIntent",
    "GenesisStrategyError",
    "InspectorFunnelConfig",
    "InspectorVerdict",
    "LookaheadError",
    "RejectionReason",
    "StrategyCandidate",
    "inspect",
    "register_candidate",
]
