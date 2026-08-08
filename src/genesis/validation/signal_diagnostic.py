"""Orquestación del diagnóstico de señal desnuda §2.2.1 (capa 4, R116-R122, ADR-D1).

Combina el núcleo estadístico puro de `candidate_a.diagnostics` (capa 2) con el coste
round-trip real de ticks (`genesis.backtest.ticks`, capa 3) y aplica el criterio
mecánico de archivo/continuación (§2.2.1, kill-switch): si el edge condicional bruto
(límite inferior del intervalo bootstrap) no supera el coste estimado, `ARCHIVE`; si lo
supera, `CONTINUE`. Sin discrecionalidad humana en la decisión. Expone el informe dual
JSON+Markdown (patrón `genesis.validation.verdict`) y el CLI `genesis-validate diagnose`.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import pandas as pd

from genesis.backtest.ticks import has_sufficient_tick_coverage, iter_ticks, ticks_in_bar_window
from genesis.data.metadata import ArtifactMetadata, current_git_commit
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, firm_profile_hash, load_firm_profile
from genesis.data.store import AnnotatedBar, iter_bars
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_a.config import (
    CandidateAConfig,
    load_candidate_a_config,
    load_placeholder_symbol_figures,
)
from genesis.strategy.candidate_a.diagnostics import (
    ConditionalReturnEvent,
    RawEdgeSummary,
    detect_ct_events,
    summarize_raw_edge,
)
from genesis.validation.errors import SignalDiagnosticConfigError

CONFIG_VERSION: str = "genesis-validation-d/2"
"""Versión del esquema de configuración/metadata de este módulo (spec §3, R39 heredado)."""

_PLACEHOLDER_SYMBOLS: frozenset[str] = frozenset({"XAUUSD", "EURUSD", "GBPUSD", "USDJPY"})
"""Símbolos con `SymbolFigure` placeholder no confirmado (R95/R107)."""


class ArchiveOrContinue(StrEnum):
    """Veredicto mecánico del diagnóstico de señal desnuda (R118, sin discrecionalidad)."""

    ARCHIVE = "archive"
    CONTINUE = "continue"


@dataclass(frozen=True, slots=True)
class SignalDiagnosticReport:
    """Informe reproducible del diagnóstico de señal desnuda (R119, ADR-D5).

    Compone `ArtifactMetadata` (capa 1) en vez de heredarla o reimplementarla,
    reutilizando `sha256_of`/`current_git_commit` sin duplicar lógica de hash.
    """

    data_metadata: ArtifactMetadata
    candidate_id: str
    symbol: str
    session_label: str
    horizons_minutes: tuple[int, ...]
    bootstrap_seed: int
    bootstrap_resamples: int
    raw_edge: RawEdgeSummary
    roundtrip_cost: float
    verdict: ArchiveOrContinue
    excluded_events_no_tick_coverage: int
    symbol_figure_is_placeholder: bool


def _tick_lookup_bar(event: ConditionalReturnEvent) -> AnnotatedBar:
    """`AnnotatedBar` mínima con `timestamp_utc`/`trading_day` reales del evento.

    `has_sufficient_tick_coverage`/`ticks_in_bar_window` (capa 3) solo leen esos dos
    campos; el resto de campos OHLC/volumen/`in_session` son relleno inerte, ya que el
    evento no conserva la vela M1 completa (solo su `entry_price`). Los bordes de sesión
    son relleno igualmente —el evento no los conserva—: se fijan al propio instante del
    evento, que es el único valor coherente con `in_session=True` sin inventar una
    ventana. Esta barra no debe pasarse a `Simulator`, que sí interpreta esos bordes.
    """
    return AnnotatedBar(
        timestamp_utc=event.event_time,
        open=event.entry_price,
        high=event.entry_price,
        low=event.entry_price,
        close=event.entry_price,
        tick_volume=0,
        trading_day=event.trading_day,
        in_session=True,
        session_open_utc=event.event_time,
        session_close_utc=event.event_time,
    )


def estimate_roundtrip_cost(
    store: RawParquetStore,
    symbol: str,
    events: Sequence[ConditionalReturnEvent],
    profile: FirmProfile,
) -> tuple[float, int]:
    """Coste round-trip real (spread relativo) estimado sobre `events` (R76, R116/R117).

    Por cada evento, calcula el spread promedio `(ask - bid)` de los ticks reales en
    `(T-60s, T]` (mismo criterio de borde que el motor de fills, `ticks.py:93-100`),
    expresado como retorno relativo (`spread / entry_price`) para ser comparable con
    `HorizonEdge.bootstrap_low`. `profile` se reenvía a `iter_ticks`/
    `has_sufficient_tick_coverage` para reinterpretar el timestamp de cada tick como
    `profile.server_tz` (R76). Si `has_sufficient_tick_coverage` es `False`, el evento
    se **excluye** del promedio (nunca degradado a un spread promedio sustituto, R117,
    R78). Retorna `(coste_promedio_eventos_con_cobertura, n_excluidos)`; `0.0` si ningún
    evento tiene cobertura suficiente (visible vía `n_excluidos == len(events)`, R117).
    """
    ticks_by_day: dict = {}
    costs: list[float] = []
    excluded = 0

    for event in events:
        lookup_bar = _tick_lookup_bar(event)
        if event.trading_day not in ticks_by_day:
            ticks_by_day[event.trading_day] = list(
                iter_ticks(store, symbol, event.trading_day, profile)
            )
        day_ticks = ticks_by_day[event.trading_day]

        if not has_sufficient_tick_coverage(store, symbol, lookup_bar, day_ticks, profile):
            excluded += 1
            continue

        window_ticks = ticks_in_bar_window(lookup_bar, day_ticks)
        average_spread = sum(tick.ask - tick.bid for tick in window_ticks) / len(window_ticks)
        costs.append(average_spread / event.entry_price)

    if not costs:
        return 0.0, excluded
    return sum(costs) / len(costs), excluded


def decide_verdict(raw_edge: RawEdgeSummary, roundtrip_cost: float) -> ArchiveOrContinue:
    """Criterio mecánico de archivo (R118): compara el edge bruto contra el coste.

    El edge bruto de referencia es el límite inferior del intervalo bootstrap
    (`bootstrap_low`) del **primer** horizonte de `raw_edge.horizons` (el más corto de
    `horizons_minutes`, la medida más directa del round-trip inmediato tras el sweep).
    Si el edge bruto supera estrictamente el coste, `CONTINUE`; si no, `ARCHIVE`. Sin
    discrecionalidad humana en la decisión (criterio de éxito 4 del proposal).
    """
    if not raw_edge.horizons:
        return ArchiveOrContinue.ARCHIVE
    edge_bruto = raw_edge.horizons[0].bootstrap_low
    return ArchiveOrContinue.CONTINUE if edge_bruto > roundtrip_cost else ArchiveOrContinue.ARCHIVE


def run_signal_diagnostic(
    store: RawParquetStore,
    frame: pd.DataFrame,
    symbol: str,
    session_label: str,
    profile: FirmProfile,
    config: CandidateAConfig,
    figure: SymbolFigure,
    *,
    symbol_figure_is_placeholder: bool,
    git_commit: str | None = None,
) -> SignalDiagnosticReport:
    """Orquesta el pipeline completo: `iter_bars -> detect_ct_events -> summarize_raw_edge`
    (capa 2) `-> estimate_roundtrip_cost` (capa 3, ticks) `-> decide_verdict ->
    SignalDiagnosticReport` (R116-R119).

    `git_commit is None` -> `current_git_commit()` (patrón `write_verdict_artifacts`);
    un valor explícito permite reproducibilidad determinista en golden tests sin
    depender del commit vigente del repositorio.
    """
    bars = list(iter_bars(frame, symbol, profile))
    events = detect_ct_events(bars, config, symbol, session_label)
    raw_edge = summarize_raw_edge(bars, events, config)
    roundtrip_cost, excluded = estimate_roundtrip_cost(store, symbol, events, profile)
    verdict = decide_verdict(raw_edge, roundtrip_cost)

    if bars:
        time_range = (bars[0].timestamp_utc, bars[-1].timestamp_utc)
    else:
        now = datetime.now(UTC)
        time_range = (now, now)

    resolved_git_commit = git_commit if git_commit is not None else current_git_commit()
    data_metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash=firm_profile_hash(profile),
        time_range=time_range,
        git_commit=resolved_git_commit,
        symbol_figure=figure,
    )

    return SignalDiagnosticReport(
        data_metadata=data_metadata,
        candidate_id="A",
        symbol=symbol,
        session_label=session_label,
        horizons_minutes=config.diagnostics.horizons_minutes,
        bootstrap_seed=config.diagnostics.bootstrap_seed,
        bootstrap_resamples=config.diagnostics.bootstrap_resamples,
        raw_edge=raw_edge,
        roundtrip_cost=roundtrip_cost,
        verdict=verdict,
        excluded_events_no_tick_coverage=excluded,
        symbol_figure_is_placeholder=symbol_figure_is_placeholder,
    )


def _horizon_edge_payload(horizon) -> dict:
    return {
        "horizon_minutes": horizon.horizon_minutes,
        "conditional_mean": horizon.conditional_mean,
        "unconditional_mean": horizon.unconditional_mean,
        "bootstrap_low": horizon.bootstrap_low,
        "bootstrap_high": horizon.bootstrap_high,
        "n_events": horizon.n_events,
    }


def _report_payload(report: SignalDiagnosticReport) -> dict:
    """Payload serializable compartido por JSON y Markdown (única fuente, R120)."""
    return {
        "data_metadata": json.loads(report.data_metadata.to_json()),
        "candidate_id": report.candidate_id,
        "symbol": report.symbol,
        "session_label": report.session_label,
        "horizons_minutes": list(report.horizons_minutes),
        "bootstrap_seed": report.bootstrap_seed,
        "bootstrap_resamples": report.bootstrap_resamples,
        "raw_edge": {
            "symbol": report.raw_edge.symbol,
            "session_label": report.raw_edge.session_label,
            "horizons": [_horizon_edge_payload(h) for h in report.raw_edge.horizons],
            "vwap_touch_rate": report.raw_edge.vwap_touch_rate,
            "typical_stop_distance": report.raw_edge.typical_stop_distance,
            "n_ct_events": report.raw_edge.n_ct_events,
        },
        "roundtrip_cost": report.roundtrip_cost,
        "verdict": report.verdict.value,
        "excluded_events_no_tick_coverage": report.excluded_events_no_tick_coverage,
        "symbol_figure_is_placeholder": report.symbol_figure_is_placeholder,
    }


def signal_diagnostic_report_to_json(report: SignalDiagnosticReport) -> str:
    """Serializa `report` a JSON canónico determinista (R120): `sort_keys=True`."""
    return json.dumps(_report_payload(report), ensure_ascii=False, sort_keys=True)


def render_signal_diagnostic_markdown(report: SignalDiagnosticReport) -> str:
    """Markdown puro de `report`, sin I/O, del mismo payload que el JSON (R120)."""
    payload = _report_payload(report)
    lines = [
        f"# Diagnóstico de señal desnuda — Candidato {report.candidate_id} / {report.symbol}",
        "",
        f"- Sesión: `{report.session_label}`",
        f"- Veredicto: **{report.verdict.value.upper()}**",
        f"- Coste round-trip estimado: `{report.roundtrip_cost:.6f}`",
        f"- Eventos CT excluidos por falta de cobertura de ticks: "
        f"{report.excluded_events_no_tick_coverage}",
        f"- Ficha de símbolo placeholder (no confirmada): {report.symbol_figure_is_placeholder}",
        f"- Eventos CT totales: {report.raw_edge.n_ct_events}",
        f"- Tasa de toque de VWAP antes del stop típico: `{report.raw_edge.vwap_touch_rate:.4f}`",
        f"- Distancia de stop típica media: `{report.raw_edge.typical_stop_distance:.6f}`",
        "",
        "## Edge condicional bruto por horizonte",
        "",
        "| Horizonte (min) | Media condicional | Media incondicional | Bootstrap p5 "
        "| Bootstrap p95 | N eventos |",
        "|---|---|---|---|---|---|",
    ]
    for horizon in payload["raw_edge"]["horizons"]:
        lines.append(
            f"| {horizon['horizon_minutes']} | {horizon['conditional_mean']:.6f} | "
            f"{horizon['unconditional_mean']:.6f} | {horizon['bootstrap_low']:.6f} | "
            f"{horizon['bootstrap_high']:.6f} | {horizon['n_events']} |"
        )
    lines.append("")
    lines.append(f"- `dataset_hash`: `{report.data_metadata.dataset_hash}`")
    lines.append(f"- `git_commit`: `{report.data_metadata.git_commit}`")
    lines.append(
        f"- `bootstrap_seed`: `{report.bootstrap_seed}` (`{report.bootstrap_resamples}` resamples)"
    )
    return "\n".join(lines) + "\n"


def write_signal_diagnostic_artifacts(
    report: SignalDiagnosticReport, output_dir: Path
) -> tuple[Path, Path]:
    """Única I/O de escritura: `report.json` + `report.md` (patrón `write_verdict_artifacts`)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(signal_diagnostic_report_to_json(report), encoding="utf-8")
    markdown_path.write_text(render_signal_diagnostic_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _load_m1_csv(path: Path) -> pd.DataFrame:
    """Carga un CSV M1 (`timestamp,open,high,low,close,tick_volume` o `time,...`)."""
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns and "time" in frame.columns:
        frame = frame.rename(columns={"time": "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame


def _resolve_figure(
    symbol: str, figure_json: Path | None, *, allow_placeholder_figures: bool
) -> tuple[SymbolFigure, bool]:
    """Resuelve `(SymbolFigure, symbol_figure_is_placeholder)` para `symbol` (R107)."""
    if figure_json is not None:
        payload = json.loads(figure_json.read_text(encoding="utf-8"))
        return SymbolFigure(**payload), False

    if symbol in _PLACEHOLDER_SYMBOLS:
        if not allow_placeholder_figures:
            message = (
                f"Símbolo '{symbol}' no tiene ficha SymbolFigure confirmada; se requiere "
                "--allow-placeholder-figures explícito para usar el placeholder no "
                "confirmado (R107)."
            )
            raise SignalDiagnosticConfigError(message)
        placeholders = load_placeholder_symbol_figures()
        return placeholders[symbol], True

    message = (
        f"Símbolo '{symbol}' no tiene ficha SymbolFigure confirmada ni placeholder "
        "definido; provea --figure-json con la ficha real."
    )
    raise SignalDiagnosticConfigError(message)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genesis-validate", description="CLI de validación de genesis (capa 4)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Diagnóstico de señal desnuda del Candidato A (§2.2.1, kill-switch)."
    )
    diagnose_parser.add_argument("--candidate", required=True, choices=["A"], help="Candidato.")
    diagnose_parser.add_argument("--firm", required=True, help="Nombre de la ficha de firma.")
    diagnose_parser.add_argument("--symbol", required=True, help="Símbolo a diagnosticar.")
    diagnose_parser.add_argument(
        "--session-label", required=True, help="Etiqueta de sesión del diagnóstico."
    )
    diagnose_parser.add_argument(
        "--input-csv",
        required=True,
        help="CSV M1 de entrada (timestamp/time,open,high,low,close,tick_volume).",
    )
    diagnose_parser.add_argument(
        "--data-root", default="data/raw", help="Raíz del RawParquetStore (ticks para el coste)."
    )
    diagnose_parser.add_argument(
        "--out", default="out/signal_diagnostic", help="Directorio de salida del informe."
    )
    diagnose_parser.add_argument(
        "--profile", default=None, help="Ruta a una ficha de firma alternativa."
    )
    diagnose_parser.add_argument(
        "--figure-json", default=None, help="Ruta a un JSON con la SymbolFigure confirmada."
    )
    diagnose_parser.add_argument(
        "--allow-placeholder-figures",
        action="store_true",
        help="Permite usar fichas placeholder no confirmadas de oro/majors (R107).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint CLI `genesis-validate` con subcomando `diagnose` (R121)."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command != "diagnose":
        return 2  # inalcanzable: argparse exige un subcomando (subparsers required=True)

    try:
        profile_path = Path(args.profile) if args.profile else None
        profile = load_firm_profile(profile_path)
        if profile.name != args.firm:
            message = (
                f"--firm '{args.firm}' no coincide con la ficha de firma cargada "
                f"('{profile.name}'); provea --profile explícito si desea otra ficha."
            )
            raise SignalDiagnosticConfigError(message)

        config = load_candidate_a_config()
        figure_json = Path(args.figure_json) if args.figure_json else None
        figure, is_placeholder = _resolve_figure(
            args.symbol, figure_json, allow_placeholder_figures=args.allow_placeholder_figures
        )

        frame = _load_m1_csv(Path(args.input_csv))
        store = RawParquetStore(Path(args.data_root))

        report = run_signal_diagnostic(
            store,
            frame,
            args.symbol,
            args.session_label,
            profile,
            config,
            figure,
            symbol_figure_is_placeholder=is_placeholder,
        )
        json_path, markdown_path = write_signal_diagnostic_artifacts(report, Path(args.out))
        print(f"genesis-validate diagnose: informe escrito en {json_path} y {markdown_path}.")
        print(f"veredicto: {report.verdict.value}")
        return 0
    except SignalDiagnosticConfigError as exc:
        print(f"genesis-validate diagnose: {exc}", file=sys.stderr)
        return 1
