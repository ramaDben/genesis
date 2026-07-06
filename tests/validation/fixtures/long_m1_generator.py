"""Generador determinista de un frame M1 largo con ruptura de rango diaria (Rg-6).

Base: el patrón `_deterministic_m1_frame` de `tests/data/fakes.py`, ampliado para
(a) saltar fines de semana, (b) alinear las barras a la sesión real de `symbol`
(`genesis.data.sessions.session_window`), (c) forzar exactamente una ruptura de
rango operable por día. Con `n_trading_days >= IS_WINDOW_TRADING_DAYS +
OOS_WINDOW_TRADING_DAYS` (>= 378), cubre al menos una ventana WFA completa con el
`WfaWindowConfig` por defecto.

Cada día produce, en orden: `_RANGE_BARS` barras de rango muy estrecho (compatibles
con cualquier `n_minutes` del grid del Candidato B, `{5, 15, 30}`), una barra de
ruptura muy por encima del rango (dispara `CandidateB` sin ambigüedad de nivel), y
una barra final alineada al cierre de sesión (`close_utc` del símbolo) que fuerza el
cierre de cualquier posición viva vía `Simulator._enforce_session_close_and_guard`
— garantiza al menos un `FillRecord` de salida por día con señal, sin depender de
cobertura de ticks.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from genesis.data.sessions import session_window

_RANGE_BARS = 30
"""Cubre el mayor `n_minutes` del grid por defecto del Candidato B (5, 15, 30)."""

_SERVER_TZ = ZoneInfo("America/New_York")
"""`server_tz` del `FirmProfile` por defecto (`the5ers.json`)."""

_BASE_PRICE = 4500.0
_RANGE_HALF_WIDTH = 0.3
_BREAKOUT_JUMP = 5.0
_DAY_JITTER_STD = 0.01
_FIRST_MONDAY = date(2020, 1, 6)


def _weekdays(n_trading_days: int, start: date = _FIRST_MONDAY) -> list[date]:
    """Lista de `n_trading_days` fechas hábiles (lunes-viernes) consecutivas desde `start`."""
    days: list[date] = []
    cursor = start
    while len(days) < n_trading_days:
        if cursor.weekday() < 5:  # 0=lunes .. 4=viernes
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _to_server_local(moment_utc: datetime) -> datetime:
    """Convierte un instante UTC a hora local naive de `_SERVER_TZ` (inverso de `_to_utc`)."""
    return moment_utc.astimezone(_SERVER_TZ).replace(tzinfo=None)


def _day_rows(symbol: str, trading_day: date, base: float) -> list[dict[str, object]]:
    """Filas de un único día: rango estrecho + ruptura + barra de cierre de sesión."""
    open_utc, close_utc = session_window(symbol, trading_day)
    open_local = _to_server_local(open_utc)
    close_local = _to_server_local(close_utc)

    rows: list[dict[str, object]] = []
    for minute in range(_RANGE_BARS):
        timestamp = open_local + timedelta(minutes=minute)
        wiggle = 0.05 if minute % 2 == 0 else -0.03
        rows.append(
            {
                "timestamp": timestamp,
                "open": base,
                "high": base + _RANGE_HALF_WIDTH,
                "low": base - _RANGE_HALF_WIDTH,
                "close": base + wiggle,
                "tick_volume": 100,
            }
        )

    breakout_close = base + _BREAKOUT_JUMP
    rows.append(
        {
            "timestamp": open_local + timedelta(minutes=_RANGE_BARS),
            "open": base,
            "high": breakout_close + 1.0,
            "low": base - 0.2,
            "close": breakout_close,
            "tick_volume": 150,
        }
    )

    rows.append(
        {
            "timestamp": close_local,
            "open": breakout_close,
            "high": breakout_close + 0.05,
            "low": breakout_close - 0.05,
            "close": breakout_close,
            "tick_volume": 100,
        }
    )
    return rows


def generate_long_m1_frame(
    symbol: str,
    n_trading_days: int,
    *,
    seed: int = 0,
) -> pd.DataFrame:
    """Genera un frame M1 crudo determinista de `n_trading_days` días hábiles (Rg-6).

    Misma `(symbol, n_trading_days, seed)` produce siempre el mismo frame
    bit-idéntico (sin I/O, sin estado global): la única fuente de variación entre
    días es un jitter determinista del precio base, generado por
    `numpy.random.default_rng(seed)`.
    """
    rng = np.random.default_rng(seed)
    days = _weekdays(n_trading_days)

    rows: list[dict[str, object]] = []
    base = _BASE_PRICE
    for trading_day in days:
        base += float(rng.normal(0.0, _DAY_JITTER_STD))
        rows.extend(_day_rows(symbol, trading_day, base))

    frame = pd.DataFrame(rows)
    return frame.sort_values("timestamp").reset_index(drop=True)
