"""Lectura normalizada tz-servidor → UTC, forward-only, con marcas de día y sesión.

`iter_bars` es un generador: la única forma de consumo es iteración monotónica hacia
adelante (R32) — no expone acceso por índice absoluto ni una forma de adelantar el
cursor para inspeccionar filas futuras. La excepción de lookahead de la capa de
estrategia no se implementa en este Change (PA-4 es de Issue C, fuera de alcance; ver
spec §11.1).
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from genesis.data.errors import GenesisDataError
from genesis.data.metadata import ArtifactMetadata, sha256_of
from genesis.data.profile import FirmProfile
from genesis.data.sessions import session_window


class DayBoundaryError(GenesisDataError):
    """Corte de día inconsistente con `daily_reset_time` de la ficha activa (R30)."""


class Granularity(StrEnum):
    """Granularidad de descarga: M1 (troceado por meses) o ticks (troceado por días)."""

    M1 = "m1"
    TICK = "tick"


@dataclass(frozen=True, slots=True)
class ChunkWindow:
    """Sub-rango temporal `[start, end]` planificado por `plan_chunks`."""

    start: datetime
    end: datetime


_CANONICAL_COLUMN_ORDER = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "bid",
    "ask",
    "last",
)


def _next_month_boundary(moment: datetime) -> datetime:
    """Primer instante (00:00) del mes calendario siguiente al de `moment`."""
    if moment.month == 12:
        return moment.replace(
            year=moment.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return moment.replace(month=moment.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _one_day_later(moment: datetime) -> datetime:
    return moment + timedelta(days=1)


def plan_chunks(start: datetime, end: datetime, granularity: Granularity) -> list[ChunkWindow]:
    """Trocea `[start, end]` en sub-rangos ordenados y sin solapes que cubren el rango exacto.

    M1 se trocea por meses calendario; ticks por días (spec §4.1, ADR-4). Función pura,
    sin I/O: la unión de los `ChunkWindow` retornados cubre exactamente `[start, end]`
    (R5); property-testeable con `hypothesis` (R53).

    Lanza `GenesisDataError` si `start > end`.
    """
    if start > end:
        message = f"Rango temporal inválido para plan_chunks: start={start!r} > end={end!r}."
        raise GenesisDataError(message)
    if start == end:
        return [ChunkWindow(start=start, end=end)]

    step = _next_month_boundary if granularity is Granularity.M1 else _one_day_later

    boundaries = [start]
    cursor = step(start)
    while cursor < end:
        boundaries.append(cursor)
        cursor = step(cursor)
    boundaries.append(end)

    return [
        ChunkWindow(start=segment_start, end=segment_end)
        for segment_start, segment_end in pairwise(boundaries)
    ]


def _chunk_filename(window: ChunkWindow, granularity: Granularity) -> str:
    if granularity is Granularity.M1:
        return f"{window.start:%Y-%m}.parquet"
    return f"{window.start:%Y-%m-%d}.parquet"


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normaliza un frame crudo a orden de columnas y dtypes canónicos (ADR-2/ADR-3)."""
    ordered_columns = [column for column in _CANONICAL_COLUMN_ORDER if column in frame.columns]
    normalized = frame[ordered_columns].copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    return normalized.sort_values("timestamp").reset_index(drop=True)


class RawParquetStore:
    """Store cache-first de Parquet crudo (ADR-2): `root/<symbol>/<gran>/<YYYY>/<file>`.

    M1 se persiste un archivo por mes calendario; ticks un archivo por día. Cada chunk
    lleva un sidecar `<file>.meta.json` (`ArtifactMetadata`) y un índice
    `root/_manifest.json` (`chunk_hash -> ruta relativa`) para lookup O(1) por hash.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _chunk_path(self, symbol: str, granularity: Granularity, window: ChunkWindow) -> Path:
        return (
            self._root
            / symbol
            / granularity.value
            / f"{window.start:%Y}"
            / _chunk_filename(window, granularity)
        )

    def chunk_hash(self, frame: pd.DataFrame) -> str:
        """Hash `sha256` determinista sobre el contenido crudo normalizado de `frame`.

        Se calcula sobre los valores del frame (dtypes/orden de columnas fijos), no sobre
        los bytes del archivo Parquet (ADR-3): dos frames con el mismo contenido producen
        siempre el mismo hash, independientemente del orden original de columnas/filas.
        """
        normalized = _normalize_frame(frame)
        canonical_bytes = normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
        return sha256_of(canonical_bytes)

    def has_chunk(self, symbol: str, granularity: Granularity, window: ChunkWindow) -> bool:
        """`True` si el chunk `(symbol, granularity, window)` ya está persistido (R8)."""
        return self._chunk_path(symbol, granularity, window).exists()

    def read_chunk(
        self, symbol: str, granularity: Granularity, window: ChunkWindow
    ) -> pd.DataFrame:
        """Lee el chunk ya persistido para `(symbol, granularity, window)`."""
        path = self._chunk_path(symbol, granularity, window)
        return pd.read_parquet(path)

    def write_chunk(
        self,
        frame: pd.DataFrame,
        symbol: str,
        granularity: Granularity,
        window: ChunkWindow,
        metadata: ArtifactMetadata,
    ) -> Path:
        """Persiste `frame` de forma determinista y adjunta `metadata` en un sidecar.

        Escritura Parquet con parámetros fijos (ADR-3): orden de columnas canónico,
        `preserve_index=False`, timestamps en microsegundos, compresión `zstd` fija y sin
        metadata de esquema variable (se elimina la metadata `pandas` embebida por
        pyarrow), de modo que dos escrituras del mismo frame produzcan archivos
        bit-idénticos.
        """
        normalized = _normalize_frame(frame)
        path = self._chunk_path(symbol, granularity, window)
        path.parent.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pandas(normalized, preserve_index=False)
        table = table.replace_schema_metadata({})
        pq.write_table(
            table,
            path,
            compression="zstd",
            coerce_timestamps="us",
            allow_truncated_timestamps=True,
            use_deprecated_int96_timestamps=False,
            write_statistics=False,
        )

        sidecar = path.with_suffix(".meta.json")
        sidecar.write_text(metadata.to_json(), encoding="utf-8")

        manifest_path = self._root / "_manifest.json"
        manifest: dict[str, str] = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest[metadata.dataset_hash] = str(path.relative_to(self._root))
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        return path


@dataclass(frozen=True, slots=True)
class AnnotatedBar:
    """Barra M1 anotada: timestamp UTC, día de trading y ventana de sesión.

    `session_open_utc`/`session_close_utc` son la ventana de contado del `trading_day` de
    la barra. Se propagan —en vez de quedarse solo con el booleano `in_session` derivado—
    porque la capa 3 necesita el borde exacto para el cierre forzado de sesión, y
    recalcularlo allí significaba invocar `session_window` dos veces por barra.

    Ambos campos son obligatorios: un default `None` convertiría un error de construcción
    en un fallo silencioso aguas abajo.
    """

    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    trading_day: date
    in_session: bool
    session_open_utc: datetime
    session_close_utc: datetime


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

    La ventana de sesión se resuelve **una vez por `trading_day`** y se propaga en la
    barra: `session_window` es pura y su resultado solo depende del día, así que
    invocarla por barra era recomputar lo mismo ~390 veces por sesión (Change #46, R8).

    Único punto de emisión: no expone acceso por índice absoluto ni un método para
    reposicionar el cursor de lectura (R32); la excepción de lookahead de la capa de
    estrategia no se implementa en este Change (R33, PA-4 = Issue C).
    """
    server_tz = ZoneInfo(profile.server_tz)
    previous_trading_day: date | None = None
    session_bounds: tuple[datetime, datetime] | None = None

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

        if trading_day != previous_trading_day or session_bounds is None:
            session_bounds = session_window(symbol, trading_day)
        previous_trading_day = trading_day

        open_utc, close_utc = session_bounds
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
            session_open_utc=open_utc,
            session_close_utc=close_utc,
        )
