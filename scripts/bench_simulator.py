"""Bench del simulador event-driven: baseline del Bloque 0 del Change #46 (R15-R20).

Mide `Simulator.run(frame)` sobre una ventana real del store Parquet, con desglose por
etapa y contadores de invocación, para que los bloques 2/3a/4/6 puedan demostrar su
mejora contra una referencia archivada en vez de argumentarla.

Dos magnitudes importan y se reportan por separado:

- **Tiempo**: repetido `--repeat` veces (default 27, el número de combinaciones de
  ejecución que `wfa.py::_run_single_window` corre por ventana, R17). Cada repetición
  instancia un `Simulator` nuevo, igual que `_run_execution_combo`.
- **Pico de RSS**: la magnitud que motiva el Bloque 3a. El caché de ticks por `Simulator`
  no evicta nada hoy, y en la corrida D se observaron 6-8 GB por proceso.

El desglose por etapa sale de una pasada bajo `cProfile` (`--profile`), que además da los
**contadores de llamadas** — la evidencia directa de R14 (`session_window` una vez por
`trading_day`, no por barra) y R43 (`store.has_chunk` una vez por día, no por barra).
El tiempo bajo profiler no es comparable con el tiempo limpio: se reportan aparte.

Uso:
    uv run python scripts/bench_simulator.py --from-store US500.cash --repeat 27
    uv run python scripts/bench_simulator.py --from-store US500.cash --days 20 --profile
"""

import argparse
import cProfile
import gc
import json
import pstats
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import FillRecord
from genesis.backtest.simulator import Simulator
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import RawParquetStore
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_a.config import load_placeholder_symbol_figures
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.inspector import load_inspector_funnel_config

_STORE_ROOT = Path("data/raw")
_DEFAULT_SYMBOL = "US500.cash"
_DEFAULT_REPEAT = 27
"""Combinaciones de ejecución por ventana WFA (spec §6.2): el multiplicador real."""

_DEFAULT_BALANCE = 100_000.0
_DEFAULT_N_MINUTES = 15
_DEFAULT_ATR_STOP_FRAC = 1.0
_DEFAULT_RISK_PCT = 0.375
"""Punto central del grid 3x3x3 del Candidato B (spec §6.2)."""

_STAGES = (
    ("iter_bars", "store.py"),
    ("session_window", "sessions.py"),
    ("iter_ticks", "ticks.py"),
    ("has_sufficient_tick_coverage", "ticks.py"),
    ("ticks_in_bar_window", "ticks.py"),
    ("has_chunk", "store.py"),
    ("news_windows", "calendar.py"),
    ("_process_bar", "simulator.py"),
)
"""Funciones cuyo tiempo y nº de llamadas se extraen del perfil (una por hallazgo del issue)."""


_BROKER_TO_CANONICAL = {"US100.cash": "NAS100"}
"""Excepción al mapeo por sufijo: el índice Nasdaq se exporta como `US100.cash`."""


def _canonical_symbol(store_symbol: str) -> str:
    """Traduce el símbolo del broker al canónico de `genesis.data.sessions.SESSIONS`.

    El store guarda el nombre tal como lo sirve el broker (`US500.cash`), pero la tabla
    de sesiones, las fichas de símbolo y el `Simulator` usan el canónico (`US500`). El
    store resuelve el canónico por enlace simbólico (`data/raw/US500 -> US500.cash`).
    """
    if store_symbol in _BROKER_TO_CANONICAL:
        return _BROKER_TO_CANONICAL[store_symbol]
    return store_symbol.removesuffix(".cash")


def store_m1_frame(symbol: str, days: int | None = None) -> pd.DataFrame:
    """Concatena las particiones M1 reales de `symbol`, opcionalmente recortadas a `days`.

    El recorte es por fecha del reloj del servidor (columna `timestamp`), no por
    `trading_day` del `FirmProfile`: para dimensionar un bench la diferencia es
    irrelevante y evita depender de helpers privados de `validation/`.
    """
    partitions = sorted((_STORE_ROOT / symbol / "m1").rglob("*.parquet"))
    if not partitions:
        raise SystemExit(
            f"No hay particiones M1 para '{symbol}' en {_STORE_ROOT}/{symbol}/m1/. "
            f"Restaurá el dataset con: gh release download dataset-ftmo-2026-08-01 "
            f"-R ramaDben/genesis"
        )
    frame = pd.concat([pd.read_parquet(p) for p in partitions], ignore_index=True)
    if days is not None:
        server_dates = frame["timestamp"].dt.date
        keep = sorted(server_dates.unique())[:days]
        frame = frame[server_dates.isin(keep)].reset_index(drop=True)
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


def _resolve_figure(symbol: str, figure_json: str | None) -> SymbolFigure:
    """Ficha de símbolo: la indicada, la archivada por la corrida D, o el placeholder.

    Las fichas de la corrida D se nombran sin el sufijo de contado (`US500.json` para
    `US500.cash`), así que se prueban ambas formas antes de caer al placeholder.
    """
    if figure_json is not None:
        payload = json.loads(Path(figure_json).read_text(encoding="utf-8"))
        return SymbolFigure(**payload)

    bare_symbol = symbol.removesuffix(".cash")
    for root in ("out/run_d/figures", "~/genesis-artifacts/out/run_d/figures"):
        for name in (symbol, bare_symbol):
            path = Path(root).expanduser() / f"{name}.json"
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return SymbolFigure(**payload)

    placeholders = load_placeholder_symbol_figures()
    if symbol in placeholders:
        return placeholders[symbol]
    raise SystemExit(
        f"Símbolo '{symbol}' sin ficha ni placeholder de SymbolFigure: pasá --figure-json "
        f"con la ficha real (la corrida D las dejó en out/run_d/figures/)."
    )


def _peak_rss_mb() -> float | None:
    """Pico de RSS del proceso en MB, o `None` fuera de POSIX (`resource` no existe)."""
    try:
        import resource
    except ImportError:
        return None
    # ru_maxrss viene en KB en Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _build_simulator(
    *,
    symbol: str,
    firm_profile: FirmProfile,
    figure: SymbolFigure,
    tick_store: RawParquetStore | None,
    balance: float,
    dataset_hash: str,
) -> Simulator:
    """Instancia `CandidateB` + `Simulator` en frío, igual que `wfa._run_execution_combo`."""
    candidate = CandidateB(
        figure=figure,
        reference_balance=balance,
        n_minutes=_DEFAULT_N_MINUTES,
        atr_stop_frac=_DEFAULT_ATR_STOP_FRAC,
        risk_pct=_DEFAULT_RISK_PCT,
    )
    return Simulator(
        candidate,
        symbol=symbol,
        firm_profile=firm_profile,
        exit_geometry=load_exit_geometry(),
        figure=figure,
        funnel_config=load_inspector_funnel_config(),
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=tick_store,
        starting_balance=balance,
        dataset_hash=dataset_hash,
    )


def _stage_breakdown(profiler: cProfile.Profile) -> dict[str, dict[str, float]]:
    """Extrae `(ncalls, tottime, cumtime)` de las funciones de `_STAGES` del perfil.

    Usa `get_stats_profile()` (API pública de `pstats`) en vez del atributo interno
    `Stats.stats`, que no está tipado. `ncalls` llega como texto y puede venir en la
    forma `"totales/primitivas"` cuando la función es recursiva: interesa el total.
    """
    profile = pstats.Stats(profiler).get_stats_profile()
    breakdown: dict[str, dict[str, float]] = {}
    for stage_name, stage_file in _STAGES:
        entry = profile.func_profiles.get(stage_name)
        if entry is None or not entry.file_name.endswith(stage_file):
            continue
        breakdown[stage_name] = {
            "ncalls": float(str(entry.ncalls).split("/")[0]),
            "tottime_s": round(entry.tottime, 4),
            "cumtime_s": round(entry.cumtime, 4),
        }
    return breakdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-store", default=_DEFAULT_SYMBOL, metavar="SIMBOLO")
    parser.add_argument(
        "--symbol",
        default=None,
        help="símbolo canónico para sesiones/ficha (default: derivado del símbolo del store)",
    )
    parser.add_argument("--days", type=int, default=None, help="recorta a los N primeros días")
    parser.add_argument("--repeat", type=int, default=_DEFAULT_REPEAT)
    parser.add_argument("--profile", default=None, help="ruta de la ficha de firma (ftmo.json)")
    parser.add_argument("--figure-json", default=None, help="ruta de la ficha del símbolo")
    parser.add_argument("--balance", type=float, default=_DEFAULT_BALANCE)
    parser.add_argument("--no-ticks", action="store_true", help="corre sin tick_store")
    parser.add_argument(
        "--cprofile", action="store_true", help="una pasada extra con cProfile para el desglose"
    )
    parser.add_argument("--windows", type=int, default=3, help="ventanas WFA para extrapolar")
    parser.add_argument("--symbols", type=int, default=8, help="símbolos para extrapolar")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None, help="archiva el reporte JSON en esta ruta")
    args = parser.parse_args(argv)

    store_symbol = args.from_store
    symbol = args.symbol or _canonical_symbol(store_symbol)
    firm_profile = _resolve_profile(args.profile)
    figure = _resolve_figure(symbol, args.figure_json)
    frame = store_m1_frame(store_symbol, args.days)
    tick_store = None if args.no_ticks else RawParquetStore(_STORE_ROOT)
    dataset_hash = RawParquetStore(_STORE_ROOT).chunk_hash(frame)

    n_days = int(frame["timestamp"].dt.date.nunique())

    durations: list[float] = []
    n_ledger_entries = 0
    n_exit_fills = 0
    for repetition in range(1, args.repeat + 1):
        simulator = _build_simulator(
            symbol=symbol,
            firm_profile=firm_profile,
            figure=figure,
            tick_store=tick_store,
            balance=args.balance,
            dataset_hash=dataset_hash,
        )
        gc.collect()
        started = time.perf_counter()
        ledger = simulator.run(frame)
        durations.append(time.perf_counter() - started)
        # Fuera de la zona cronometrada: si el candidato no opera, el bench estaría
        # midiendo el camino sin fills y conviene que el reporte lo diga.
        n_ledger_entries = len(ledger.entries)
        n_exit_fills = sum(
            1
            for entry in ledger.entries
            if isinstance(entry.payload, FillRecord) and entry.payload.is_exit
        )
        # Progreso a stderr: una corrida completa puede tardar minutos y `--json`
        # necesita stdout limpio.
        print(
            f"  [{repetition}/{args.repeat}] {durations[-1]:.1f}s"
            f"  RSS {_peak_rss_mb() or 0:.0f} MB",
            file=sys.stderr,
            flush=True,
        )

    total_s = sum(durations)
    measured: dict[str, Any] = {
        "symbol": symbol,
        "store_symbol": store_symbol,
        "n_bars": len(frame),
        "n_days": n_days,
        "repeat": args.repeat,
        "with_ticks": not args.no_ticks,
        "per_run_s": [round(d, 3) for d in durations],
        "run_min_s": round(min(durations), 3),
        "run_max_s": round(max(durations), 3),
        "run_mean_s": round(total_s / len(durations), 3),
        "total_s": round(total_s, 3),
        "peak_rss_mb": _peak_rss_mb(),
        "n_ledger_entries": n_ledger_entries,
        "n_exit_fills": n_exit_fills,
        "dataset_hash": dataset_hash,
    }
    # Extrapolación a la corrida completa: repeticiones x ventanas x símbolos (R18).
    measured["extrapolated_h"] = round(
        measured["run_mean_s"] * args.repeat * args.windows * args.symbols / 3600, 2
    )

    if args.cprofile:
        simulator = _build_simulator(
            symbol=symbol,
            firm_profile=firm_profile,
            figure=figure,
            tick_store=tick_store,
            balance=args.balance,
            dataset_hash=dataset_hash,
        )
        profiler = cProfile.Profile()
        profiler.enable()
        simulator.run(frame)
        profiler.disable()
        measured["stages_profiled"] = _stage_breakdown(profiler)

    if args.json:
        print(json.dumps(measured, indent=2, ensure_ascii=False))
    else:
        print(
            f"símbolo={symbol}  barras={measured['n_bars']:,}  días={n_days}  "
            f"ticks={'sí' if not args.no_ticks else 'no'}  repeticiones={args.repeat}\n"
        )
        print(f"  {'por corrida (media)':<34} {measured['run_mean_s']:8.2f}s")
        print(
            f"  {'por corrida (min/max)':<34} {measured['run_min_s']:8.2f}s / "
            f"{measured['run_max_s']:.2f}s"
        )
        print(f"  {'TOTAL ' + str(args.repeat) + ' corridas':<34} {measured['total_s']:8.2f}s")
        if measured["peak_rss_mb"] is not None:
            print(f"  {'pico de RSS':<34} {measured['peak_rss_mb']:8.1f} MB")
        print(
            f"\nExtrapolado a {args.repeat} combos x {args.windows} ventanas x "
            f"{args.symbols} símbolos: {measured['extrapolated_h']:.2f} h"
        )
        stages = measured.get("stages_profiled")
        if stages:
            print("\n--- desglose bajo cProfile (tiempos NO comparables con los de arriba) ---")
            print(f"  {'función':<32} {'llamadas':>12} {'tottime':>10} {'cumtime':>10}")
            for name, data in sorted(
                stages.items(), key=lambda kv: kv[1]["cumtime_s"], reverse=True
            ):
                print(
                    f"  {name:<32} {int(data['ncalls']):>12,} "
                    f"{data['tottime_s']:>9.2f}s {data['cumtime_s']:>9.2f}s"
                )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(measured, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nBaseline archivado en {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
