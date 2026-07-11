"""Candidato A (CT sweep-fade, spec §2.2): `smc_engine` + diagnóstico de señal desnuda.

Este paquete **no** registra `"A"` en `CANDIDATE_REGISTRY` (ADR-D8): `smc/` y
`diagnostics.py` son módulos de análisis (estructura de mercado + núcleo estadístico
puro), no un `StrategyCandidate` ejecutable. El gatillo CT y el `risk` propio del
Candidato A quedan reservados a Issue F, condicional al veredicto del diagnóstico de
señal desnuda de este Change.
"""

from genesis.strategy.candidate_a.config import (
    CandidateAConfig,
    DiagnosticsConfig,
    SmcEngineConfig,
    load_candidate_a_config,
    load_placeholder_symbol_figures,
)
from genesis.strategy.candidate_a.diagnostics import (
    ConditionalReturnEvent,
    HorizonEdge,
    RawEdgeSummary,
    detect_ct_events,
    summarize_raw_edge,
)
from genesis.strategy.candidate_a.errors import CandidateAConfigError, SmcEngineStateError

__all__ = [
    "CandidateAConfig",
    "CandidateAConfigError",
    "ConditionalReturnEvent",
    "DiagnosticsConfig",
    "HorizonEdge",
    "RawEdgeSummary",
    "SmcEngineConfig",
    "SmcEngineStateError",
    "detect_ct_events",
    "load_candidate_a_config",
    "load_placeholder_symbol_figures",
    "summarize_raw_edge",
]
