"""`SweepState` + `transition_sweep`: máquina de estados de sweep de 5 estados (R103).

Módulo de dominio puro: solo stdlib + `genesis.data.store.AnnotatedBar` (capa 1) +
`genesis.strategy.candidate_a.{errors,smc.liquidity,smc.fractals}` (capa 2). El conteo
de ventanas (`sweep_window_k`, `sweep_validity_m`) se hace en **velas M1**, medido por
un contador incremental interno del tracker (no por delta de tiempo, para robustez
ante huecos de mercado — decisión menor de design §3.3).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from genesis.data.store import AnnotatedBar
from genesis.strategy.candidate_a.errors import SmcEngineStateError
from genesis.strategy.candidate_a.smc.fractals import SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityLevel


class SweepState(StrEnum):
    """Los 5 estados normativos de la máquina de sweep (R103)."""

    ARMADO = "armado"
    TOCADO = "tocado"
    BARRIDO = "barrido"
    EXPIRADO = "expirado"
    MITIGADO = "mitigado"


@dataclass(frozen=True, slots=True)
class SweepTracker:
    """Estado de la FSM de sweep para un `LiquidityLevel` (R103).

    `bars_in_state` es un contador interno (implementación, no normativo del spec) de
    velas M1 transcurridas desde que se entró al estado vigente; se usa para acotar
    `sweep_window_k`/`sweep_validity_m` por índice de vela, nunca por delta de tiempo.
    """

    level: LiquidityLevel
    state: SweepState
    touch_time: datetime | None
    swept_time: datetime | None
    extreme_price: float | None
    bars_in_state: int = 0


@runtime_checkable
class SweepConfigProtocol(Protocol):
    """Estructura mínima de configuración consumida por `transition_sweep` (duck typing).

    Evita importar `candidate_a.config.SmcEngineConfig` desde `smc/` (mantendría el
    acoplamiento en un solo sentido: `config.py` no depende de `smc/`, y `smc/` no
    necesita importar `config.py` para tipar; ambos son capa 2, sin ciclo). Un objeto
    con más atributos (p. ej. `SmcEngineConfig` completo, o el protocolo más amplio de
    `engine.py`) satisface esta estructura por subtipado estructural.
    """

    sweep_tolerance_atr: float
    sweep_window_k: int
    sweep_validity_m: int


def _is_beyond(price: float, level_price: float, *, is_high: bool) -> bool:
    return price > level_price if is_high else price < level_price


def _is_closed_back(close: float, level_price: float, *, is_high: bool) -> bool:
    return close < level_price if is_high else close > level_price


def transition_sweep(
    tracker: SweepTracker,
    bar: AnnotatedBar,
    atr_m1: float,
    config: SweepConfigProtocol,
) -> SweepTracker:
    """Transición PURA de la FSM de sweep (R103), simétrica superior/inferior.

    - `ARMADO`: el nivel existe y no está mitigado; transiciona a `TOCADO` si
      `high > nivel + sweep_tolerance_atr*ATR(14,M1)` (o `low <` para inferior). Si la
      misma vela ya cierra de vuelta dentro del nivel, transiciona directo a `BARRIDO`
      (la vela del toque cuenta como posición 1 de `sweep_window_k`, R103).
    - `TOCADO`: dentro de `sweep_window_k` velas M1 desde el toque (incluida la del
      toque), una vela M1 CIERRA de vuelta dentro del nivel -> `BARRIDO`; agotada la
      ventana sin cierre de vuelta -> `MITIGADO`.
    - `BARRIDO`: habilita entradas durante `sweep_validity_m` velas; si una vela CIERRA
      más allá del nivel en cualquier momento -> `MITIGADO`; agotado el plazo sin
      mitigación -> `EXPIRADO`.
    - `EXPIRADO`: vuelve a `ARMADO` en la siguiente actualización.
    - `MITIGADO`: terminal; el motor remueve el nivel del mapa activo.

    Nunca produce un estado fuera de los 5 definidos (R123, exhaustivo).
    """
    level = tracker.level
    is_high = level.direction == SwingDirection.HIGH

    if tracker.state == SweepState.MITIGADO:
        return tracker

    if tracker.state == SweepState.ARMADO:
        tolerance = config.sweep_tolerance_atr * atr_m1
        touch_threshold = level.price + tolerance if is_high else level.price - tolerance
        touched = bar.high > touch_threshold if is_high else bar.low < touch_threshold
        if not touched:
            return tracker

        extreme_price = bar.high if is_high else bar.low
        if _is_closed_back(bar.close, level.price, is_high=is_high):
            return SweepTracker(
                level=level,
                state=SweepState.BARRIDO,
                touch_time=bar.timestamp_utc,
                swept_time=bar.timestamp_utc,
                extreme_price=extreme_price,
                bars_in_state=0,
            )
        return SweepTracker(
            level=level,
            state=SweepState.TOCADO,
            touch_time=bar.timestamp_utc,
            swept_time=None,
            extreme_price=extreme_price,
            bars_in_state=0,
        )

    if tracker.state == SweepState.TOCADO:
        bars_since_touch = tracker.bars_in_state + 1
        window_position = bars_since_touch + 1  # la vela del toque ya ocupó la posición 1
        extreme_price = tracker.extreme_price
        new_extreme = (
            (max(extreme_price, bar.high) if is_high else min(extreme_price, bar.low))
            if extreme_price is not None
            else (bar.high if is_high else bar.low)
        )
        closed_back = _is_closed_back(bar.close, level.price, is_high=is_high)

        if closed_back and window_position <= config.sweep_window_k:
            return SweepTracker(
                level=level,
                state=SweepState.BARRIDO,
                touch_time=tracker.touch_time,
                swept_time=bar.timestamp_utc,
                extreme_price=new_extreme,
                bars_in_state=0,
            )
        if window_position >= config.sweep_window_k:
            return SweepTracker(
                level=level,
                state=SweepState.MITIGADO,
                touch_time=tracker.touch_time,
                swept_time=None,
                extreme_price=new_extreme,
                bars_in_state=0,
            )
        return SweepTracker(
            level=level,
            state=SweepState.TOCADO,
            touch_time=tracker.touch_time,
            swept_time=None,
            extreme_price=new_extreme,
            bars_in_state=bars_since_touch,
        )

    if tracker.state == SweepState.BARRIDO:
        beyond = _is_beyond(bar.close, level.price, is_high=is_high)
        if beyond:
            return SweepTracker(
                level=level,
                state=SweepState.MITIGADO,
                touch_time=tracker.touch_time,
                swept_time=tracker.swept_time,
                extreme_price=tracker.extreme_price,
                bars_in_state=0,
            )
        new_bars_in_state = tracker.bars_in_state + 1
        if new_bars_in_state >= config.sweep_validity_m:
            return SweepTracker(
                level=level,
                state=SweepState.EXPIRADO,
                touch_time=tracker.touch_time,
                swept_time=tracker.swept_time,
                extreme_price=tracker.extreme_price,
                bars_in_state=0,
            )
        return SweepTracker(
            level=level,
            state=SweepState.BARRIDO,
            touch_time=tracker.touch_time,
            swept_time=tracker.swept_time,
            extreme_price=tracker.extreme_price,
            bars_in_state=new_bars_in_state,
        )

    if tracker.state == SweepState.EXPIRADO:
        return SweepTracker(
            level=level,
            state=SweepState.ARMADO,
            touch_time=None,
            swept_time=None,
            extreme_price=None,
            bars_in_state=0,
        )

    message = f"Estado de sweep desconocido: {tracker.state!r} — invariante R103 violado."
    raise SmcEngineStateError(message)
