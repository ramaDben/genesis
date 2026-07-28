"""Lector de ticks forward-only propio sobre `RawParquetStore` (R15–R19, ADR-G6).

No añade métodos nuevos a `store.py`/`mt5_export.py` (capa 1 cerrada, R57): consume
exclusivamente `RawParquetStore.has_chunk`/`read_chunk`, ya públicos. La ausencia de
ticks para un `(symbol, trading_day)` es el caso normal (PA-2 de B), nunca una
excepción (R16); solo un chunk presente-pero-inválido lanza `BacktestConfigError`
(R17). `_day_window` y `has_sufficient_tick_coverage` comparten el mismo criterio de
borde de la ventana de cobertura `(T-60s, T]` (RI-G5, ADR-G8, Rg-3 §5.2).
"""

from bisect import bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from operator import attrgetter
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from genesis.backtest.errors import BacktestConfigError
from genesis.data.mt5_export import ChunkWindow, Granularity, RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.store import AnnotatedBar

_REQUIRED_COLUMNS = ("bid", "ask", "last")
_COVERAGE_WINDOW = timedelta(seconds=60)
_TIMESTAMP_KEY = attrgetter("timestamp_utc")


@dataclass(frozen=True, slots=True)
class TickRow:
    """Fila de tick ya normalizada, forward-only (una vez emitida no se relee)."""

    timestamp_utc: datetime
    bid: float
    ask: float
    last: float


def _day_window(trading_day: date) -> ChunkWindow:
    """Construye el `ChunkWindow` del día completo `[00:00, 24:00)` UTC de `trading_day`."""
    start = datetime.combine(trading_day, time.min, tzinfo=UTC)
    return ChunkWindow(start=start, end=start + timedelta(days=1))


def _to_utc(raw_timestamp: Any, server_tz: ZoneInfo) -> datetime:
    """Reinterpreta `raw_timestamp` como hora local del servidor y la convierte a UTC.

    Copia local **INTENCIONAL** de `genesis.data.store._to_utc` (capa 1 cerrada, R57,
    ADR-21-1): NO se importa el símbolo privado de `store.py` a través de la frontera
    de capas. **DEBE** mantenerse semánticamente sincronizada con `store._to_utc`
    (Rg-9): descarta cualquier `tzinfo` que ya traiga el valor crudo, reinterpreta el
    wall-clock como `server_tz` vía `zoneinfo` (NUNCA un offset fijo, R28/R40) y
    convierte a UTC real. `raw_timestamp` puede ser un `pd.Timestamp` (frame leído de
    Parquet) o un `datetime.datetime` ya nativo; de ahí `Any`.
    """
    moment: datetime = (
        raw_timestamp.to_pydatetime() if hasattr(raw_timestamp, "to_pydatetime") else raw_timestamp
    )
    naive = moment.replace(tzinfo=None)
    server_local = naive.replace(tzinfo=server_tz)
    return server_local.astimezone(UTC)


def _candidate_server_dates(window: ChunkWindow, server_tz: ZoneInfo) -> list[date]:
    """Fechas calendario de `server_tz` que intersectan `window` (UTC), ascendentes (R63).

    Rango inclusive `[window.start→server_tz].date() .. [(window.end - 1µs)→server_tz]
    .date()`. Los chunks físicos se particionan por día calendario del servidor
    (`mt5_export._chunk_filename`); con `server_tz != UTC` un día UTC objetivo puede
    repartirse entre 1-2 (raramente 3, borde DST de ~25h) chunks de servidor
    adyacentes. Acotado por la duración real de `window`; NO hardcodea un conteo fijo
    ni impone un límite artificial (Rg-10). Con `server_tz="UTC"` retorna exactamente
    `[trading_day]` (R71: sin spillover, regresión no-op).
    """
    start_date = window.start.astimezone(server_tz).date()
    end_date = (window.end - timedelta(microseconds=1)).astimezone(server_tz).date()
    span_days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(span_days + 1)]


def _validate_tick_schema(frame: pd.DataFrame, *, symbol: str, trading_day: date) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        message = (
            f"Chunk de ticks inválido para symbol={symbol!r}, trading_day={trading_day!r}: "
            f"columnas faltantes {missing} (esperadas {_REQUIRED_COLUMNS})."
        )
        raise BacktestConfigError(message)
    for column in _REQUIRED_COLUMNS:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            message = (
                f"Chunk de ticks inválido para symbol={symbol!r}, trading_day={trading_day!r}: "
                f"columna '{column}' no es numérica (dtype={frame[column].dtype})."
            )
            raise BacktestConfigError(message)


def _has_dst_transition(naive_min: datetime, naive_max: datetime, server_tz: ZoneInfo) -> bool:
    """`True` sii `server_tz` tiene distinto `utcoffset()` en `naive_min` y `naive_max`.

    Supuesto explícito (Rg-12, no verificado exhaustivamente para husos exóticos no
    soportados): a lo sumo una transición de horario dentro del chunk (verdadero para
    todos los husos IANA reales soportados, `Europe/Athens`/`America/New_York`/
    `Australia/Sydney` — ninguno tiene 2 transiciones en <25h). Bajo ese supuesto,
    comparar únicamente los dos extremos de un chunk ascendente basta para decidir si
    el offset es constante en todo el rango.
    """
    return (
        naive_min.replace(tzinfo=server_tz).utcoffset()
        != naive_max.replace(tzinfo=server_tz).utcoffset()
    )


def iter_ticks(
    store: RawParquetStore,
    symbol: str,
    trading_day: date,
    profile: FirmProfile,
) -> Iterator[TickRow]:
    """Lector forward-only de ticks del día, reinterpretando `server_tz` (R15, R62-R67).

    Los chunks físicos de ticks están particionados por día calendario del **servidor**
    (`mt5_export._chunk_filename`), no por día UTC; con `profile.server_tz != UTC` el
    día `trading_day` objetivo (UTC) puede intersectar 1-N chunks de servidor
    adyacentes (`_candidate_server_dates`, R63). Por cada candidato cuyo chunk exista
    (`store.has_chunk`), lo lee (`store.read_chunk`), valida su esquema y reinterpreta
    cada timestamp crudo como `server_tz` (R62). Acumula, filtra a la ventana UTC
    objetivo `[00:00, 24:00)` de `trading_day` (R65) y emite `TickRow` ordenados por
    `timestamp_utc` ascendente.

    Mecanismo híbrido por chunk (Issue #24, sin cambio de comportamiento observable):
    si `_has_dst_transition` detecta un cambio de horario dentro del chunk (~2 días/año
    por huso) se reconvierte fila a fila con `_to_utc` (fallback escalar, `itertuples`);
    en el caso normal (sin transición) se resta el offset constante de forma
    vectorizada sobre toda la columna (ruta rápida). Ambas rutas producen el mismo
    resultado que la conversión escalar fila a fila.

    Si *ningún* candidato tiene chunk persistido, retorna secuencia vacía sin excepción
    (R66, extiende R16). Si un candidato existe pero su esquema es inválido (columnas
    `bid`/`ask`/`last` ausentes o mal tipadas), lanza `BacktestConfigError` (R67,
    extiende R17). Solo usa `has_chunk`/`read_chunk`, ya públicos de `RawParquetStore`
    (R70). Con `profile.server_tz="UTC"` el comportamiento observable es idéntico al
    pre-fix (R71); `_has_dst_transition` siempre es `False` (offset 0 en ambos
    extremos) y la ruta rápida se toma siempre.
    """
    window = _day_window(trading_day)
    server_tz = ZoneInfo(profile.server_tz)

    rows: list[TickRow] = []
    for server_date in _candidate_server_dates(window, server_tz):
        chunk_window = _day_window(server_date)
        if not store.has_chunk(symbol, Granularity.TICK, chunk_window):
            continue

        frame = store.read_chunk(symbol, Granularity.TICK, chunk_window)
        _validate_tick_schema(frame, symbol=symbol, trading_day=trading_day)
        if frame.empty:
            continue

        naive_col = frame["timestamp"].dt.tz_localize(None)
        naive_min = naive_col.iloc[0].to_pydatetime()
        naive_max = naive_col.iloc[-1].to_pydatetime()

        if _has_dst_transition(naive_min, naive_max, server_tz):
            # Fallback escalar (acotado al puñado de chunks/año con transición real):
            # misma conversión fila a fila que la implementación pre-#24, vía `itertuples`
            # (no vía el iterador fila-a-fila de pandas basado en `Series`).
            for tick in frame.itertuples(index=False):
                timestamp_utc = _to_utc(tick.timestamp, server_tz)  # ty: ignore[unresolved-attribute]
                if window.start <= timestamp_utc < window.end:
                    rows.append(
                        TickRow(
                            timestamp_utc=timestamp_utc,
                            bid=float(tick.bid),  # ty: ignore[unresolved-attribute]
                            ask=float(tick.ask),  # ty: ignore[unresolved-attribute]
                            last=float(tick.last),  # ty: ignore[unresolved-attribute]
                        )
                    )
        else:
            # Ruta rápida: el offset es constante en todo el chunk -> resta vectorizada
            # de un único `Timedelta` en vez de una llamada `astimezone()` por fila.
            offset = naive_min.replace(tzinfo=server_tz).utcoffset()
            utc_naive = naive_col - pd.Timedelta(offset)
            py_naive = utc_naive.dt.to_pydatetime()
            for ts_naive, bid, ask, last in zip(
                py_naive,
                frame["bid"].to_numpy(),
                frame["ask"].to_numpy(),
                frame["last"].to_numpy(),
                strict=True,
            ):
                timestamp_utc = ts_naive.replace(tzinfo=UTC)
                if window.start <= timestamp_utc < window.end:
                    rows.append(
                        TickRow(
                            timestamp_utc=timestamp_utc,
                            bid=float(bid),
                            ask=float(ask),
                            last=float(last),
                        )
                    )

    rows.sort(key=_TIMESTAMP_KEY)
    yield from rows


def _tick_in_bar_window(tick_timestamp: datetime, bar_timestamp: datetime) -> bool:
    """Criterio único de borde de la ventana de cobertura `(T-60s, T]` (RI-G5, ADR-G8).

    Compartido por `has_sufficient_tick_coverage` y el motor de fills de `simulator.py`
    para que ambos nunca discrepen sobre a qué vela pertenece un tick.
    """
    lower_bound = bar_timestamp - _COVERAGE_WINDOW
    return lower_bound < tick_timestamp <= bar_timestamp


def _bisect_window_bounds(day_ticks: Sequence[TickRow], bar_timestamp: datetime) -> tuple[int, int]:
    """Índices `[start, end)` de `day_ticks` en la ventana `(bar_timestamp - 60s, bar_timestamp]`.

    Asume `day_ticks` **ascendente** por `timestamp_utc` (R65/R101, invariante de
    `iter_ticks`); no reordena. Replica exactamente el borde `(T-60s, T]` de
    `_tick_in_bar_window` (estricto en el extremo bajo, cerrado en el alto) vía dos
    `bisect_right`: sobre una secuencia ordenada, `day_ticks[start:end]` es el mismo
    subconjunto contiguo que el filtrado lineal con `_tick_in_bar_window` (R107/R114).
    """
    lower_bound = bar_timestamp - _COVERAGE_WINDOW
    start_idx = bisect_right(day_ticks, lower_bound, key=_TIMESTAMP_KEY)
    end_idx = bisect_right(day_ticks, bar_timestamp, key=_TIMESTAMP_KEY)
    return (start_idx, end_idx)


def has_sufficient_tick_coverage(
    store: RawParquetStore,
    symbol: str,
    bar: AnnotatedBar,
    day_ticks: Sequence[TickRow],
    profile: FirmProfile,
) -> bool:
    """Criterio de dos niveles de cobertura suficiente de ticks para `bar` (R18, R68, R69).

    `True` si y solo si `(a)` existe **al menos uno** de los chunks de servidor
    candidatos (`_candidate_server_dates`, mismo helper que `iter_ticks`, R68) que
    intersectan el día de `bar` — condición **OR**, nunca AND (R69): con offset != 0
    puede haber solo un chunk persistido de los 1-N candidatos (p. ej. el del día
    siguiente aún no exportado) y, si ya cubre las velas reales de la sesión, exigir
    AND reportaría falsamente "sin cobertura" — y `(b)` hay al menos un tick en la
    ventana semiabierta-izquierda/cerrada-derecha `(bar.timestamp_utc - 60s,
    bar.timestamp_utc]` (tolerancia cero, Rg-3 §5.2, sin cambios).
    """
    window = _day_window(bar.trading_day)
    server_tz = ZoneInfo(profile.server_tz)
    chunk_exists = any(
        store.has_chunk(symbol, Granularity.TICK, _day_window(server_date))
        for server_date in _candidate_server_dates(window, server_tz)
    )
    if not chunk_exists:
        return False

    start_idx, end_idx = _bisect_window_bounds(day_ticks, bar.timestamp_utc)
    return start_idx < end_idx


def ticks_in_bar_window(bar: AnnotatedBar, day_ticks: Sequence[TickRow]) -> list[TickRow]:
    """Filtra `day_ticks` a los que caen en la ventana `(bar.timestamp_utc - 60s, T]`.

    Ordenados por `timestamp_utc` ascendente (forward-only); usado por el motor de
    fills de `simulator.py` (R35) — misma fuente de borde que `has_sufficient_tick_coverage`.
    `day_ticks` ya viene ascendente (invariante de `iter_ticks`), por lo que la slice
    de `_bisect_window_bounds` ya está ordenada (sin reordenar de nuevo).
    """
    start_idx, end_idx = _bisect_window_bounds(day_ticks, bar.timestamp_utc)
    return list(day_ticks[start_idx:end_idx])
