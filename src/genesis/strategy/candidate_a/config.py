"""`CandidateAConfig` + `load_candidate_a_config` + `load_placeholder_symbol_figures`.

Importa solo stdlib + `genesis.data.symbols` (capa 1) + `genesis.strategy.errors` (misma
capa 2): este módulo no depende del paquete de capa 3 (backtest) ni de
`genesis.strategy.inspector`/`common` (aislamiento del candidato, spec §2.1/§2.5).
Réplica del patrón fail-fast de `load_candidate_b_config`
(`candidate_b/config.py:36-66`), leyendo el namespace `candidates.A.*` del **mismo**
recurso empaquetado `inspector_config.json` (R110).
"""

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_a.errors import CandidateAConfigError

_CONFIG_PACKAGE = "genesis.strategy"
_CONFIG_RESOURCE = "inspector_config.json"


@dataclass(frozen=True, slots=True)
class SmcEngineConfig:
    """Los 8 campos de estructura de `smc_engine` (spec §3.3/§3.4, defaults ADR-D3)."""

    fractal_n: int
    """Número de velas a cada lado exigidas para confirmar un fractal (R99)."""

    eq_tolerance_atr: float
    """Tolerancia (en múltiplos de ATR del TF) para agrupar swings en un EQH/EQL (R102)."""

    sweep_tolerance_atr: float
    """Tolerancia (en múltiplos de ATR M1) para el toque `ARMADO -> TOCADO` (R103)."""

    sweep_window_k: int
    """Ventana en velas M1 (incluida la del toque) para confirmar `BARRIDO` (R103)."""

    sweep_validity_m: int
    """Velas M1 tras `BARRIDO` antes de expirar y volver a `ARMADO` (R103)."""

    free_path_radius_sigma: float
    """Radio (en múltiplos de sigma del VWAP) de búsqueda de liquidez macro (R104)."""

    ct_zscore_min: float
    """Umbral `|zscore|` de zona CT reutilizado por `common.zones.classify_zone` (R112)."""

    atr_period: int
    """Período del ATR-Wilder incremental por `Timeframe` (R106)."""


@dataclass(frozen=True, slots=True)
class DiagnosticsConfig:
    """Parámetros del diagnóstico de señal desnuda §2.2.1 (spec §3.4/§3.5, R108)."""

    horizons_minutes: tuple[int, ...]
    """Horizontes de retorno forward evaluados (default `(5, 15, 30, 60)`)."""

    bootstrap_resamples: int
    """Número de trayectorias del bootstrap de bloques temporales (R114)."""

    bootstrap_block_size: int | None
    """Tamaño de bloque del bootstrap; `None` -> mismo criterio que `_default_block_size`."""

    bootstrap_seed: int
    """Semilla explícita de `numpy.random.default_rng` (determinismo, R114)."""

    stop_distance_atr_buffer_multiple: float
    """Multiplicador de ATR sumado a la distancia estructural del sweep (§3.5, R108)."""


@dataclass(frozen=True, slots=True)
class CandidateAConfig:
    """Configuración compuesta de estructura + diagnóstico del Candidato A (R110)."""

    smc: SmcEngineConfig
    diagnostics: DiagnosticsConfig


def _read_resource(path: Path | None) -> tuple[str, str]:
    """Retorna `(raw_text, source)` desde `path` o desde el recurso empaquetado."""
    if path is not None:
        return path.read_text(encoding="utf-8"), str(path)
    resource = resources.files(_CONFIG_PACKAGE).joinpath(_CONFIG_RESOURCE)
    return resource.read_text(encoding="utf-8"), f"{_CONFIG_PACKAGE}/{_CONFIG_RESOURCE}"


def load_candidate_a_config(path: Path | None = None) -> CandidateAConfig:
    """Carga `CandidateAConfig` desde `payload["candidates"]["A"]` (R110).

    `path=None` -> recurso empaquetado `genesis.strategy/inspector_config.json` (mismo
    recurso que `load_candidate_b_config`). Lanza `CandidateAConfigError` con contexto
    (campo faltante/inválido + fuente) si `candidates.A.smc`/`candidates.A.diagnostics`
    falta o está incompleto — nunca degradación silenciosa. Separada de
    `load_placeholder_symbol_figures` (R96: parámetros de señal vs. fichas de contrato).
    """
    raw_text, source = _read_resource(path)
    try:
        payload = json.loads(raw_text)
        section = payload["candidates"]["A"]
        smc_raw = section["smc"]
        diagnostics_raw = section["diagnostics"]

        smc = SmcEngineConfig(
            fractal_n=int(smc_raw["fractal_n"]),
            eq_tolerance_atr=float(smc_raw["eq_tolerance_atr"]),
            sweep_tolerance_atr=float(smc_raw["sweep_tolerance_atr"]),
            sweep_window_k=int(smc_raw["sweep_window_k"]),
            sweep_validity_m=int(smc_raw["sweep_validity_m"]),
            free_path_radius_sigma=float(smc_raw["free_path_radius_sigma"]),
            ct_zscore_min=float(smc_raw["ct_zscore_min"]),
            atr_period=int(smc_raw["atr_period"]),
        )
        raw_block_size = diagnostics_raw["bootstrap_block_size"]
        diagnostics = DiagnosticsConfig(
            horizons_minutes=tuple(int(h) for h in diagnostics_raw["horizons_minutes"]),
            bootstrap_resamples=int(diagnostics_raw["bootstrap_resamples"]),
            bootstrap_block_size=None if raw_block_size is None else int(raw_block_size),
            bootstrap_seed=int(diagnostics_raw["bootstrap_seed"]),
            stop_distance_atr_buffer_multiple=float(
                diagnostics_raw["stop_distance_atr_buffer_multiple"]
            ),
        )
        return CandidateAConfig(smc=smc, diagnostics=diagnostics)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Configuración candidates.A.* inválida/incompleta en '{source}': {exc}"
        raise CandidateAConfigError(message) from exc


def load_placeholder_symbol_figures(path: Path | None = None) -> dict[str, SymbolFigure]:
    """Carga las fichas placeholder **no confirmadas** de `candidates.A.diagnostics` (R96).

    Separada de `load_candidate_a_config` (separación de responsabilidad: parámetros de
    señal vs. fichas de contrato). Los valores retornados son placeholders plausibles de
    un broker MT5 estándar, **no confirmados** contra la cuenta demo real de The5ers
    (spec §3.2); cualquier decisión de negocio real sobre oro/majors exige esa
    confirmación previa (Issue B/F). `tick_size=1.0` en los 4 símbolos preserva
    `value_per_point == tick_value` (Change #55, D6): sigue sin confirmar contra el bróker.
    Lanza `CandidateAConfigError` si el bloque `symbol_figures_placeholder` falta o algún
    campo de `SymbolFigure` es inválido.
    """
    raw_text, source = _read_resource(path)
    try:
        payload = json.loads(raw_text)
        placeholders_raw = payload["candidates"]["A"]["diagnostics"]["symbol_figures_placeholder"]
        return {
            symbol: SymbolFigure(
                symbol=str(figure_raw["symbol"]),
                tick_value=float(figure_raw["tick_value"]),
                tick_size=float(figure_raw["tick_size"]),
                volume_step=float(figure_raw["volume_step"]),
                stops_level=int(figure_raw["stops_level"]),
                freeze_level=int(figure_raw["freeze_level"]),
                digits=int(figure_raw["digits"]),
                swap_long=float(figure_raw["swap_long"]),
                swap_short=float(figure_raw["swap_short"]),
                swap_rollover_day=int(figure_raw["swap_rollover_day"]),
            )
            for symbol, figure_raw in placeholders_raw.items()
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = (
            f"Bloque candidates.A.diagnostics.symbol_figures_placeholder "
            f"inválido/incompleto en '{source}': {exc}"
        )
        raise CandidateAConfigError(message) from exc
