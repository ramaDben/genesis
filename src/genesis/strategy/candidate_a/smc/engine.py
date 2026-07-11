"""`SmcEngineState` + `update_smc_engine` + `resolve_free_path` (R101, R104, R105).

Orquesta agregación M1→TF, ATR incremental, fractales, liquidez EQH/EQL y la FSM de
sweep sobre un único símbolo (aislamiento §2.5, mismo patrón que `CandidateB`). El
`smc_engine` es alimentado barra a barra por el **caller** (nunca por sí mismo);
`sigma_t` (para el radio de camino libre, R104) lo provee el caller desde
`common.vwap_engine`.

Módulo de dominio puro: solo stdlib + `genesis.data.store.AnnotatedBar` (capa 1) +
`genesis.strategy.{clock,errors}` + `genesis.strategy.candidate_a.smc.*` (capa 2).
**NUNCA** importa `numpy`/`pandas` ni los paquetes de capa 3 (backtest)/capa 4 (validación) (R105).
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol, runtime_checkable

from genesis.data.store import AnnotatedBar
from genesis.strategy.candidate_a.smc.atr import IncrementalAtr
from genesis.strategy.candidate_a.smc.fractals import FractalDetector, Swing, SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityLevel, LiquidityMap
from genesis.strategy.candidate_a.smc.sweep import SweepState, SweepTracker, transition_sweep
from genesis.strategy.candidate_a.smc.timeframe import (
    BarAggregator,
    Timeframe,
    to_m1_aggregated_bar,
)
from genesis.strategy.clock import BarClock

_ALL_TIMEFRAMES: tuple[Timeframe, ...] = (Timeframe.M1, Timeframe.M15, Timeframe.H1)


@runtime_checkable
class SmcEngineConfigProtocol(Protocol):
    """Superficie completa de configuración consumida por `SmcEngineState`/`resolve_free_path`.

    Superconjunto estructural de `sweep.SweepConfigProtocol` (mismo motivo: evitar
    importar `candidate_a.config` desde `smc/`); cualquier objeto que satisfaga este
    protocolo (p. ej. `SmcEngineConfig`) también satisface el protocolo más angosto de
    `transition_sweep` por subtipado estructural.
    """

    fractal_n: int
    eq_tolerance_atr: float
    sweep_tolerance_atr: float
    sweep_window_k: int
    sweep_validity_m: int
    free_path_radius_sigma: float
    ct_zscore_min: float
    atr_period: int


_MACRO_HIERARCHY: tuple[Timeframe, ...] = (Timeframe.H1, Timeframe.M15)


@dataclass(frozen=True, slots=True)
class SmcEngineResult:
    """Resultado inmutable de una llamada a `update_smc_engine`.

    Solo expone sweeps `BARRIDO`/`EXPIRADO` (los únicos "vigentes" para el diagnóstico,
    R112); no expone ningún `Swing` sin confirmar (garantía estructural de
    `FractalDetector`, R100 — este resultado ni siquiera modela `Swing`s directamente).
    """

    current_time: datetime
    atr_by_tf: Mapping[Timeframe, float]
    active_sweeps: tuple[SweepTracker, ...]
    resolved_level: LiquidityLevel | None


def resolve_free_path(
    sweep_extreme_price: float,
    direction: SwingDirection,
    sigma_t: float,
    liquidity: LiquidityMap,
    config: SmcEngineConfigProtocol,
) -> LiquidityLevel | None:
    """ "Camino libre" (R104): liquidez macro no mitigada dentro del radio de búsqueda.

    Busca en `LiquidityMap` niveles EQH/EQL de H1 y luego M15 (jerarquía H1 > M15) que
    compartan `direction` y estén dentro de `free_path_radius_sigma * sigma_t` de
    `sweep_extreme_price`. Retorna el primer nivel macro encontrado (mayor jerarquía
    primero) o `None` si no existe ninguno (camino libre: se acepta el sweep M1 directo).
    """
    radius = config.free_path_radius_sigma * sigma_t
    for timeframe in _MACRO_HIERARCHY:
        for level in liquidity.active_levels(timeframe):
            if level.direction != direction:
                continue
            if abs(level.price - sweep_extreme_price) <= radius:
                return level
    return None


class SmcEngineState:
    """Estado incremental forward-only de `smc_engine`, ligado a **un** símbolo (R101).

    Compone un `BarClock` interno, avanzado en cada `update_smc_engine`; toda consulta
    de vigencia externa (`require_valid_as_of`) pasa por `BarClock.require`, reutilizando
    `LookaheadError` sin duplicar su lógica.
    """

    def __init__(self, symbol: str, config: SmcEngineConfigProtocol) -> None:
        self.symbol = symbol
        self._config = config
        self._clock = BarClock()
        self._bar_aggregator = BarAggregator()
        self._atr: dict[Timeframe, IncrementalAtr] = {
            tf: IncrementalAtr(config.atr_period) for tf in _ALL_TIMEFRAMES
        }
        self._fractals: dict[Timeframe, FractalDetector] = {
            tf: FractalDetector(tf, config.fractal_n) for tf in _ALL_TIMEFRAMES
        }
        self._liquidity = LiquidityMap(config.eq_tolerance_atr)
        self._confirmed_swings: dict[Timeframe, list[Swing]] = {tf: [] for tf in _ALL_TIMEFRAMES}
        self._sweep_trackers: dict[int, SweepTracker] = {}

    @property
    def current_time(self) -> datetime | None:
        """`current_time` vigente del `BarClock` interno; `None` antes de la 1.ª barra."""
        return self._clock.current_time

    def require_valid_as_of(self, timestamp: datetime) -> None:
        """Lanza `LookaheadError` si `timestamp` es posterior al `current_time` vigente (R101)."""
        self._clock.require(timestamp)

    def active_swings(self, timeframe: Timeframe) -> tuple[Swing, ...]:
        """`Swing` confirmados del TF (nunca antes de su `confirmed_time`, R100)."""
        return tuple(self._confirmed_swings[timeframe])


def _atr_value_or_zero(atr: IncrementalAtr) -> float:
    return atr.value() if atr.is_warmed() else 0.0


def update_smc_engine(state: SmcEngineState, bar: AnnotatedBar, sigma_t: float) -> SmcEngineResult:
    """Avanza el motor una barra M1: agregación → ATR → fractales → liquidez → sweeps.

    `sigma_t` es el sigma vigente del VWAP (provisto por el caller vía
    `common.vwap_engine.update_vwap`), usado por `resolve_free_path` (R104). No importa
    `numpy`/`pandas` ni los paquetes de capa 3 (backtest)/capa 4 (validación) (R105).
    """
    state._clock.advance(bar)
    config = state._config

    m1_agg = to_m1_aggregated_bar(bar)
    new_agg_bars = [m1_agg, *state._bar_aggregator.push(bar)]

    for agg_bar in new_agg_bars:
        timeframe = agg_bar.timeframe
        atr = state._atr[timeframe]
        atr.update(agg_bar.high, agg_bar.low, agg_bar.close)
        atr_value = _atr_value_or_zero(atr)

        for swing in state._fractals[timeframe].push(agg_bar):
            state._confirmed_swings[timeframe].append(swing)
            state._liquidity.add_swing(swing, atr_value)

        state._liquidity.apply_close(agg_bar)

    atr_m1 = _atr_value_or_zero(state._atr[Timeframe.M1])

    active_level_ids = {
        level.level_id
        for timeframe in _ALL_TIMEFRAMES
        for level in state._liquidity.active_levels(timeframe)
    }

    for level_id in active_level_ids:
        if level_id not in state._sweep_trackers:
            level = state._liquidity.get(level_id)
            state._sweep_trackers[level_id] = SweepTracker(
                level=level,
                state=SweepState.ARMADO,
                touch_time=None,
                swept_time=None,
                extreme_price=None,
            )

    updated_trackers: dict[int, SweepTracker] = {}
    for level_id, tracker in state._sweep_trackers.items():
        if level_id not in active_level_ids:
            continue  # el nivel salió del mapa de LiquidityMap: se descarta su tracker
        current_level = state._liquidity.get(level_id)
        refreshed = replace(tracker, level=current_level)
        updated_trackers[level_id] = transition_sweep(refreshed, bar, atr_m1, config)
    state._sweep_trackers = updated_trackers

    active_sweeps = tuple(
        tracker
        for tracker in state._sweep_trackers.values()
        if tracker.state in (SweepState.BARRIDO, SweepState.EXPIRADO)
    )

    resolved_level: LiquidityLevel | None = None
    if active_sweeps:
        chosen = active_sweeps[0]
        if chosen.extreme_price is not None:
            macro = resolve_free_path(
                chosen.extreme_price, chosen.level.direction, sigma_t, state._liquidity, config
            )
            resolved_level = macro if macro is not None else chosen.level

    atr_by_tf = {tf: _atr_value_or_zero(state._atr[tf]) for tf in _ALL_TIMEFRAMES}

    return SmcEngineResult(
        current_time=bar.timestamp_utc,
        atr_by_tf=atr_by_tf,
        active_sweeps=active_sweeps,
        resolved_level=resolved_level,
    )
