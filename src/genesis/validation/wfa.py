"""Walk-forward rolling con grid IS exhaustivo, selección DSR-IS, OOS cosido y WFE.

Capa 4 (`genesis.validation`): consume la API pública ya cerrada de `genesis.data`,
`genesis.strategy` y `genesis.backtest` (capas 1-3) en un solo sentido, sin
modificar ninguno de los tres árboles (R61). Grid exhaustivo 27 combinaciones de
ejecución / 9 configuraciones de señal (spec §6.2, Candidato B): sin muestreo, sin
paralelismo (`multiprocessing`/`concurrent.futures`, R32), loop secuencial.

Advertencia heredada del Candidato B (Rg-1, aceptada, no defecto de este Change):
cada combinación/ventana instancia un `CandidateB` **nuevo** (nunca reutilizado);
el estado ATR-Wilder-14 arranca en frío (`atr_value=None`) al inicio de cada
instancia, de modo que los primeros `atr_period` (14) días de cada ventana pueden
operar sin componente ATR del stop. Con `IS_WINDOW_TRADING_DAYS = 252` el sesgo es
despreciable (14/252).
"""

from collections.abc import Iterator, Sequence
from datetime import date

import pandas as pd

from genesis.backtest.ledger import FillRecord, Ledger
from genesis.data.profile import FirmProfile
from genesis.data.store import iter_bars
from genesis.validation.errors import WfaConfigError
from genesis.validation.window_config import WfaWindowConfig


def _extract_exit_returns(ledger: Ledger) -> list[float]:
    """Deltas de `equity_after` de los `FillRecord` de salida del `ledger` (§2 del spec).

    Replica el patrón `genesis.backtest.metrics._running_equity_deltas` + filtro
    `is_exit`, duplicado a propósito en `wfa.py` y `montecarlo.py` (ADR-H5): NO
    importa ningún símbolo privado de `genesis.backtest.metrics` (R61).
    """
    deltas: list[float] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                deltas.append(payload.equity_after - previous_equity)
            previous_equity = payload.equity_after
    return deltas


def _plan_windows(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
) -> tuple[list[date], dict[date, tuple[int, int]]]:
    """Pasada única de planificación (R8, ADR-H3): `days` ordenados + `row_span` posicional.

    Recorre `iter_bars(frame, symbol, firm_profile)` una sola vez, forward-only, sin
    reposicionar cursor ni reimplementar `_trading_day`. `row_span[day]` es
    `(posición_mínima, posición_máxima)` de fila del frame crudo para ese
    `trading_day`, en el mismo orden posicional que `frame` (invariante: `frame` ya
    viene ordenado cronológicamente, impuesto por `iter_bars`).
    """
    days: list[date] = []
    row_span: dict[date, tuple[int, int]] = {}
    for position, bar in enumerate(iter_bars(frame, symbol, firm_profile)):
        trading_day = bar.trading_day
        if trading_day not in row_span:
            days.append(trading_day)
            row_span[trading_day] = (position, position)
        else:
            first_position, _ = row_span[trading_day]
            row_span[trading_day] = (first_position, position)
    return days, row_span


def _validate_history(
    days: Sequence[date],
    window_config: WfaWindowConfig,
    *,
    candidate_id: str,
    symbol: str,
) -> None:
    """Guarda de historia insuficiente (R11): fail-fast antes de cualquier backtest."""
    required = window_config.is_window_trading_days + window_config.oos_window_trading_days
    if len(days) < required:
        message = (
            f"Historia insuficiente para candidate_id={candidate_id!r} symbol={symbol!r}: "
            f"{len(days)} trading_day distintos disponibles, se requieren >= {required} "
            f"(is_window_trading_days={window_config.is_window_trading_days} + "
            f"oos_window_trading_days={window_config.oos_window_trading_days}, R11)."
        )
        raise WfaConfigError(message)


def _iter_window_bounds(
    n_days: int,
    window_config: WfaWindowConfig,
) -> Iterator[tuple[int, int, int, int]]:
    """Enumera `(k, is_start, is_end, oos_end)`, límites exclusivos sobre la lista `days` (R9).

    IS: `days[is_start:is_end]`; OOS: `days[is_end:oos_end]`. Con
    `step_trading_days == oos_window_trading_days` (default), los tramos OOS de
    ventanas consecutivas son contiguos, sin solape ni hueco.
    """
    is_window = window_config.is_window_trading_days
    oos_window = window_config.oos_window_trading_days
    step = window_config.step_trading_days
    k = 0
    while k * step + is_window + oos_window <= n_days:
        is_start = k * step
        is_end = is_start + is_window
        oos_end = is_end + oos_window
        yield k, is_start, is_end, oos_end
        k += 1


def _slice_frame_by_days(
    frame: pd.DataFrame,
    row_span: dict[date, tuple[int, int]],
    days_slice: Sequence[date],
) -> pd.DataFrame:
    """Trocea `frame` por span posicional contiguo de `days_slice` (R10, ADR-H3).

    `frame.iloc[first_position:last_position + 1]`, límites resueltos de
    `row_span` de la pasada de planificación de `_plan_windows` — nunca por
    comparación de fechas naive de la columna `timestamp` ni reejecutando
    `iter_bars` por ventana.
    """
    first_position = row_span[days_slice[0]][0]
    last_position = row_span[days_slice[-1]][1]
    return frame.iloc[first_position : last_position + 1]


def _plan_and_validate_windows(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    window_config: WfaWindowConfig,
    *,
    candidate_id: str,
) -> tuple[list[date], dict[date, tuple[int, int]]]:
    """Planifica ventanas (R8) y aplica la guarda de historia insuficiente (R11)."""
    days, row_span = _plan_windows(frame, symbol, firm_profile)
    _validate_history(days, window_config, candidate_id=candidate_id, symbol=symbol)
    return days, row_span
