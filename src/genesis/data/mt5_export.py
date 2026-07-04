"""Adaptador delgado sobre el SDK `MetaTrader5`, expuesto también como CLI `mt5-export`.

Descarga M1 OHLCV + `tick_volume`, ticks (`copy_ticks_range`) y la ficha extendida del
símbolo, con separación estricta de cuenta (spec §4.1: guard de cuenta demo/investor
antes de cualquier descarga) y troceo secuencial "buen ciudadano" (pausa + backoff).

El SDK `MetaTrader5` es Windows-only y requiere terminal vivo: se importa de forma
perezosa (nunca a nivel de módulo, R2/R35), de modo que `import genesis.data.mt5_export`
no falla en una plataforma sin el paquete instalado.
"""

import json
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from genesis.data.errors import GenesisDataError
from genesis.data.metadata import CONFIG_VERSION, ArtifactMetadata, current_git_commit, sha256_of
from genesis.data.profile import FirmProfile, SymbolAliases, firm_profile_hash
from genesis.data.symbols import SymbolFigure

# Valor documentado del SDK MetaTrader5 para `account_info().trade_mode` en cuentas demo
# (`MetaTrader5.ACCOUNT_TRADE_MODE_DEMO == 0`); se replica como constante local para no
# requerir importar el SDK a nivel de módulo (R2/R35).
_ACCOUNT_TRADE_MODE_DEMO = 0
# TIMEFRAME_M1 y COPY_TICKS_ALL del SDK MetaTrader5, replicados como constantes locales
# por el mismo motivo (`MetaTrader5.TIMEFRAME_M1 == 1`, `MetaTrader5.COPY_TICKS_ALL == -1`).
_TIMEFRAME_M1 = 1
_COPY_TICKS_ALL = -1

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


class AccountScopeError(GenesisDataError):
    """Cuenta con permiso de trading real/challenge detectada al conectar (R3)."""


class Granularity(StrEnum):
    """Granularidad de descarga: M1 (troceado por meses) o ticks (troceado por días)."""

    M1 = "m1"
    TICK = "tick"


@dataclass(frozen=True, slots=True)
class ChunkWindow:
    """Sub-rango temporal `[start, end]` planificado por `plan_chunks`."""

    start: datetime
    end: datetime


class Mt5Terminal(Protocol):
    """Puerto con la superficie mínima usada del SDK `MetaTrader5` (R1, R34).

    Permite testear la orquestación de `mt5_export.py` con un `FakeMt5Terminal`
    determinista, sin conexión real ni el paquete `MetaTrader5` instalado.
    """

    def initialize(self, *args: object, **kwargs: object) -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> tuple[int, str]: ...

    def account_info(self) -> object: ...

    def symbols_get(self, group: str | None = None) -> tuple[object, ...]: ...

    def symbol_info(self, symbol: str) -> object: ...

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: datetime, date_to: datetime
    ) -> object: ...

    def copy_ticks_range(
        self, symbol: str, date_from: datetime, date_to: datetime, flags: int
    ) -> object: ...


class RealMt5Terminal:
    """Implementa `Mt5Terminal` importando `MetaTrader5` de forma perezosa (ADR-1).

    El import del SDK ocurre dentro de `__init__`, nunca a nivel de módulo: en una
    plataforma sin `MetaTrader5` instalado, `import genesis.data.mt5_export` sigue
    funcionando; solo instanciar `RealMt5Terminal` requiere el SDK presente.
    """

    def __init__(self) -> None:
        import MetaTrader5 as _mt5  # noqa: N813 (nombre del SDK, no controlado por este repo)

        # El SDK no publica stubs de tipos completos: se aísla como `Any` tras este único
        # punto de import perezoso; el `Protocol` Mt5Terminal es el contrato tipado real.
        self._mt5: Any = _mt5

    def initialize(self, *args: object, **kwargs: object) -> bool:
        return bool(self._mt5.initialize(*args, **kwargs))

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def last_error(self) -> tuple[int, str]:
        return self._mt5.last_error()

    def account_info(self) -> object:
        return self._mt5.account_info()

    def symbols_get(self, group: str | None = None) -> tuple[object, ...]:
        result = self._mt5.symbols_get(group) if group is not None else self._mt5.symbols_get()
        return tuple(result) if result is not None else ()

    def symbol_info(self, symbol: str) -> object:
        return self._mt5.symbol_info(symbol)

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: datetime, date_to: datetime
    ) -> object:
        return self._mt5.copy_rates_range(symbol, timeframe, date_from, date_to)

    def copy_ticks_range(
        self, symbol: str, date_from: datetime, date_to: datetime, flags: int
    ) -> object:
        return self._mt5.copy_ticks_range(symbol, date_from, date_to, flags)


def _next_month_boundary(moment: datetime) -> datetime:
    """Primer instante (00:00) del mes calendario siguiente al de `moment`."""
    if moment.month == 12:
        return moment.replace(
            year=moment.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return moment.replace(month=moment.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


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


def _one_day_later(moment: datetime) -> datetime:
    return moment + timedelta(days=1)


def backoff_delay(attempt: int, *, base: float = 0.5, cap: float = 60.0) -> float:
    """Retorna la pausa de backoff exponencial para el intento `attempt` (R6).

    Monótonamente creciente con `attempt` (`base * 2**attempt`), acotada por `cap`.
    """
    return min(base * (2**attempt), cap)


def resolve_symbol_alias(
    conventional_name: str,
    available_symbols: Sequence[str],
    expected_table: Mapping[str, SymbolAliases],
) -> str:
    """Resuelve el símbolo MT5 real para `conventional_name` (R9).

    Intenta primero el símbolo esperado (`expected_table[conventional_name].expected`);
    si no está en `available_symbols`, prueba los alias documentados en orden. Nunca
    adivina: si nada coincide, o si `conventional_name` no está documentado en
    `expected_table`, lanza `GenesisDataError` con contexto (símbolo buscado, candidatos
    probados, símbolos disponibles).
    """
    if conventional_name not in expected_table:
        message = (
            f"Símbolo convencional '{conventional_name}' no está documentado en la tabla de "
            f"la ficha de firma. Símbolos documentados: {sorted(expected_table)}."
        )
        raise GenesisDataError(message)

    aliases = expected_table[conventional_name]
    candidates = (aliases.expected, *aliases.aliases)
    for candidate in candidates:
        if candidate in available_symbols:
            return candidate

    message = (
        f"No se encontró símbolo MT5 para '{conventional_name}' entre los candidatos "
        f"{candidates} ni en los símbolos disponibles del terminal: {list(available_symbols)}."
    )
    raise GenesisDataError(message)


def assert_demo_account(terminal: Mt5Terminal) -> None:
    """Valida que `terminal.account_info().trade_mode` sea una cuenta demo/investor (R3).

    Lanza `AccountScopeError` con contexto si la cuenta conectada tiene permiso de
    trading real/challenge. Debe invocarse antes de cualquier llamada de descarga.
    """
    account = terminal.account_info()
    trade_mode = getattr(account, "trade_mode", None)
    if trade_mode != _ACCOUNT_TRADE_MODE_DEMO:
        message = (
            f"La cuenta conectada tiene trade_mode={trade_mode!r} (se esperaba "
            f"{_ACCOUNT_TRADE_MODE_DEMO!r}, cuenta demo/investor). Abortando antes de "
            "cualquier descarga (spec §4.1: separación estricta de cuenta)."
        )
        raise AccountScopeError(message)


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
class ExportResult:
    """Resultado del export de un símbolo convencional (R10, R39)."""

    symbol: str
    resolved_symbol: str
    figure: SymbolFigure
    chunks_written: int
    chunks_cached: int


def _raw_to_frame(raw: object) -> pd.DataFrame:
    """Normaliza el retorno crudo de `copy_rates_range`/`copy_ticks_range` a `pd.DataFrame`.

    Acepta tanto un `pd.DataFrame` ya construido (fakes de test) como cualquier
    estructura tabular con una columna `time` en segundos epoch (numpy structured array
    del SDK real `MetaTrader5`), que se renombra y convierte a `timestamp` UTC.
    """
    frame = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
    if "timestamp" not in frame.columns and "time" in frame.columns:
        frame = frame.rename(columns={"time": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    return frame


def _coerce_symbol_figure(symbol: str, raw: Any) -> SymbolFigure:
    """Convierte la ficha extendida cruda del SDK (o de un fake) a `SymbolFigure` (R10).

    `raw` puede ser ya un `SymbolFigure` (fakes de test) o el objeto `SymbolInfo` del SDK
    real `MetaTrader5` (sin stubs de tipos, de ahí `Any`): en ese caso se leen sus
    atributos documentados (`trade_tick_value`, `volume_step`, `trade_stops_level`,
    `trade_freeze_level`, `digits`, `swap_long`, `swap_short`, `swap_rollover3days`).
    """
    if isinstance(raw, SymbolFigure):
        return raw
    return SymbolFigure(
        symbol=symbol,
        tick_value=float(raw.trade_tick_value),
        volume_step=float(raw.volume_step),
        stops_level=int(raw.trade_stops_level),
        freeze_level=int(raw.trade_freeze_level),
        digits=int(raw.digits),
        swap_long=float(raw.swap_long),
        swap_short=float(raw.swap_short),
        swap_rollover_day=int(raw.swap_rollover3days),
    )


def _call_with_backoff(func: Any, *args: object, max_retries: int) -> object:
    """Invoca `func(*args)` con reintentos y backoff exponencial ante error de servidor."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return func(*args)
        except OSError as exc:
            last_exc = exc
            time.sleep(backoff_delay(attempt))
    message = f"Descarga fallida tras {max_retries} intentos consecutivos: {last_exc}"
    raise GenesisDataError(message) from last_exc


def run_export(
    terminal: Mt5Terminal,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    profile: FirmProfile,
    store: RawParquetStore,
    *,
    pause_range: tuple[float, float] = (0.5, 2.0),
    max_retries: int = 5,
) -> list[ExportResult]:
    """Orquesta el export secuencial y troceado de `symbols` en `[start, end]`.

    Guard de cuenta (`assert_demo_account`) antes de cualquier descarga; resuelve el
    símbolo real vía `resolve_symbol_alias`; trocea con `plan_chunks` (M1 por meses,
    ticks por días); descarga un símbolo a la vez, cache-first (`RawParquetStore.has_chunk`);
    aplica `pause_range` entre peticiones y `backoff_delay` ante error de servidor;
    persiste cada chunk con `ArtifactMetadata` (R39). Fail-fast con contexto
    (símbolo/rango/causa) para configuración o ficha inválida (R38).
    """
    terminal.initialize()
    try:
        assert_demo_account(terminal)

        available_symbols = [
            getattr(item, "name")  # noqa: B009 (item es `object`; ty exige acceso indirecto)
            for item in terminal.symbols_get()
        ]
        results: list[ExportResult] = []

        for conventional_symbol in symbols:
            resolved_symbol = resolve_symbol_alias(
                conventional_symbol, available_symbols, profile.symbols
            )
            figure = _coerce_symbol_figure(resolved_symbol, terminal.symbol_info(resolved_symbol))

            chunks_written = 0
            chunks_cached = 0
            for granularity in (Granularity.M1, Granularity.TICK):
                for window in plan_chunks(start, end, granularity):
                    if store.has_chunk(resolved_symbol, granularity, window):
                        chunks_cached += 1
                        continue

                    if granularity is Granularity.M1:
                        raw = _call_with_backoff(
                            terminal.copy_rates_range,
                            resolved_symbol,
                            _TIMEFRAME_M1,
                            window.start,
                            window.end,
                            max_retries=max_retries,
                        )
                    else:
                        raw = _call_with_backoff(
                            terminal.copy_ticks_range,
                            resolved_symbol,
                            window.start,
                            window.end,
                            _COPY_TICKS_ALL,
                            max_retries=max_retries,
                        )
                    frame = _raw_to_frame(raw)
                    metadata = ArtifactMetadata(
                        config_version=CONFIG_VERSION,
                        dataset_hash=store.chunk_hash(frame),
                        firm_profile_hash=firm_profile_hash(profile),
                        time_range=(window.start, window.end),
                        git_commit=current_git_commit(),
                        symbol_figure=figure,
                    )
                    store.write_chunk(frame, resolved_symbol, granularity, window, metadata)
                    chunks_written += 1

                    pause_low, pause_high = pause_range
                    if pause_high > 0:
                        time.sleep(random.uniform(pause_low, pause_high))  # noqa: S311 # nosec B311

            results.append(
                ExportResult(
                    symbol=conventional_symbol,
                    resolved_symbol=resolved_symbol,
                    figure=figure,
                    chunks_written=chunks_written,
                    chunks_cached=chunks_cached,
                )
            )

        return results
    finally:
        terminal.shutdown()
