"""Núcleo estadístico puro del diagnóstico de señal desnuda §2.2.1 (capa 2, R111-R115).

Detección del evento CT, retornos condicionales por horizonte frente a la distribución
incondicional del mismo símbolo/sesión, tasa de toque de VWAP antes de la distancia de
stop típica, e intervalos por bootstrap de bloques temporales (`numpy` puro,
reimplementado localmente — ADR-D4/ADR-H5). Depende solo de capa 1
(`genesis.data.store.AnnotatedBar`) + capa 2 (`smc_engine`, `common.zones`,
`common.vwap_engine`, `contract.Direction`) + `numpy`. **NUNCA** importa los paquetes de
capa 3 (backtest)/capa 4 (validación) (R111): sin coste real de ticks, sin veredicto —
eso vive en la orquestación de capa 4 (§3.9 del spec).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from genesis.data.store import AnnotatedBar
from genesis.strategy.candidate_a.config import CandidateAConfig
from genesis.strategy.candidate_a.smc.engine import SmcEngineState, update_smc_engine
from genesis.strategy.candidate_a.smc.fractals import SwingDirection
from genesis.strategy.candidate_a.smc.timeframe import Timeframe
from genesis.strategy.common.vwap_engine import (
    VWAPState,
    default_vwap_anchor_config,
    is_new_anchor,
    update_vwap,
)
from genesis.strategy.common.zones import Zone, classify_zone
from genesis.strategy.contract import Direction

_MIN_BOOTSTRAP_BLOCK = 1
_BOOTSTRAP_LOW_PERCENTILE = 5.0
_BOOTSTRAP_HIGH_PERCENTILE = 95.0


@dataclass(frozen=True, slots=True)
class ConditionalReturnEvent:
    """Evento CT con sweep vigente: base del edge condicional bruto (R112)."""

    symbol: str
    session_label: str
    event_time: datetime
    """Timestamp de la barra M1 que disparó el evento (zona CT + sweep vigente)."""
    trading_day: date
    """Día de trading (`AnnotatedBar.trading_day`) de la barra del evento.

    Campo adicional (no listado explícitamente en el diseño §3.5, refinamiento de
    implementación): permite a `signal_diagnostic.estimate_roundtrip_cost` (capa 4)
    resolver la ventana de ticks con el **mismo** criterio de `trading_day` que
    `has_sufficient_tick_coverage`/`ticks_in_bar_window` (R116), en vez de aproximar
    con `event_time.date()` (que puede diferir del día de trading según
    `daily_reset_time` de la ficha de firma activa).
    """
    expected_reversion: Direction
    """Dirección esperada de reversión (mean-reversion hacia el VWAP)."""
    entry_price: float
    stop_distance: float
    """Distancia de stop típica (§3.5): |extremo del sweep − nivel| + buffer×ATR(M1)."""
    vwap_at_event: float


@dataclass(frozen=True, slots=True)
class HorizonEdge:
    """Retorno condicional/incondicional e intervalo bootstrap de un horizonte (R113/R114)."""

    horizon_minutes: int
    conditional_mean: float
    unconditional_mean: float
    bootstrap_low: float
    """Límite inferior del intervalo de bootstrap del retorno condicional medio."""
    bootstrap_high: float
    n_events: int
    """Número de eventos con retorno forward disponible en este horizonte."""


@dataclass(frozen=True, slots=True)
class RawEdgeSummary:
    """Edge condicional bruto, SIN coste ni veredicto (eso vive en capa 4, R115)."""

    symbol: str
    session_label: str
    horizons: tuple[HorizonEdge, ...]
    vwap_touch_rate: float
    """Tasa de toque del VWAP antes de recorrer la distancia de stop típica."""
    typical_stop_distance: float
    n_ct_events: int


def _resolved_sweep_extreme_and_level(smc_result) -> tuple[float, float, SwingDirection] | None:
    """Extrae `(extreme_price, level_price, direction)` del sweep vigente, si existe."""
    if not smc_result.active_sweeps:
        return None
    chosen = smc_result.active_sweeps[0]
    if chosen.extreme_price is None:
        return None
    level = smc_result.resolved_level if smc_result.resolved_level is not None else chosen.level
    return chosen.extreme_price, level.price, chosen.level.direction


def detect_ct_events(
    bars: Sequence[AnnotatedBar],
    config: CandidateAConfig,
    symbol: str,
    session_label: str,
) -> list[ConditionalReturnEvent]:
    """Detecta eventos CT con sweep vigente (`BARRIDO`/`EXPIRADO`) sobre `bars` (R112).

    Alimenta `smc_engine` y el VWAP internamente, barra a barra (forward-only). El
    umbral de zona CT reutiliza `common.zones.classify_zone` (R112, sin reimplementar).
    """
    smc_state = SmcEngineState(symbol, config.smc)
    vwap_state = VWAPState()
    vwap_config = default_vwap_anchor_config()

    events: list[ConditionalReturnEvent] = []
    for bar in bars:
        is_anchor = is_new_anchor(bar.timestamp_utc, vwap_config)
        vwap_result = update_vwap(
            vwap_state,
            bar.high,
            bar.low,
            bar.close,
            bar.tick_volume,
            bar_closed=True,
            is_anchor=is_anchor,
            config=vwap_config,
        )
        smc_result = update_smc_engine(smc_state, bar, sigma_t=vwap_result.sigma)

        if not vwap_result.is_valid:
            continue
        zone = classify_zone(vwap_result.zscore, ct_zscore_min=config.smc.ct_zscore_min)
        if zone != Zone.CT:
            continue

        extreme_and_level = _resolved_sweep_extreme_and_level(smc_result)
        if extreme_and_level is None:
            continue
        extreme_price, level_price, sweep_direction = extreme_and_level

        atr_m1 = smc_result.atr_by_tf.get(Timeframe.M1, 0.0)
        stop_distance = abs(extreme_price - level_price) + (
            config.diagnostics.stop_distance_atr_buffer_multiple * atr_m1
        )
        expected_reversion = (
            Direction.SHORT if sweep_direction == SwingDirection.HIGH else Direction.LONG
        )

        events.append(
            ConditionalReturnEvent(
                symbol=symbol,
                session_label=session_label,
                event_time=bar.timestamp_utc,
                trading_day=bar.trading_day,
                expected_reversion=expected_reversion,
                entry_price=bar.close,
                stop_distance=stop_distance,
                vwap_at_event=vwap_result.vwap,
            )
        )
    return events


def _default_block_size(n: int) -> int:
    """`clip(round(n ** (1/3)), 1, max(1, n))` — variante local sin piso de 5.

    Mismo patrón conceptual que `_default_block_size` del motor de Monte Carlo (capa 4).
    """
    if n <= 0:
        return _MIN_BOOTSTRAP_BLOCK
    size = round(n ** (1.0 / 3.0))
    return max(_MIN_BOOTSTRAP_BLOCK, min(size, n))


def _block_resample(
    returns: np.ndarray, block_size: int, rng: np.random.Generator, *, target_len: int
) -> np.ndarray:
    """Moving-block bootstrap circular (reimplementado localmente, ADR-D4/ADR-H5).

    Mismo patrón que `_block_resample` del motor de Monte Carlo (capa 4): bloques contiguos
    de `block_size` con reemplazo, envueltos circularmente (`wrap-around`).
    """
    n = len(returns)
    n_blocks_needed = -(-target_len // block_size)
    starts = rng.integers(0, n, size=n_blocks_needed)
    blocks = [np.take(returns, np.arange(start, start + block_size) % n) for start in starts]
    return np.concatenate(blocks)[:target_len]


def _bootstrap_interval(
    returns: list[float], n_resamples: int, block_size: int | None, seed: int
) -> tuple[float, float]:
    """Intervalo `[p5, p95]` del retorno medio, vía bootstrap de bloques (R114)."""
    if not returns:
        return 0.0, 0.0
    array = np.asarray(returns, dtype=float)
    resolved_block_size = block_size if block_size is not None else _default_block_size(len(array))
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples, dtype=float)
    for path_index in range(n_resamples):
        resampled = _block_resample(array, resolved_block_size, rng, target_len=len(array))
        means[path_index] = resampled.mean()
    low = float(np.percentile(means, _BOOTSTRAP_LOW_PERCENTILE))
    high = float(np.percentile(means, _BOOTSTRAP_HIGH_PERCENTILE))
    return low, high


def _signed_return(entry_price: float, future_close: float, direction: Direction) -> float:
    """Retorno orientado a `direction`: positivo == movimiento favorable a la tesis."""
    if direction == Direction.LONG:
        return (future_close - entry_price) / entry_price
    return (entry_price - future_close) / entry_price


def _touches_vwap_before_stop(
    bars_by_time: dict[datetime, int],
    bars: Sequence[AnnotatedBar],
    event: ConditionalReturnEvent,
    max_lookahead_minutes: int,
) -> bool:
    """`True` si el precio toca el VWAP del evento antes de recorrer `stop_distance`."""
    start_index = bars_by_time.get(event.event_time)
    if start_index is None:
        return False
    is_long = event.expected_reversion == Direction.LONG
    for offset in range(1, max_lookahead_minutes + 1):
        index = start_index + offset
        if index >= len(bars):
            return False
        bar = bars[index]
        if is_long:
            if bar.low <= event.entry_price - event.stop_distance:
                return False
            if bar.high >= event.vwap_at_event:
                return True
        else:
            if bar.high >= event.entry_price + event.stop_distance:
                return False
            if bar.low <= event.vwap_at_event:
                return True
    return False


def summarize_raw_edge(
    bars: Sequence[AnnotatedBar],
    events: Sequence[ConditionalReturnEvent],
    config: CandidateAConfig,
) -> RawEdgeSummary:
    """Resume el edge condicional bruto de `events` sobre `bars` (R113-R115).

    Retorno forward a cada horizonte de `horizons_minutes` (o el subconjunto disponible
    antes de agotar `bars`) frente a la distribución incondicional del mismo símbolo/
    sesión (misma ventana, sin filtro CT). Asume `bars` contiguas minuto a minuto
    (búsqueda del retorno forward por aritmética de índice, decisión de implementación
    documentada): válido para el dataset de muestra de este Change; series con huecos
    de mercado reales quedan para una futura iteración (spec §8, riesgo análogo a la
    ventana Londres-NY sin DST).
    """
    bars_by_time = {bar.timestamp_utc: index for index, bar in enumerate(bars)}
    seed = config.diagnostics.bootstrap_seed
    block_size = config.diagnostics.bootstrap_block_size
    n_resamples = config.diagnostics.bootstrap_resamples

    horizons: list[HorizonEdge] = []
    for horizon_minutes in config.diagnostics.horizons_minutes:
        conditional_returns: list[float] = []
        for event in events:
            start_index = bars_by_time.get(event.event_time)
            if start_index is None:
                continue
            future_index = start_index + horizon_minutes
            if future_index >= len(bars):
                continue
            future_bar = bars[future_index]
            conditional_returns.append(
                _signed_return(event.entry_price, future_bar.close, event.expected_reversion)
            )

        unconditional_returns = [
            (bars[index + horizon_minutes].close - bar.close) / bar.close
            for index, bar in enumerate(bars)
            if index + horizon_minutes < len(bars)
        ]

        conditional_mean = float(np.mean(conditional_returns)) if conditional_returns else 0.0
        unconditional_mean = float(np.mean(unconditional_returns)) if unconditional_returns else 0.0
        bootstrap_low, bootstrap_high = _bootstrap_interval(
            conditional_returns, n_resamples, block_size, seed + horizon_minutes
        )
        horizons.append(
            HorizonEdge(
                horizon_minutes=horizon_minutes,
                conditional_mean=conditional_mean,
                unconditional_mean=unconditional_mean,
                bootstrap_low=bootstrap_low,
                bootstrap_high=bootstrap_high,
                n_events=len(conditional_returns),
            )
        )

    max_horizon = (
        max(config.diagnostics.horizons_minutes) if config.diagnostics.horizons_minutes else 0
    )
    touches = [
        _touches_vwap_before_stop(bars_by_time, bars, event, max_horizon) for event in events
    ]
    vwap_touch_rate = (sum(touches) / len(touches)) if touches else 0.0
    typical_stop_distance = (
        float(np.mean([event.stop_distance for event in events])) if events else 0.0
    )

    symbol = events[0].symbol if events else ""
    session_label = events[0].session_label if events else ""

    return RawEdgeSummary(
        symbol=symbol,
        session_label=session_label,
        horizons=tuple(horizons),
        vwap_touch_rate=vwap_touch_rate,
        typical_stop_distance=typical_stop_distance,
        n_ct_events=len(events),
    )
