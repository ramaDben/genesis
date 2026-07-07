"""Geometría de ventanas walk-forward reutilizable, módulo interno (ADR-I2, R25).

`build_signal_trial_matrix` (`dsr_pbo.py`, no recibe `WfaResult`) y `run_sensitivity`
(`sensitivity.py`, trocea el último tramo OOS) necesitan reproducir exactamente la
misma geometría IS/OOS que `wfa.py` ya usa (`_plan_windows`/`_iter_window_bounds`/
`_slice_frame_by_days`), pero sin importar ningún símbolo con prefijo `_` de
`wfa.py` (R25) — `wfa.py` es un módulo ya cerrado de H (R56). Reimplementación
independiente sobre la API pública `iter_bars`; interno (prefijo `_`), nunca
exportado en `src/genesis/validation/__init__.py`.
"""

from collections.abc import Iterator, Sequence
from datetime import date

import pandas as pd

from genesis.data.profile import FirmProfile
from genesis.data.store import iter_bars
from genesis.validation.window_config import WfaWindowConfig


def plan_trading_days(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
) -> tuple[list[date], dict[date, tuple[int, int]]]:
    """Pasada única de planificación forward-only (mismo patrón que `wfa._plan_windows`).

    Recorre `iter_bars(frame, symbol, firm_profile)` una sola vez y devuelve
    `days` (`trading_day` distintos, en orden de aparición) y `row_span` (posición
    mínima/máxima de fila del `frame` crudo para cada `trading_day`, en el mismo
    orden posicional que `frame` — invariante: `frame` ya viene ordenado
    cronológicamente, impuesto por `iter_bars`).
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


def iter_is_oos_bounds(
    n_days: int,
    window_config: WfaWindowConfig,
) -> Iterator[tuple[int, int, int, int]]:
    """Enumera `(k, is_start, is_end, oos_end)`, idéntica geometría que `wfa._iter_window_bounds`.

    Límites exclusivos sobre una lista `days` de longitud `n_days`: tramo IS
    `days[is_start:is_end]`, tramo OOS `days[is_end:oos_end]`. Con
    `step_trading_days == oos_window_trading_days` (default de `WfaWindowConfig`),
    los tramos OOS de ventanas consecutivas son contiguos, sin solape ni hueco.
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


def slice_frame_by_days(
    frame: pd.DataFrame,
    row_span: dict[date, tuple[int, int]],
    days_slice: Sequence[date],
) -> pd.DataFrame:
    """Trocea `frame` por span posicional contiguo de `days_slice` (mismo patrón que H).

    `frame.iloc[first_position:last_position + 1]`, límites resueltos de
    `row_span` de la pasada de `plan_trading_days` — nunca por comparación de
    fechas naive de la columna `timestamp` ni reejecutando `iter_bars` por ventana.
    """
    first_position = row_span[days_slice[0]][0]
    last_position = row_span[days_slice[-1]][1]
    return frame.iloc[first_position : last_position + 1]


def slice_frame_by_day_range(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    day_range: tuple[date, date],
) -> pd.DataFrame:
    """Conveniencia: una pasada de `plan_trading_days` + troceo del rango `[start, end]`.

    Usado por `sensitivity.py` para recuperar el tramo OOS de la última ventana
    WFA (`WfaResult.windows[-1].oos_trading_day_range`) a partir del `frame`
    original completo, sin volver a ejecutar `run_wfa`.
    """
    days, row_span = plan_trading_days(frame, symbol, firm_profile)
    start, end = day_range
    days_slice = [day for day in days if start <= day <= end]
    return slice_frame_by_days(frame, row_span, days_slice)
