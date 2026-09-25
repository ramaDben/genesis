"""Lector de ticks forward-only propio sobre `RawParquetStore` (R15–R19, ADR-G6).

No añade métodos nuevos a `store.py`/`mt5_export.py` (capa 1 cerrada, R57): consume
exclusivamente `RawParquetStore.has_chunk`/`read_chunk`, ya públicos. La ausencia de
ticks para un `(symbol, trading_day)` es el caso normal (PA-2 de B), nunca una
excepción (R16); solo un chunk presente-pero-inválido lanza `BacktestConfigError`
(R17). `_day_window` y `has_sufficient_tick_coverage` comparten el mismo criterio de
borde de la ventana de cobertura `(T-60s, T]` (RI-G5, ADR-G8, Rg-3 §5.2).
"""

from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from operator import attrgetter
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from genesis.backtest.errors import BacktestConfigError
from genesis.data.profile import FirmProfile
from genesis.data.store import AnnotatedBar, ChunkWindow, Granularity, RawParquetStore

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


_DEFAULT_MAX_CACHED_DAYS = 2
"""Días de ticks vivos a la vez: el actual y el anterior, por si un fill mira atrás."""


class TickCache:
    """Ticks por `(símbolo, trading_day)` con evicción LRU **acotada** (Change #46).

    Existe por dos motivos distintos, y conviene no confundirlos:

    1. **Cota de memoria** (el motivo principal). El caché que vivía dentro de cada
       `Simulator` no evictaba nunca: sobre 173 días de `US500` retenía 4,0 GB medidos, y
       una ventana IS+OOS de 378 días proyecta ~8,7 GB por símbolo — más de lo que tiene
       la máquina. Con la cota, el techo es de dos días (~80 MB).
    2. **Compartir entre combos**. Se construye una vez por ventana y se inyecta en cada
       `Simulator`, de modo que varios backtests sobre el mismo tramo puedan reutilizar la
       lectura en vez de repetirla.

    Sobre el punto 2, sin adornos: con los 27 combos del WFA corriendo **en serie**, cada
    uno recorre los días de principio a fin, así que una cota de dos días no alcanza para
    que el combo siguiente encuentre nada cacheado. El ahorro de I/O real exige recorrer
    los días una vez con los combos avanzando en paralelo, que es trabajo aparte y
    condicionado a medición. Donde sí ahorra hoy es en tramos cortos revisitados —el OOS
    de `run_sensitivity`, nueve backtests sobre el mismo slice—.

    `max_days` es ajustable para quien pueda permitirse más memoria a cambio de más
    aciertos; el default no obliga a nadie a recordar apagar nada.
    """

    def __init__(self, *, max_days: int = _DEFAULT_MAX_CACHED_DAYS) -> None:
        if max_days < 1:
            message = f"TickCache.max_days={max_days!r} debe ser >= 1 (Change #46, R33)."
            raise BacktestConfigError(message)
        self._max_days = max_days
        self._entries: OrderedDict[tuple[str, date], list[TickRow]] = OrderedDict()
        self._chunk_exists: dict[tuple[str, date], bool] = {}

    def ticks_for_day(
        self,
        store: RawParquetStore,
        symbol: str,
        trading_day: date,
        profile: FirmProfile,
    ) -> list[TickRow]:
        """Ticks de `(symbol, trading_day)`, leídos del store solo si no están cacheados."""
        key = (symbol, trading_day)
        cached = self._entries.get(key)
        if cached is not None:
            self._entries.move_to_end(key)
            return cached

        ticks = list(iter_ticks(store, symbol, trading_day, profile))
        self._entries[key] = ticks
        while len(self._entries) > self._max_days:
            # Evicción hacia atrás (el menos recientemente usado): nunca prefetch de días
            # futuros, que rompería el anti-lookahead.
            self._entries.popitem(last=False)
        return ticks

    def has_chunk_for_day(
        self,
        store: RawParquetStore,
        symbol: str,
        trading_day: date,
        profile: FirmProfile,
    ) -> bool:
        """`chunk_exists_for_day` memoizado por `(símbolo, día)` (Change #46, R38).

        Se consultaba una vez por barra —1-3 `Path.exists()` cada vez, 232.833 llamadas
        medidas en una corrida de 173 días— para un valor que solo cambia de día en día.

        No participa de la evicción LRU: guardar un booleano por día no cuesta memoria
        apreciable, y recalcularlo sí cuesta syscalls.
        """
        key = (symbol, trading_day)
        cached = self._chunk_exists.get(key)
        if cached is None:
            cached = chunk_exists_for_day(store, symbol, trading_day, profile)
            self._chunk_exists[key] = cached
        return cached

    def cached_days(self) -> int:
        """Días vivos en el caché. Existe para que los tests puedan afirmar la cota."""
        return len(self._entries)


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


def chunk_exists_for_day(
    store: RawParquetStore,
    symbol: str,
    trading_day: date,
    profile: FirmProfile,
) -> bool:
    """Condición (a) de la cobertura: existe algún chunk de servidor para `trading_day`.

    Depende solo del día, nunca de la barra: es la mitad memoizable del criterio, y la
    cara —cada evaluación son 1-3 `Path.exists()`— (Change #46, R38).
    """
    window = _day_window(trading_day)
    server_tz = ZoneInfo(profile.server_tz)
    return any(
        store.has_chunk(symbol, Granularity.TICK, _day_window(server_date))
        for server_date in _candidate_server_dates(window, server_tz)
    )


def has_ticks_in_bar_window(bar: AnnotatedBar, day_ticks: Sequence[TickRow]) -> bool:
    """Condición (b) de la cobertura: hay al menos un tick en la ventana de `bar`."""
    start_idx, end_idx = _bisect_window_bounds(day_ticks, bar.timestamp_utc)
    return start_idx < end_idx


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

    El criterio y su orden de evaluación son los mismos de siempre; lo único nuevo es que
    cada condición vive en su propia función, para que quien recorra muchas barras del
    mismo día pueda memoizar la parte (a), que solo depende del día (Change #46, R38).
    """
    if not chunk_exists_for_day(store, symbol, bar.trading_day, profile):
        return False
    return has_ticks_in_bar_window(bar, day_ticks)


def ticks_in_bar_window(bar: AnnotatedBar, day_ticks: Sequence[TickRow]) -> list[TickRow]:
    """Filtra `day_ticks` a los que caen en la ventana `(bar.timestamp_utc - 60s, T]`.

    Ordenados por `timestamp_utc` ascendente (forward-only); usado por el motor de
    fills de `simulator.py` (R35) — misma fuente de borde que `has_sufficient_tick_coverage`.
    `day_ticks` ya viene ascendente (invariante de `iter_ticks`), por lo que la slice
    de `_bisect_window_bounds` ya está ordenada (sin reordenar de nuevo).
    """
    start_idx, end_idx = _bisect_window_bounds(day_ticks, bar.timestamp_utc)
    return list(day_ticks[start_idx:end_idx])
