"""Benchmark y perfilado del diagnóstico de señal desnuda (§2.2.1).

Evidencia **no-pytest** (no bloquea `mise run ci`, Rg-13), en la línea de
`bench_iter_ticks.py`: mide por separado las tres etapas del diagnóstico y
permite perfilar la más costosa con `cProfile`.

Dos fuentes de barras, según lo que haya disponible:

- `--from-store <símbolo>` lee los Parquet reales de `data/raw/<símbolo>/m1/`. Es la
  medición representativa: tamaño y tasa de eventos CT verdaderos.
- `--bars N` genera un frame sintético, para entornos sin datos de MT5 (CI incluido).

**Limitación del modo sintético.** Emite timestamps naive contiguos que `iter_bars`
reinterpreta como hora local del servidor; al cruzar una transición DST la
secuencia deja de ser monótona en UTC y el reloj de la capa 2 aborta con
`LookaheadError` — correctamente, porque el dato de entrada es inválido. Por eso
`_MAX_SYNTHETIC_BARS` acota el rango sintético a la ventana que no alcanza la
transición de marzo. Para medir por encima de ese tope hay que usar
`--from-store`. Los datos reales no tienen el problema: MT5 no emite barras en
horas inexistentes ni repetidas (verificado sobre las 17 particiones de
`US500.cash` y `EURUSD`, cero retrocesos y cero naive duplicados).

Limitación de ambas fuentes: no se ejercita `estimate_roundtrip_cost` (capa 4),
que lee ticks. El coste de esa etapa queda fuera de esta medición.

Uso:
    uv run python scripts/bench_diagnose.py --from-store US500.cash
    uv run python scripts/bench_diagnose.py --bars 20000
    uv run python scripts/bench_diagnose.py --from-store US500.cash --profile-stage detect
    uv run python scripts/bench_diagnose.py --json
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import iter_bars
from genesis.strategy.candidate_a.config import CandidateAConfig, load_candidate_a_config
from genesis.strategy.candidate_a.diagnostics import detect_ct_events, summarize_raw_edge

_DEFAULT_BARS = 78_000
_DEFAULT_SYMBOL = "US500"
"""Nombre canónico de la tabla de sesiones (sin el sufijo del broker, p. ej. `.cash`)."""
_DEFAULT_SESSION = "londres-ny"
_SYNTHETIC_START = datetime(2026, 1, 5, 0, 0)
_MAX_SYNTHETIC_BARS = 110_000
"""Tope del modo sintético: 110k minutos desde `_SYNTHETIC_START` llegan al 2026-03-21,
antes de la transición DST europea del 29 de marzo. Cruzarla haría que la secuencia
naive deje de ser monótona en UTC y el reloj de la capa 2 abortaría con
`LookaheadError`. Para medir por encima de este tope, usar `--from-store`."""

_STORE_ROOT = Path("data/raw")


def synthetic_m1_frame(n_bars: int, seed: int = 7) -> pd.DataFrame:
    """Frame M1 contiguo y reproducible: random walk con rango intrabar no degenerado."""
    if n_bars > _MAX_SYNTHETIC_BARS:
        raise SystemExit(
            f"--bars {n_bars:,} excede el tope sintético de {_MAX_SYNTHETIC_BARS:,}: el rango "
            f"cruzaría la transición DST del 2026-03-29 y la secuencia dejaría de ser monótona "
            f"en UTC (LookaheadError en la capa 2). Usá --from-store <símbolo> para medir con "
            f"el tamaño real del dataset."
        )
    rng = np.random.default_rng(seed)
    close = 5000.0 + rng.normal(0.0, 0.35, size=n_bars).cumsum()
    half_range = np.abs(rng.normal(0.0, 0.8, size=n_bars))
    return pd.DataFrame(
        {
            "timestamp": [_SYNTHETIC_START + timedelta(minutes=i) for i in range(n_bars)],
            "open": close - rng.normal(0.0, 0.2, size=n_bars),
            "high": close + half_range,
            "low": close - half_range,
            "close": close,
            "tick_volume": rng.integers(20, 400, size=n_bars),
        }
    )


def store_m1_frame(symbol: str, limit: int | None = None) -> pd.DataFrame:
    """Concatena las particiones M1 reales de `symbol` desde el store Parquet."""
    partitions = sorted((_STORE_ROOT / symbol / "m1").rglob("*.parquet"))
    if not partitions:
        raise SystemExit(
            f"No hay particiones M1 para '{symbol}' en {_STORE_ROOT}/{symbol}/m1/. "
            f"Restaurá el dataset con: gh release download dataset-ftmo-2026-08-01 "
            f"-R ramaDben/genesis"
        )
    frame = pd.concat([pd.read_parquet(p) for p in partitions], ignore_index=True)
    if limit is not None:
        frame = frame.head(limit)
    return frame


def _resolve_profile(explicit: str | None) -> FirmProfile:
    """Ficha de firma: la indicada, o la primera candidata que exista en disco."""
    candidates = (
        [explicit]
        if explicit
        else ["out/run_d/ftmo.json", "~/genesis-artifacts/out/run_d/ftmo.json"]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return load_firm_profile(path)
    raise SystemExit(
        "No se encontró una ficha de firma. Pasá --profile con la ruta de ftmo.json "
        "(el release archive-2026-07-28 la incluye en out/run_d/)."
    )


def _stage_times(
    frame: pd.DataFrame, profile: FirmProfile, config: CandidateAConfig, symbol: str, session: str
) -> tuple[dict[str, Any], list, list]:
    """Cronometra las tres etapas y devuelve también sus salidas, para reutilizarlas."""
    measured: dict[str, Any] = {}

    t0 = time.perf_counter()
    bars = list(iter_bars(frame, symbol, profile))
    measured["iter_bars_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    events = detect_ct_events(bars, config, symbol, session)
    measured["detect_ct_events_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    summarize_raw_edge(bars, events, config)
    measured["summarize_raw_edge_s"] = time.perf_counter() - t0

    measured["n_bars"] = len(bars)
    measured["n_events"] = len(events)
    measured["total_s"] = (
        measured["iter_bars_s"] + measured["detect_ct_events_s"] + measured["summarize_raw_edge_s"]
    )
    return measured, bars, events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, default=_DEFAULT_BARS)
    parser.add_argument(
        "--from-store",
        default=None,
        metavar="SIMBOLO",
        help="lee las barras reales del store (p. ej. US500.cash) en vez de sintetizarlas",
    )
    parser.add_argument("--limit", type=int, default=None, help="corta las barras del store")
    parser.add_argument("--symbol", default=_DEFAULT_SYMBOL)
    parser.add_argument("--session", default=_DEFAULT_SESSION)
    parser.add_argument("--profile", default=None, help="ruta de la ficha de firma (ftmo.json)")
    parser.add_argument("--profile-stage", choices=["iter_bars", "detect", "summarize"])
    parser.add_argument("--top", type=int, default=12, help="filas de cProfile a mostrar")
    parser.add_argument("--symbols", type=int, default=8, help="símbolos para extrapolar")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    firm_profile = _resolve_profile(args.profile)
    config = load_candidate_a_config()

    if args.from_store:
        frame = store_m1_frame(args.from_store, args.limit)
        fuente = f"store:{args.from_store}"
    else:
        frame = synthetic_m1_frame(args.bars)
        fuente = "sintetico"

    measured, bars, events = _stage_times(frame, firm_profile, config, args.symbol, args.session)
    measured["horizons_minutes"] = list(config.diagnostics.horizons_minutes)
    measured["extrapolated_min"] = measured["total_s"] * args.symbols / 60
    measured["source"] = fuente

    if args.json:
        print(json.dumps(measured, indent=2))
    else:
        total = measured["total_s"]
        print(
            f"fuente={fuente}  barras={measured['n_bars']:,}  "
            f"eventos CT={measured['n_events']:,}  "
            f"horizontes={measured['horizons_minutes']}\n"
        )
        for label, key in (
            ("iter_bars (capa 1)", "iter_bars_s"),
            ("detect_ct_events (capa 2)", "detect_ct_events_s"),
            ("summarize_raw_edge (capa 2)", "summarize_raw_edge_s"),
        ):
            seconds = measured[key]
            pct = 100 * seconds / total if total else 0.0
            print(f"  {label:<30} {seconds:8.2f}s  {pct:5.1f}%  {'#' * int(pct / 2)}")
        print(f"  {'TOTAL':<30} {total:8.2f}s")
        print(f"\nExtrapolado a {args.symbols} símbolos: {measured['extrapolated_min']:.1f} min")

    if args.profile_stage:
        targets = {
            "iter_bars": lambda: list(iter_bars(frame, args.symbol, firm_profile)),
            "detect": lambda: detect_ct_events(bars, config, args.symbol, args.session),
            "summarize": lambda: summarize_raw_edge(bars, events, config),
        }
        profiler = cProfile.Profile()
        profiler.enable()
        targets[args.profile_stage]()
        profiler.disable()
        buffer = io.StringIO()
        pstats.Stats(profiler, stream=buffer).sort_stats("tottime").print_stats(args.top)
        print(f"\n--- cProfile de {args.profile_stage} (ordenado por tiempo propio) ---")
        print(buffer.getvalue())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
