"""Benchmark y perfilado del diagnóstico de señal desnuda (§2.2.1).

Evidencia **no-pytest** (no bloquea `mise run ci`, Rg-13), en la línea de
`bench_iter_ticks.py`: mide por separado las tres etapas del diagnóstico y
permite perfilar la más costosa con `cProfile`.

A diferencia de `bench_iter_ticks.py`, **no requiere datos de MT5**: genera un
frame M1 sintético contiguo del tamaño real de un símbolo (~78k barras, el orden
de magnitud que reporta `m1_edge.json` de la corrida D). Eso lo hace ejecutable
en cualquier entorno, incluido CI, y suficiente para localizar cuellos
algorítmicos —que dependen del número de barras y de niveles acumulados, no de
los valores concretos de precio—.

Limitación deliberada: no ejercita `estimate_roundtrip_cost` (capa 4), que lee
ticks reales. El coste de esa etapa queda fuera de esta medición.

Uso:
    uv run python scripts/bench_diagnose.py
    uv run python scripts/bench_diagnose.py --bars 20000
    uv run python scripts/bench_diagnose.py --profile-stage detect --top 15
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


def synthetic_m1_frame(n_bars: int, seed: int = 7) -> pd.DataFrame:
    """Frame M1 contiguo y reproducible: random walk con rango intrabar no degenerado."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 5, 0, 0)
    close = 5000.0 + rng.normal(0.0, 0.35, size=n_bars).cumsum()
    half_range = np.abs(rng.normal(0.0, 0.8, size=n_bars))
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=i) for i in range(n_bars)],
            "open": close - rng.normal(0.0, 0.2, size=n_bars),
            "high": close + half_range,
            "low": close - half_range,
            "close": close,
            "tick_volume": rng.integers(20, 400, size=n_bars),
        }
    )


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
    frame = synthetic_m1_frame(args.bars)

    measured, bars, events = _stage_times(frame, firm_profile, config, args.symbol, args.session)
    measured["horizons_minutes"] = list(config.diagnostics.horizons_minutes)
    measured["extrapolated_min"] = measured["total_s"] * args.symbols / 60

    if args.json:
        print(json.dumps(measured, indent=2))
    else:
        total = measured["total_s"]
        print(
            f"barras={measured['n_bars']:,}  eventos CT={measured['n_events']:,}  "
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
