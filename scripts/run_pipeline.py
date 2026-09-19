"""Runner end-to-end del pipeline de validación: del frame M1 crudo al veredicto.

Cierra el hueco que los `design.md` de los issues G, H, I y J dejaron fuera de alcance
de forma explícita y repetida ("mismo criterio que G con la CLI"): hasta ahora el único
flujo completo del pipeline vivía en `tests/validation/test_integration_pipeline_j.py`,
sobre fixtures sintéticas.

Herramienta de desarrollo (misma categoría que `bench_*.py`, evidencia no-pytest que no
bloquea `mise run ci`): compone APIs ya publicadas por las capas 3 y 4, sin añadir
ninguna ni tocar la superficie pública de `genesis`.

**El ledger de ensayos está cableado por defecto y hay que pedir `--no-ledger` para
apagarlo.** El default es deliberado: una corrida sin registrar quema un ensayo real
que el DSR de la corrida siguiente ignorará en silencio, sub-contando `n_trials` y
relajando el gate G4 sin que nadie lo note (el error asimétrico que motivó el #53).

Limitaciones honestas de este runner, no del pipeline:

- `news_events` va vacío: no carga el calendario económico. El filtro de noticias del
  Inspector queda inactivo, así que los resultados no descuentan ventanas de evento.
- Un solo símbolo por corrida. El torneo multi-símbolo/multi-candidato compone varios
  `CandidateValidationBundle`; esto ejecuta uno.
- `--server-offset-hours` desplaza el timestamp crudo **antes** de que `iter_bars` lo
  interprete con el `server_tz` de la ficha de firma. Solo tiene sentido junto a un
  `server_tz` que comparta las fechas de transición DST del reloj real del broker;
  con un `server_tz` de offset fijo (`Etc/GMT-N`) sobra y debe quedar en 0.

Uso:
    uv run python scripts/run_pipeline.py \\
        --store data/raw --firm-profile perfiles/moneta.json \\
        --symbol US500 --resolved-symbol SP500 \\
        --start 2023-09-01 --end 2026-08-29 \\
        --out-dir out/run_us500
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from genesis.backtest.costs import load_costs_config
from genesis.data.metadata import ArtifactMetadata, current_git_commit
from genesis.data.mt5_export import Granularity, RawParquetStore, plan_chunks
from genesis.data.profile import FirmProfile, firm_profile_hash, load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.genome import compile_genome
from genesis.strategy.inspector import InspectorFunnelConfig, load_inspector_funnel_config
from genesis.validation import (
    CandidateValidationBundle,
    load_prop_economics_profile,
    run_prop_sim,
    run_verdict,
    write_verdict_artifacts,
)
from genesis.validation.dsr_pbo import build_signal_trial_matrix, run_dsr_pbo
from genesis.validation.montecarlo import monte_carlo_portfolio, monte_carlo_symbol
from genesis.validation.prop_sim import PropSimConfig, prop_economics_profile_hash
from genesis.validation.purged_cv import PurgedCvConfig, run_purged_cv
from genesis.validation.sensitivity import run_sensitivity
from genesis.validation.trial_ledger import (
    LEDGER_RELATIVE_PATH,
    TrialIdentityContext,
    TrialLedger,
)
from genesis.validation.verdict import record_trial_completions
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import GridConfig, WfaWindowConfig

CONFIG_VERSION: str = "genesis-run-pipeline/1"
"""Versión del esquema de configuración de este runner, sellada en el manifest."""

_REPO_ROOT = Path(__file__).resolve().parent.parent

_timings: dict[str, float] = {}


@contextmanager
def _timed(label: str) -> Iterator[None]:
    start = time.perf_counter()
    yield
    _timings[label] = time.perf_counter() - start
    print(f"  [{label}] {_timings[label]:.2f}s", flush=True)


def _parse_utc_date(raw: str) -> dt.datetime:
    return dt.datetime.fromisoformat(raw).replace(tzinfo=dt.UTC)


def _load_frame(
    store: RawParquetStore,
    resolved_symbol: str,
    start: dt.datetime,
    end: dt.datetime,
    server_offset_hours: float,
) -> pd.DataFrame:
    """Concatena los chunks M1 del rango; fail-fast nombrando los que faltan."""
    windows = plan_chunks(start, end, Granularity.M1)
    missing = [w for w in windows if not store.has_chunk(resolved_symbol, Granularity.M1, w)]
    if missing:
        rangos = ", ".join(f"{w.start:%Y-%m}" for w in missing)
        message = (
            f"El store no tiene los chunks M1 de {resolved_symbol!r} para: {rangos}. "
            "Exportarlos con `mt5-export export` antes de correr el pipeline."
        )
        raise SystemExit(message)

    frames = [store.read_chunk(resolved_symbol, Granularity.M1, w) for w in windows]
    frame = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    if server_offset_hours:
        frame["timestamp"] = frame["timestamp"] - pd.Timedelta(hours=server_offset_hours)
    return frame


def _symbol_figure_from_store(store_root: Path, resolved_symbol: str) -> SymbolFigure:
    """Lee la ficha real del símbolo del sidecar del export; nunca la inventa."""
    sidecars = sorted((store_root / resolved_symbol / Granularity.M1.value).glob("*/*.meta.json"))
    for sidecar in sidecars:
        metadata = ArtifactMetadata.from_json(sidecar.read_text(encoding="utf-8"))
        if metadata.symbol_figure is not None:
            return metadata.symbol_figure
    message = (
        f"Ningún sidecar `.meta.json` de {resolved_symbol!r} en {store_root} trae "
        "`symbol_figure`. La ficha del símbolo solo la produce `mt5-export` contra una "
        "terminal real: sin ella no hay corrida reproducible."
    )
    raise SystemExit(message)


def _candidate_config(
    *,
    candidate_id: str,
    symbol: str,
    starting_balance: float,
    seed: int,
    window_config: WfaWindowConfig,
    grid_config: GridConfig,
    funnel_config: InspectorFunnelConfig,
    genome_config: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    """Identidad de *lo evaluado*, insumo de `compute_trial_id` (R4-R6).

    Incluye el embudo del Inspector además de la grilla: dos corridas con la misma
    grilla y distinto `lot_step_tolerance` son ensayos distintos, y colapsarlos en un
    `trial_id` sub-contaría el denominador del DSR.
    """
    cfg: dict[str, object] = {
        "candidate_id": candidate_id,
        "symbols": [symbol],
        "starting_balance": starting_balance,
        "seed": seed,
        "window_config": asdict(window_config),
        "grid_config": asdict(grid_config),
        "funnel_config": asdict(funnel_config),
        "runner_config_version": CONFIG_VERSION,
    }
    if genome_config is not None:
        cfg["genome"] = dict(genome_config)
    return cfg


def _resolve_starting_balance(cli_value: float, firm_profile: FirmProfile) -> float:
    """La ficha gobierna el balance inicial (D3b, Change #109); reconciliación fail-fast.

    Con `house_rule` declarado, `--starting-balance` debe coincidir exactamente con
    `house_rule.account_size` — si difiere, `SystemExit` con los dos números y el
    nombre de la ficha, nunca una elección silenciosa. Con `house_rule is None`
    (ficha de exchange) `--starting-balance` gobierna sin reconciliar: no hay
    contrato con el que comparar.
    """
    house_rule = firm_profile.house_rule
    if house_rule is None:
        return cli_value
    if cli_value != house_rule.account_size:
        message = (
            f"--starting-balance={cli_value!r} no coincide con "
            f"house_rule.account_size={house_rule.account_size!r} de la ficha "
            f"{firm_profile.name!r} (D3b). La ficha gobierna: pasar "
            f"--starting-balance {house_rule.account_size!r} o una ficha distinta."
        )
        raise SystemExit(message)
    return cli_value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--store", type=Path, required=True, help="Raíz del RawParquetStore.")
    parser.add_argument("--firm-profile", type=Path, required=True, help="Ficha de firma JSON.")
    parser.add_argument("--symbol", required=True, help="Símbolo canónico (tabla de sesiones).")
    parser.add_argument("--resolved-symbol", help="Nombre crudo del broker (default: --symbol).")
    parser.add_argument("--start", required=True, help="Inicio del rango, ISO (YYYY-MM-DD).")
    parser.add_argument("--end", required=True, help="Fin del rango, ISO (YYYY-MM-DD).")
    parser.add_argument("--out-dir", type=Path, required=True, help="Destino de los artefactos.")
    parser.add_argument("--candidate", default="B", help="`candidate_id` a evaluar.")
    parser.add_argument(
        "--genome",
        type=Path,
        help="Ruta al archivo YAML de genoma declarativo (ej. specs/b1.yaml).",
    )
    parser.add_argument("--starting-balance", type=float, default=100_000.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--n-paths", type=int, default=1000, help="Caminos de Monte Carlo.")
    parser.add_argument(
        "--is-days",
        type=int,
        help="Ancho IS en días de trading. Solo para diagnóstico: apartarse del default "
        "normativo produce un resultado que NO es comparable con una corrida institucional.",
    )
    parser.add_argument("--oos-days", type=int, help="Ancho OOS. Ver la nota de --is-days.")
    parser.add_argument("--step-days", type=int, help="Paso del rolling. Ver la nota de --is-days.")
    parser.add_argument(
        "--server-offset-hours",
        type=float,
        default=0.0,
        help="Horas restadas al timestamp crudo antes de interpretarlo con el `server_tz` "
        "de la ficha. Ver la limitación documentada en el encabezado del módulo.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=_REPO_ROOT / LEDGER_RELATIVE_PATH,
        help="Ruta del ledger de ensayos (#53).",
    )
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="No registrar el ensayo. Ver por qué el default es registrar, en el encabezado.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    resolved_symbol = args.resolved_symbol or args.symbol
    start, end = _parse_utc_date(args.start), _parse_utc_date(args.end)
    total_start = time.perf_counter()

    firm_profile = load_firm_profile(args.firm_profile)
    starting_balance = _resolve_starting_balance(args.starting_balance, firm_profile)
    costs_config = load_costs_config()
    funnel_config = load_inspector_funnel_config()
    prop_economics = load_prop_economics_profile()
    store = RawParquetStore(args.store)
    figure = _symbol_figure_from_store(args.store, resolved_symbol)
    grid_config = GridConfig()
    normative = WfaWindowConfig()
    window_config = WfaWindowConfig(
        is_window_trading_days=args.is_days or normative.is_window_trading_days,
        oos_window_trading_days=args.oos_days or normative.oos_window_trading_days,
        step_trading_days=args.step_days or normative.step_trading_days,
    )
    prop_sim_config = PropSimConfig(n_paths=args.n_paths, seed=42)

    candidate_id = args.candidate
    candidate_factory = None
    genome_config = None
    if args.genome is not None:
        genome_factory = compile_genome(args.genome)
        candidate_factory = genome_factory
        candidate_id = genome_factory.candidate_id
        genome_config = genome_factory.raw_config

    print(f"=== Pipeline {candidate_id}/{args.symbol} ({resolved_symbol}) ===")
    print(
        f"Rango: {start:%Y-%m-%d} .. {end:%Y-%m-%d} | ficha: {figure.symbol} "
        f"volume_step={figure.volume_step}"
    )
    print("Sin calendario económico: el filtro de noticias queda inactivo.")
    if window_config != normative:
        print(
            f"DIAGNÓSTICO: ventana {window_config} != normativa {normative} — "
            "el resultado no es comparable con una corrida institucional."
        )
    print()

    with _timed("load_frame"):
        frame = _load_frame(store, resolved_symbol, start, end, args.server_offset_hours)
    print(f"  filas M1: {len(frame)}")

    with _timed("run_wfa"):
        wfa_result = run_wfa(
            candidate_id,
            args.symbol,
            frame,
            firm_profile,
            None,
            figure,
            funnel_config,
            costs_config,
            [],
            store,
            store,
            starting_balance,
            window_config=window_config,
            grid_config=grid_config,
            candidate_factory=candidate_factory,
            seed=args.seed,
        )
    print(
        f"  n_windows={wfa_result.n_windows} wfe={wfa_result.wfe:.4f} "
        f"trades_oos={len(wfa_result.oos_ledger_cosido.entries)}"
    )
    # No se reconstruye ExitGeometry/HouseRule en el script (RD-1): las huellas
    # de procedencia se leen de la RunProvenance que `run_wfa` ya produjo.
    provenance = wfa_result.oos_ledger_cosido.provenance
    exit_geometry_hash_value = provenance.exit_geometry_hash
    house_rule_hash_value = provenance.house_rule_hash

    oos_ledgers = {args.symbol: wfa_result.oos_ledger_cosido}
    house_rule = firm_profile.house_rule
    if house_rule is None:
        message = (
            f"La ficha de firma {firm_profile.name!r} no declara 'house_rule': este runner "
            "solo evalúa prop firms (D2)."
        )
        raise SystemExit(message)

    with _timed("monte_carlo_symbol"):
        mc_symbol_result = monte_carlo_symbol(
            wfa_result.oos_ledger_cosido, house_rule, n_paths=args.n_paths, seed=11
        )

    with _timed("purged_cv"):
        purged_result = run_purged_cv(wfa_result.oos_ledger_cosido, PurgedCvConfig(n_folds=4))
    print(f"  purged_cv: {len(purged_result.folds)} folds, {purged_result.total_trades} trades")

    with _timed("trial_matrix+dsr_pbo"):
        trial_matrix = build_signal_trial_matrix(
            candidate_id,
            args.symbol,
            frame,
            firm_profile,
            None,
            figure,
            funnel_config,
            costs_config,
            [],
            store,
            store,
            starting_balance,
            # Obligatorio, no opcional: `build_signal_trial_matrix` reconstruye la misma
            # geometría IS/OOS que `run_wfa`. Omitirlo la deja en el default normativo y
            # la matriz sale con 0 ventanas contra un WFA que sí encontró 5 (R25).
            window_config=window_config,
            grid_config=grid_config,
            candidate_factory=candidate_factory,
        )
        dsr_pbo_result = run_dsr_pbo(wfa_result, trial_matrix)
    print(
        f"  DSR={dsr_pbo_result.dsr:.4f} PBO={dsr_pbo_result.pbo:.4f} "
        f"n_trials_signal_total={dsr_pbo_result.n_trials_signal_total}"
    )

    with _timed("sensitivity"):
        sensitivity_result = run_sensitivity(
            wfa_result,
            frame,
            args.symbol,
            firm_profile,
            None,
            figure,
            funnel_config,
            costs_config,
            [],
            store,
            store,
            starting_balance,
            candidate_factory=candidate_factory,
        )
    print(
        f"  baseline_pf={sensitivity_result.baseline_profit_factor:.4f} "
        f"has_cliff={sensitivity_result.has_cliff}"
    )

    with _timed("monte_carlo_portfolio"):
        mc_portfolio_result = monte_carlo_portfolio(
            oos_ledgers, house_rule, n_paths=args.n_paths, seed=13
        )
    print(f"  breach_probability={mc_portfolio_result.block_bootstrap.breach_probability:.4f}")

    with _timed("run_prop_sim"):
        prop_sim_result = run_prop_sim(
            oos_ledgers,
            starting_balance,
            firm_profile,
            prop_economics,
            prop_sim_config,
            candidate_id,
        )
    print(f"  prop_sim: p_pass={prop_sim_result.p_pass}")

    dataset_hash_by_symbol = {args.symbol: store.chunk_hash(frame)}
    firm_hash = firm_profile_hash(firm_profile)
    git_commit = current_git_commit()

    ledger: TrialLedger | None = None
    if not args.no_ledger:
        ledger = TrialLedger(
            args.ledger,
            TrialIdentityContext(
                dataset_hash_by_symbol=dataset_hash_by_symbol,
                firm_profile_hash=firm_hash,
                exit_geometry_hash=exit_geometry_hash_value,
                house_rule_hash=house_rule_hash_value,
                git_commit=git_commit,
            ),
        )
        print(f"\n  ledger: {args.ledger} ({ledger.read_summary().n_trials_total} ensayos previos)")
    else:
        print("\n  ledger: DESACTIVADO — este ensayo no contará en el DSR de corridas futuras.")

    candidates = {
        candidate_id: CandidateValidationBundle(
            candidate_id=candidate_id,
            wfa_results_by_symbol={args.symbol: wfa_result},
            dsr_pbo_results_by_symbol={args.symbol: dsr_pbo_result},
            sensitivity_results_by_symbol={args.symbol: sensitivity_result},
            mc_symbol_results_by_symbol={args.symbol: mc_symbol_result},
            mc_portfolio_result=mc_portfolio_result,
            prop_sim_result=prop_sim_result,
            candidate_config=_candidate_config(
                candidate_id=candidate_id,
                symbol=args.symbol,
                starting_balance=starting_balance,
                seed=args.seed,
                window_config=window_config,
                grid_config=grid_config,
                funnel_config=funnel_config,
                genome_config=genome_config,
            ),
        )
    }

    with _timed("run_verdict"):
        verdict_result = run_verdict(
            candidates,
            starting_balance,
            firm_profile,
            prop_economics,
            prop_sim_config,
            ledger=ledger,
        )
    print(f"  VEREDICTO: {verdict_result.verdict}")

    manifest_path, tearsheet_path = write_verdict_artifacts(
        verdict_result,
        args.out_dir,
        config_version=CONFIG_VERSION,
        dataset_hash_by_symbol=dataset_hash_by_symbol,
        firm_profile_hash=firm_hash,
        exit_geometry_hash=exit_geometry_hash_value,
        house_rule_hash=house_rule_hash_value,
        prop_economics_profile_hash_value=prop_economics_profile_hash(prop_economics),
        seeds={candidate_id: {"mc_seed": 13, "prop_sim_seed": prop_sim_config.seed}},
        git_commit=git_commit,
        purged_cv_results_by_candidate={candidate_id: {args.symbol: purged_result}},
    )

    if ledger is not None:
        trial_ids = record_trial_completions(ledger, candidates)
        summary = ledger.read_summary()
        print(
            f"  ledger: +{len(trial_ids)} registrado(s), "
            f"{summary.n_trials_total} ensayos acumulados"
        )

    print(f"\nArtefactos: {manifest_path}, {tearsheet_path}")
    print(f"\n=== TIEMPO TOTAL: {time.perf_counter() - total_start:.2f}s ===")
    for label, seconds in sorted(_timings.items(), key=lambda kv: -kv[1]):
        print(f"  {label}: {seconds:.2f}s")


if __name__ == "__main__":
    main()
