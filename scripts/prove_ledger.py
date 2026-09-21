"""Casilla 0.2 del roadmap: demostrar que el ledger de ensayos registra, de punta a punta.

`ledger/trials.jsonl` tiene **cero líneas** después de tres backtests reales corridos en
agosto: los runners ad-hoc de esa sesión nunca llamaron a `record_trial_completions`. El
cableado existe y está activo por defecto (`scripts/run_pipeline.py`), pero nunca se
demostró end-to-end. La política A2 dice que lo único que separa al arquitecto de una casa
de apuestas es la contabilidad honesta de ensayos: un arquitecto sobre un contador que
nunca contó es exactamente lo que A2 prohíbe.

Este script genera un dataset **sintético y determinista**, lo persiste en un
`RawParquetStore` temporal, corre `scripts/run_pipeline.py` dos veces sobre él contra un
**ledger temporal**, y verifica tres cosas:

1. La primera corrida deja exactamente un `TrialRecord` legible por `read_trial_summary`.
2. La segunda corrida idéntica **no** agrega fila (idempotencia por `trial_id`, R8).
3. El `dataset_hash` sintético queda impreso, de modo que el registro sea distinguible de
   cualquier ensayo sobre datos reales.

**Por qué un ledger temporal y no `ledger/trials.jsonl`.** `verdict.py` suma
`ledger_extra_trials` sin filtrar por símbolo, bróker ni clase de activo, así que un
registro sintético inflaría para siempre el `n_trials` del DSR de las corridas reales
futuras — endureciendo G4 con un ensayo que nunca existió. Escribir la demostración en el
ledger versionado sería, en sí mismo, el defecto que el punto 4 del #114 describe. Queda
como requisito para D1 del RFC #57: el ledger tiene que particionar antes de que una
corrida sintética pueda convivir con las reales.

Herramienta de desarrollo, misma categoría que `bench_*.py` y `run_pipeline.py`: compone
APIs ya publicadas, no añade ninguna.

Uso:
    uv run python scripts/prove_ledger.py
    uv run python scripts/prove_ledger.py --trading-days 240 --keep
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from genesis.data.metadata import ArtifactMetadata, current_git_commit
from genesis.data.mt5_export import Granularity, RawParquetStore, plan_chunks
from genesis.data.profile import firm_profile_hash, load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.validation.trial_ledger import read_trial_summary

_REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIG_VERSION: str = "genesis-prove-ledger/1"

SYMBOL = "US500"
"""Símbolo canónico: tiene que existir en la tabla de sesiones para que el embudo corra.

El dato es sintético; el nombre sólo selecciona la ventana de sesión (09:30-16:00 ET).
"""

_SESSION_START_UTC = dt.time(13, 0)
_SESSION_END_UTC = dt.time(21, 30)
"""Ventana UTC generada, con margen a ambos lados de la sesión de contado para cubrir DST."""

_SYNTHETIC_FIGURE = SymbolFigure(
    symbol=SYMBOL,
    tick_value=0.1,
    tick_size=0.1,
    volume_step=0.01,
    stops_level=0,
    freeze_level=0,
    digits=1,
    swap_long=0.0,
    swap_short=0.0,
    swap_rollover_day=3,
)
"""Ficha sintética: `value_per_point = tick_value / tick_size = 1.0`, deliberadamente redonda."""


def _trading_days(start: dt.date, count: int) -> list[dt.date]:
    """`count` días hábiles consecutivos desde `start` (sin calendario de feriados)."""
    days: list[dt.date] = []
    cursor = start
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += dt.timedelta(days=1)
    return days


def _synthetic_m1_frame(days: list[dt.date], seed: int) -> pd.DataFrame:
    """Barras M1 deterministas con estructura intradía suficiente para que el ORB dispare.

    Camino aleatorio con semilla fija más una expansión de rango en los primeros 30
    minutos de cada día: no pretende parecerse a un mercado, sólo producir rupturas del
    rango de apertura en ambas direcciones para que el WFA tenga operaciones que contar.
    """
    rng = np.random.default_rng(seed)
    minutes_per_day = int(
        (
            dt.datetime.combine(dt.date(2000, 1, 1), _SESSION_END_UTC)
            - dt.datetime.combine(dt.date(2000, 1, 1), _SESSION_START_UTC)
        ).total_seconds()
        // 60
    )

    timestamps: list[pd.Timestamp] = []
    closes: list[float] = []
    volumes: list[int] = []

    price = 5000.0
    for day in days:
        base = pd.Timestamp(dt.datetime.combine(day, _SESSION_START_UTC), tz="UTC")
        drift = rng.normal(0.0, 0.15)
        for minute in range(minutes_per_day):
            # Volatilidad mayor en la primera media hora: da rango de apertura y ruptura.
            sigma = 1.2 if minute < 30 else 0.55
            price += rng.normal(drift * 0.02, sigma)
            timestamps.append(base + pd.Timedelta(minutes=minute))
            closes.append(price)
            volumes.append(int(rng.integers(400, 1200) * (2 if minute < 30 else 1)))

    close = np.asarray(closes, dtype=float)
    open_ = np.concatenate(([close[0]], close[:-1]))
    spread = np.abs(rng.normal(0.0, 0.4, size=close.size)) + 0.1
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread

    return pd.DataFrame(
        {
            "timestamp": pd.DatetimeIndex(timestamps),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": np.asarray(volumes, dtype="int64"),
        }
    )


def _build_store(
    store_root: Path, frame: pd.DataFrame, firm_profile_path: Path, git_commit: str
) -> list[str]:
    """Persiste `frame` como chunks M1 mensuales con sus sidecars; devuelve los hashes."""
    store = RawParquetStore(store_root)
    profile_hash = firm_profile_hash(load_firm_profile(firm_profile_path))

    start = frame["timestamp"].iloc[0].to_pydatetime()
    end = frame["timestamp"].iloc[-1].to_pydatetime()
    hashes: list[str] = []
    for window in plan_chunks(start, end, Granularity.M1):
        mask = (frame["timestamp"] >= window.start) & (frame["timestamp"] < window.end)
        chunk = frame.loc[mask].reset_index(drop=True)
        if chunk.empty:
            message = (
                f"El chunk {window.start:%Y-%m} quedó vacío: el rango generado no cubre "
                "todos los meses que `plan_chunks` enumera, y `_load_frame` va a fallar."
            )
            raise SystemExit(message)
        chunk_hash = store.chunk_hash(chunk)
        hashes.append(chunk_hash)
        store.write_chunk(
            chunk,
            SYMBOL,
            Granularity.M1,
            window,
            ArtifactMetadata(
                config_version=CONFIG_VERSION,
                dataset_hash=chunk_hash,
                firm_profile_hash=profile_hash,
                time_range=(window.start, window.end),
                git_commit=git_commit,
                symbol_figure=_SYNTHETIC_FIGURE,
            ),
        )
    return hashes


def _run_pipeline(
    *,
    store_root: Path,
    firm_profile: Path,
    ledger_path: Path,
    out_dir: Path,
    start: dt.date,
    end: dt.date,
    is_days: int,
    oos_days: int,
    step_days: int,
    n_paths: int,
    starting_balance: float,
    genome: Path,
    label: str,
) -> None:
    """Invoca `scripts/run_pipeline.py` como subproceso y falla ruidosamente si no termina bien."""
    command = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "run_pipeline.py"),
        "--store",
        str(store_root),
        "--firm-profile",
        str(firm_profile),
        "--symbol",
        SYMBOL,
        "--genome",
        str(genome),
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--out-dir",
        str(out_dir),
        "--ledger",
        str(ledger_path),
        "--is-days",
        str(is_days),
        "--oos-days",
        str(oos_days),
        "--step-days",
        str(step_days),
        "--n-paths",
        str(n_paths),
        "--starting-balance",
        str(starting_balance),
    ]
    print(f"\n{'=' * 78}\n[{label}] {' '.join(command[1:])}\n{'=' * 78}", flush=True)
    completed = subprocess.run(command, cwd=_REPO_ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"[{label}] run_pipeline.py terminó con código {completed.returncode}.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--trading-days", type=int, default=180, help="Días hábiles a generar.")
    parser.add_argument("--seed", type=int, default=20260920, help="Semilla del generador.")
    parser.add_argument("--is-days", type=int, default=60)
    parser.add_argument("--oos-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--n-paths", type=int, default=50, help="Caminos de Monte Carlo.")
    parser.add_argument(
        "--genome",
        type=Path,
        default=_REPO_ROOT / "candidates" / "specs" / "candidate_b1_orb.yaml",
        help="Genoma a compilar. Obligatorio en la práctica: tras el #109 la factory por "
        "letra no implementa `ExitGeometryProvider` y `run_pipeline.py --candidate B` "
        "aborta con `BacktestConfigError`.",
    )
    parser.add_argument(
        "--firm-profile",
        type=Path,
        default=_REPO_ROOT / "src" / "genesis" / "data" / "profiles" / "mffu_rapid_eod_50k.json",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Directorio de trabajo (default: uno temporal que se borra al terminar).",
    )
    parser.add_argument("--keep", action="store_true", help="No borrar el directorio de trabajo.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    work_dir = args.work_dir or Path(tempfile.mkdtemp(prefix="genesis-prove-ledger-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    store_root = work_dir / "store"
    ledger_path = work_dir / "ledger" / "trials.jsonl"

    firm_profile = load_firm_profile(args.firm_profile)
    house_rule = firm_profile.house_rule
    if house_rule is None:
        raise SystemExit(f"La ficha {args.firm_profile} no declara 'house_rule'.")
    starting_balance = house_rule.account_size

    try:
        days = _trading_days(dt.date(2021, 1, 4), args.trading_days)
        print(f"Generando {len(days)} días hábiles sintéticos: {days[0]} .. {days[-1]}", flush=True)
        frame = _synthetic_m1_frame(days, args.seed)
        print(f"  barras M1: {len(frame)}", flush=True)

        git_commit = current_git_commit()
        hashes = _build_store(store_root, frame, args.firm_profile, git_commit)
        print(f"  chunks mensuales: {len(hashes)}", flush=True)

        summary_before = read_trial_summary(ledger_path)
        print(f"  ledger temporal antes: {summary_before.n_trials_total} ensayos", flush=True)

        common = {
            "store_root": store_root,
            "firm_profile": args.firm_profile,
            "ledger_path": ledger_path,
            "start": days[0],
            "end": days[-1] + dt.timedelta(days=1),
            "is_days": args.is_days,
            "oos_days": args.oos_days,
            "step_days": args.step_days,
            "n_paths": args.n_paths,
            "starting_balance": starting_balance,
            "genome": args.genome,
        }
        _run_pipeline(out_dir=work_dir / "out_1", label="corrida 1", **common)
        summary_1 = read_trial_summary(ledger_path)
        _run_pipeline(out_dir=work_dir / "out_2", label="corrida 2 (idéntica)", **common)
        summary_2 = read_trial_summary(ledger_path)

        print(f"\n{'=' * 78}\nVERIFICACIÓN\n{'=' * 78}")
        print(f"  ensayos tras corrida 1 : {summary_1.n_trials_total} (filas {summary_1.n_rows})")
        print(f"  ensayos tras corrida 2 : {summary_2.n_trials_total} (filas {summary_2.n_rows})")
        print(f"  duplicados detectados  : {summary_2.n_duplicate_trial_ids}")
        for trial_id in sorted(summary_2.trial_ids):
            print(f"  trial_id               : {trial_id}")
        print(f"  dataset_hash (chunk 1) : {hashes[0]}")
        print(f"  ledger                 : {ledger_path}")

        failures: list[str] = []
        if summary_1.n_trials_total != 1:
            failures.append(
                f"la corrida 1 dejó {summary_1.n_trials_total} ensayos, se esperaba exactamente 1"
            )
        if summary_2.n_trials_total != summary_1.n_trials_total:
            failures.append(
                f"la corrida 2 cambió el conteo de {summary_1.n_trials_total} a "
                f"{summary_2.n_trials_total}: la idempotencia por trial_id (R8) no se cumple"
            )
        if summary_2.n_rows != summary_1.n_rows:
            failures.append(
                f"la corrida 2 agregó filas ({summary_1.n_rows} -> {summary_2.n_rows})"
            )

        if failures:
            print("\nRESULTADO: FALLA")
            for failure in failures:
                print(f"  - {failure}")
            return 1

        print("\nRESULTADO: el ledger registra y es idempotente.")
        return 0
    finally:
        if args.keep or args.work_dir is not None:
            print(f"\nDirectorio de trabajo conservado: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
