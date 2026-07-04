"""Lectura normalizada tz-servidor → UTC, forward-only, con marcas de día y sesión.

`iter_bars` es un generador: la única forma de consumo es iteración monotónica hacia
adelante (R32) — no expone acceso por índice absoluto ni una forma de adelantar el
cursor para inspeccionar filas futuras. La excepción de lookahead de la capa de
estrategia no se implementa en este Change (PA-4 es de Issue C, fuera de alcance; ver
spec §11.1).
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from genesis.data.errors import GenesisDataError
from genesis.data.profile import FirmProfile
from genesis.data.sessions import session_window


class DayBoundaryError(GenesisDataError):
    """Corte de día inconsistente con `daily_reset_time` de la ficha activa (R30)."""


@dataclass(frozen=True, slots=True)
class AnnotatedBar:
    """Barra M1 anotada: timestamp UTC, día de trading y marca de sesión."""

    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    trading_day: date
    in_session: bool


def _to_utc(raw_timestamp: Any, server_tz: ZoneInfo) -> datetime:
    """Reinterpreta `raw_timestamp` como hora local del servidor y la convierte a UTC.

    `raw_timestamp` puede ser un `pd.Timestamp` (frame leído de Parquet) o un
    `datetime.datetime` ya nativo; de ahí `Any`. El Parquet crudo de `mt5_export.py`
    almacena el timestamp con sus valores de reloj de pared del servidor MT5
    (año/mes/día/hora/minuto); cualquier `tzinfo` que ya traiga se descarta antes de
    reinterpretarlo como `server_tz` (R28, R40): nunca se usa un offset fijo, siempre
    `zoneinfo`.
    """
    moment: datetime = (
        raw_timestamp.to_pydatetime() if hasattr(raw_timestamp, "to_pydatetime") else raw_timestamp
    )
    naive = moment.replace(tzinfo=None)
    server_local = naive.replace(tzinfo=server_tz)
    return server_local.astimezone(UTC)


def _trading_day(timestamp_utc: datetime, profile: FirmProfile) -> date:
    """Día de trading según `daily_reset_time`/`daily_reset_tz` de la ficha activa (R29)."""
    reset_tz = ZoneInfo(profile.daily_reset_tz)
    local_moment = timestamp_utc.astimezone(reset_tz)
    if local_moment.time() >= profile.daily_reset_time:
        return local_moment.date()
    return local_moment.date() - timedelta(days=1)


def iter_bars(
    frame: pd.DataFrame,
    symbol: str,
    profile: FirmProfile,
) -> Iterator[AnnotatedBar]:
    """Generador forward-only de `AnnotatedBar` a partir de un frame crudo M1.

    Convierte cada timestamp de hora local del servidor MT5 (`profile.server_tz`) a UTC
    vía `zoneinfo` (R28, R40); asigna `trading_day` por `daily_reset_time` de la ficha
    activa (R29); marca `in_session` a partir de `sessions.session_window` (fuente única,
    sin tabla duplicada, R31). Si el `trading_day` calculado retrocede respecto a la barra
    anterior (corte de día inconsistente, R41), lanza `DayBoundaryError` con contexto.

    Único punto de emisión: no expone acceso por índice absoluto ni un método para
    reposicionar el cursor de lectura (R32); la excepción de lookahead de la capa de
    estrategia no se implementa en este Change (R33, PA-4 = Issue C).
    """
    server_tz = ZoneInfo(profile.server_tz)
    previous_trading_day: date | None = None

    for _, row in frame.iterrows():
        timestamp_utc = _to_utc(row["timestamp"], server_tz)
        trading_day = _trading_day(timestamp_utc, profile)

        if previous_trading_day is not None and trading_day < previous_trading_day:
            message = (
                f"Corte de día inconsistente para '{symbol}': la barra en {timestamp_utc!r} "
                f"resuelve trading_day={trading_day!r}, anterior al trading_day previo "
                f"{previous_trading_day!r}. daily_reset_time activo: "
                f"{profile.daily_reset_time!r} ({profile.daily_reset_tz})."
            )
            raise DayBoundaryError(message)
        previous_trading_day = trading_day

        open_utc, close_utc = session_window(symbol, trading_day)
        in_session = open_utc <= timestamp_utc <= close_utc

        yield AnnotatedBar(
            timestamp_utc=timestamp_utc,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            tick_volume=int(row["tick_volume"]),
            trading_day=trading_day,
            in_session=in_session,
        )
