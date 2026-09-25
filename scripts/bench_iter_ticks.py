"""Benchmark ad-hoc antes/después de la vectorización de `iter_ticks` (Issue #24, R115).

Evidencia **no-pytest** (no bloquea `mise run ci`, Rg-13): mide el factor de
aceleración de la reescritura híbrida de `iter_ticks` (T4) frente a una referencia
escalar auto-contenida que replica literalmente el bucle pre-#24
(`frame.iterrows()` + `_to_utc` fila a fila). Ambas rutas parten del **mismo** frame
leído (mismo `RawParquetStore`, mismo chunk), por lo que la comparación es
reproducible en una sola corrida, sin `git stash`/`checkout` (ADR-24-8).

Incluye un **guard diferencial embebido**: si la ruta escalar y la vectorizada
divergen en algún tick, el script falla con `AssertionError` (refuerza la
bit-identidad como subproducto, no solo mide tiempos).

Uso:
    uv run python scripts/bench_iter_ticks.py
    uv run python scripts/bench_iter_ticks.py --symbol US500.cash --day 2026-06-10
    uv run python scripts/bench_iter_ticks.py --repeats 10 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

from genesis.backtest.ticks import (
    TickRow,
    _candidate_server_dates,
    _day_window,
    _has_dst_transition,
    _to_utc,
    iter_ticks,
)
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import ChunkWindow, Granularity, RawParquetStore

_DEFAULT_DATA_ROOT = "data/raw"
_DEFAULT_SYMBOL = "US500.cash"
_DEFAULT_PROFILE = "out/run_d/ftmo.json"


def _convert_scalar_reference(
    frame: pd.DataFrame, server_tz: ZoneInfo, window: ChunkWindow
) -> list[TickRow]:
    """Réplica del bucle pre-#24: `frame.iterrows()` + `_to_utc` fila a fila.

    Vive en `scripts/` (no en `src/genesis/backtest/ticks.py`, R97): el `iterrows`
    de esta referencia de benchmark no viola la prohibición de R97, acotada al
    módulo de producción.
    """
    rows: list[TickRow] = []
    for _, row in frame.iterrows():
        timestamp_utc = _to_utc(row["timestamp"], server_tz)
        if window.start <= timestamp_utc < window.end:
            rows.append(
                TickRow(
                    timestamp_utc=timestamp_utc,
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    last=float(row["last"]),
                )
            )
    return rows


def _convert_vectorized_tz_only(frame: pd.DataFrame, server_tz: ZoneInfo) -> list[datetime]:
    """Solo la conversión de huso vectorizada (sin filtrar ni construir `TickRow`).

    Aísla el coste de la conversión de huso (`conversión_tz`) del coste de construir
    `TickRow` por fila (`construcción_TickRow`), decisión residual #4 (spec §9).
    """
    naive_col = frame["timestamp"].dt.tz_localize(None)
    if naive_col.empty:
        return []
    naive_min = naive_col.iloc[0].to_pydatetime()
    naive_max = naive_col.iloc[-1].to_pydatetime()
    if _has_dst_transition(naive_min, naive_max, server_tz):
        return [_to_utc(tick, server_tz) for tick in frame["timestamp"]]
    offset = naive_min.replace(tzinfo=server_tz).utcoffset()
    utc_naive = naive_col - pd.Timedelta(offset)
    return [ts_naive.replace(tzinfo=UTC) for ts_naive in utc_naive.dt.to_pydatetime()]


def _convert_vectorized(
    frame: pd.DataFrame, server_tz: ZoneInfo, window: ChunkWindow
) -> list[TickRow]:
    """Espejo de la ruta híbrida de `iter_ticks` (T4): detección DST + resta vectorizada.

    Réplica fiel del cuerpo por-chunk de `iter_ticks`; ver `src/genesis/backtest/ticks.py`.
    """
    if frame.empty:
        return []
    naive_col = frame["timestamp"].dt.tz_localize(None)
    naive_min = naive_col.iloc[0].to_pydatetime()
    naive_max = naive_col.iloc[-1].to_pydatetime()

    rows: list[TickRow] = []
    if _has_dst_transition(naive_min, naive_max, server_tz):
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
    rows.sort(key=lambda tick: tick.timestamp_utc)
    return rows


def _iter_ticks_scalar_reference(
    store: RawParquetStore, symbol: str, trading_day: date, profile: FirmProfile
) -> list[TickRow]:
    """Réplica completa de `iter_ticks` pre-#24 (multi-chunk incluido) para el macro.

    Mismo bucle externo (`_candidate_server_dates`/`has_chunk`/`read_chunk`) que la
    producción; el único cambio es la conversión por chunk, que usa
    `_convert_scalar_reference` (escalar) en vez de la ruta híbrida.
    """
    window = _day_window(trading_day)
    server_tz = ZoneInfo(profile.server_tz)
    rows: list[TickRow] = []
    for server_date in _candidate_server_dates(window, server_tz):
        chunk_window = _day_window(server_date)
        if not store.has_chunk(symbol, Granularity.TICK, chunk_window):
            continue
        frame = store.read_chunk(symbol, Granularity.TICK, chunk_window)
        rows.extend(_convert_scalar_reference(frame, server_tz, window))
    rows.sort(key=lambda tick: tick.timestamp_utc)
    return rows


def _time(fn: Callable[[], object], repeats: int) -> float:
    """Mediana de `repeats` corridas de `fn`, en segundos (`time.perf_counter`)."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def _discover_symbol_days(data_root: Path, symbol: str) -> list[date]:
    """Fechas de servidor (`YYYY-MM-DD.parquet`) de los chunks de ticks persistidos."""
    tick_dir = data_root / symbol / Granularity.TICK.value
    files = sorted(tick_dir.glob("*/*.parquet"))
    return [date.fromisoformat(path.stem) for path in files]


def _chunk_path(data_root: Path, symbol: str, server_date: date) -> Path:
    return (
        data_root
        / symbol
        / Granularity.TICK.value
        / f"{server_date:%Y}"
        / f"{server_date:%Y-%m-%d}.parquet"
    )


def _busiest_day(data_root: Path, symbol: str, days: Iterable[date]) -> date:
    """Día de servidor con más filas persistidas (lectura de metadata, sin decodificar datos)."""
    best_day: date | None = None
    best_count = -1
    for day in days:
        num_rows = pq.ParquetFile(_chunk_path(data_root, symbol, day)).metadata.num_rows
        if num_rows > best_count:
            best_count = num_rows
            best_day = day
    if best_day is None:
        message = f"No hay chunks de ticks persistidos para symbol={symbol!r} en {data_root}."
        raise SystemExit(message)
    return best_day


def _run_micro_benchmark(
    store: RawParquetStore, symbol: str, day: date, profile: FirmProfile, repeats: int
) -> dict[str, Any]:
    server_tz = ZoneInfo(profile.server_tz)
    window = _day_window(day)
    frame = store.read_chunk(symbol, Granularity.TICK, window)

    # Guard diferencial embebido (R115): falla ruidosamente si diverge. Es una
    # herramienta de benchmark, no una suite de tests (S101 no aplica, cf. tests/**).
    scalar_rows = _convert_scalar_reference(frame, server_tz, window)
    vector_rows = _convert_vectorized(frame, server_tz, window)
    assert scalar_rows == vector_rows, (  # noqa: S101
        f"Divergencia escalar vs vectorizado en día micro {day.isoformat()}: "
        f"{len(scalar_rows)} vs {len(vector_rows)} ticks resultantes."
    )

    scalar_s = _time(lambda: _convert_scalar_reference(frame, server_tz, window), repeats)
    vector_s = _time(lambda: _convert_vectorized(frame, server_tz, window), repeats)
    tz_only_s = _time(lambda: _convert_vectorized_tz_only(frame, server_tz), repeats)

    return {
        "day": day.isoformat(),
        "n_ticks": len(frame),
        "n_ticks_en_ventana": len(vector_rows),
        "escalar_s": scalar_s,
        "vectorizado_s": vector_s,
        "factor": scalar_s / vector_s if vector_s > 0 else float("inf"),
        "conversion_tz_s": tz_only_s,
        "construccion_tickrow_s": max(vector_s - tz_only_s, 0.0),
    }


def _run_macro_benchmark(
    store: RawParquetStore, symbol: str, profile: FirmProfile, days: list[date]
) -> dict[str, Any]:
    """Recorre `iter_ticks` (vectorizado) y su réplica escalar sobre TODO el símbolo.

    Comparación día a día (no acumula ambas listas completas en memoria a la vez):
    guard diferencial embebido por `trading_day`, además del de `_run_micro_benchmark`.
    """
    scalar_total_s = 0.0
    vector_total_s = 0.0
    total_ticks = 0
    for trading_day in days:
        start = time.perf_counter()
        scalar_rows = _iter_ticks_scalar_reference(store, symbol, trading_day, profile)
        scalar_total_s += time.perf_counter() - start

        start = time.perf_counter()
        vector_rows = list(iter_ticks(store, symbol, trading_day, profile))
        vector_total_s += time.perf_counter() - start

        assert scalar_rows == vector_rows, (  # noqa: S101
            f"Divergencia macro escalar vs vectorizado en trading_day={trading_day.isoformat()}."
        )
        total_ticks += len(vector_rows)

    return {
        "n_dias": len(days),
        "n_ticks": total_ticks,
        "escalar_s": scalar_total_s,
        "vectorizado_s": vector_total_s,
        "factor": scalar_total_s / vector_total_s if vector_total_s > 0 else float("inf"),
    }


def _print_text_report(
    symbol: str, server_tz: str, repeats: int, micro: dict[str, Any], macro: dict[str, Any]
) -> None:
    print(
        f"Benchmark iter_ticks (Issue #24) — symbol={symbol} server_tz={server_tz} "
        f"repeats={repeats}"
    )
    print()
    print(
        f"[micro] día {micro['day']} ({micro['n_ticks']} ticks, "
        f"{micro['n_ticks_en_ventana']} en ventana)"
    )
    print(f"  escalar_s      = {micro['escalar_s']:.6f}")
    print(f"  vectorizado_s  = {micro['vectorizado_s']:.6f}")
    print(f"  factor         = {micro['factor']:.1f}x")
    print(f"  conversión_tz_s        = {micro['conversion_tz_s']:.6f}")
    print(f"  construcción_TickRow_s = {micro['construccion_tickrow_s']:.6f}")
    print()
    print(f"[macro] símbolo completo ({macro['n_dias']} días, {macro['n_ticks']} ticks)")
    print(f"  escalar_s      = {macro['escalar_s']:.3f}")
    print(f"  vectorizado_s  = {macro['vectorizado_s']:.3f}")
    print(f"  factor         = {macro['factor']:.1f}x")
    print()
    print("Guard diferencial: escalar == vectorizado (micro y macro, día a día) -> OK")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark antes/después de la vectorización de iter_ticks (Issue #24, R115). "
            "Evidencia no-pytest: no bloquea mise run ci."
        )
    )
    parser.add_argument("--data-root", default=_DEFAULT_DATA_ROOT, help="Raíz de RawParquetStore.")
    parser.add_argument("--symbol", default=_DEFAULT_SYMBOL, help="Símbolo a benchmarkear.")
    parser.add_argument(
        "--profile", default=_DEFAULT_PROFILE, help="Ficha de firma (server_tz), formato JSON."
    )
    parser.add_argument(
        "--day",
        default=None,
        help="Día ISO (YYYY-MM-DD) para el micro-benchmark; por defecto, el día con más ticks.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Repeticiones del micro-benchmark (mediana, time.perf_counter).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emite el reporte como JSON en vez de texto."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    data_root = Path(args.data_root)
    profile = load_firm_profile(Path(args.profile))
    store = RawParquetStore(data_root)

    days = _discover_symbol_days(data_root, args.symbol)
    if not days:
        message = f"No hay chunks de ticks persistidos para symbol={args.symbol!r} en {data_root}."
        raise SystemExit(message)

    micro_day = (
        date.fromisoformat(args.day) if args.day else _busiest_day(data_root, args.symbol, days)
    )

    micro = _run_micro_benchmark(store, args.symbol, micro_day, profile, args.repeats)
    macro = _run_macro_benchmark(store, args.symbol, profile, days)

    if args.json:
        payload = {
            "symbol": args.symbol,
            "server_tz": profile.server_tz,
            "repeats": args.repeats,
            "n_dias": len(days),
            "micro": micro,
            "macro": macro,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text_report(args.symbol, profile.server_tz, args.repeats, micro, macro)


if __name__ == "__main__":
    main()
