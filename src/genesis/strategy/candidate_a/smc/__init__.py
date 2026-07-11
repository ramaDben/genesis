"""API pública de `smc_engine`: estructura de mercado del Candidato A (R97-R106).

Re-exporta la superficie curada del motor; los módulos internos (`timeframe`, `atr`,
`fractals`, `liquidity`, `sweep`, `engine`) son detalle de implementación (spec §3.10:
split no bloqueante). No importa `numpy`/`pandas` ni los paquetes de capa 3
(backtest)/capa 4 (validación) (R105, dominio puro).
"""

from genesis.strategy.candidate_a.smc.atr import IncrementalAtr
from genesis.strategy.candidate_a.smc.engine import (
    SmcEngineResult,
    SmcEngineState,
    resolve_free_path,
    update_smc_engine,
)
from genesis.strategy.candidate_a.smc.fractals import FractalDetector, Swing, SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityLevel, LiquidityMap
from genesis.strategy.candidate_a.smc.sweep import SweepState, SweepTracker, transition_sweep
from genesis.strategy.candidate_a.smc.timeframe import (
    AggregatedBar,
    BarAggregator,
    Timeframe,
    to_m1_aggregated_bar,
)

__all__ = [
    "AggregatedBar",
    "BarAggregator",
    "FractalDetector",
    "IncrementalAtr",
    "LiquidityLevel",
    "LiquidityMap",
    "SmcEngineResult",
    "SmcEngineState",
    "SweepState",
    "SweepTracker",
    "Swing",
    "SwingDirection",
    "Timeframe",
    "resolve_free_path",
    "to_m1_aggregated_bar",
    "transition_sweep",
    "update_smc_engine",
]
