"""Perturbación ±10%, stress de costos y definición de acantilado, Issue I (R36-R46).

Opera **exclusivamente** sobre `wfa_result.windows[-1]` (la ventana WFA más
reciente, candidata a incubación en vivo, decisión 5 §3): perturba eje por eje
(`n_minutes`, `atr_stop_frac`, `risk_pct`) el `winning_combo`, re-ejecutando el
backtest solo sobre el tramo OOS de esa ventana — costo acotado y constante, no
proporcional a `n_windows`. Solo produce números (`profit_factor`,
`relative_drop`, `is_cliff`); la comparación contra los umbrales de gate G8/G9
es responsabilidad de `verdict.py` (Issue J).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from genesis.backtest.costs import CostsConfig
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.backtest.ledger import Ledger
from genesis.backtest.metrics import profit_factor
from genesis.backtest.simulator import Simulator
from genesis.data.calendar import EconomicEvent
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.factories import CandidateFactory, ExitGeometryProvider, default_factory_for
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation._windowing import slice_frame_by_day_range
from genesis.validation.errors import SensitivityConfigError
from genesis.validation.wfa import WfaResult

CONFIG_VERSION: str = "genesis-validation-i/1"
"""Versión del esquema de configuración de este Change (Issue I, decisión 10 §3)."""

_AXES = ("n_minutes", "atr_stop_frac", "risk_pct")
"""Los tres ejes de perturbación normativos, en orden (R39)."""

_DIRECTIONS = (-1, 1)
"""Direcciones de perturbación: `-1` (a la baja) y `+1` (al alza), R39."""


@dataclass(frozen=True, slots=True)
class SensitivityConfig:
    """Configuración de la perturbación ±10%, stress de costos y acantilado (R36).

    `cliff_relative_drop_threshold` es el doble de estricto que la degradación
    general del gate G8 (`0.30`): nunca relajable por debajo de ese umbral
    (decisión 6 §3, ADR-I6) — este `__post_init__` no impone ese piso mínimo
    explícitamente (queda documentado como contrato de uso, no validación
    mecánica adicional al rango `(0.0, 1.0]`).
    """

    perturbation_fraction: float = 0.10
    cost_stress_multipliers: tuple[float, ...] = (1.5, 2.0)
    cliff_pf_floor: float = 1.0
    cliff_relative_drop_threshold: float = 0.5

    def __post_init__(self) -> None:
        if any(multiplier <= 1.0 for multiplier in self.cost_stress_multipliers):
            message = (
                f"SensitivityConfig.cost_stress_multipliers={self.cost_stress_multipliers!r} "
                "debe contener solo valores > 1.0 (R3b)."
            )
            raise SensitivityConfigError(message)
        if not (0.0 < self.cliff_relative_drop_threshold <= 1.0):
            message = (
                "SensitivityConfig.cliff_relative_drop_threshold="
                f"{self.cliff_relative_drop_threshold!r} debe estar en (0.0, 1.0] (R3c)."
            )
            raise SensitivityConfigError(message)
        if self.cliff_pf_floor <= 0.0:
            message = (
                f"SensitivityConfig.cliff_pf_floor={self.cliff_pf_floor!r} debe ser > 0.0 (R3c)."
            )
            raise SensitivityConfigError(message)


@dataclass(frozen=True, slots=True)
class PerturbationOutcome:
    """Resultado de perturbar un eje del `winning_combo` en una dirección (R40)."""

    axis: str
    direction: int
    perturbed_value: float
    profit_factor: float
    relative_drop: float
    is_cliff: bool


@dataclass(frozen=True, slots=True)
class CostStressOutcome:
    """Resultado de un backtest con `Simulator(..., stress=multiplier)` (R41)."""

    multiplier: float
    profit_factor: float


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    """Resultado congelado de la sensibilidad completa para `(candidate_id, symbol)` (R42).

    Ningún campo evalúa el umbral G8 (`< 30%`) ni G9 (`>= 1.15`) contra un
    booleano de pasa/no-pasa (R44): la comparación es responsabilidad de
    `verdict.py` (Issue J).
    """

    candidate_id: str
    symbol: str
    config_version: str
    baseline_profit_factor: float
    perturbations: Sequence[PerturbationOutcome]
    cost_stress: Sequence[CostStressOutcome]
    has_cliff: bool


def _relative_drop_and_cliff(
    baseline_pf: float, perturbed_pf: float, config: SensitivityConfig
) -> tuple[float, bool]:
    """`relative_drop` y `is_cliff` (decisión 6 §3, R40): `pf <= floor` o `drop >= threshold`."""
    relative_drop = 0.0 if baseline_pf == 0.0 else (baseline_pf - perturbed_pf) / baseline_pf
    is_cliff = (
        perturbed_pf <= config.cliff_pf_floor
        or relative_drop >= config.cliff_relative_drop_threshold
    )
    return relative_drop, is_cliff


def _replace_axis(
    combo: tuple[int, float, float], axis: str, value: float
) -> tuple[int, float, float]:
    """Sustituye el valor de `axis` en `combo`, dejando los otros dos fijos (R39)."""
    n_minutes, atr_stop_frac, risk_pct = combo
    if axis == "n_minutes":
        return (int(value), atr_stop_frac, risk_pct)
    if axis == "atr_stop_frac":
        return (n_minutes, float(value), risk_pct)
    return (n_minutes, atr_stop_frac, float(value))


def _resolve_exit_geometry(
    candidate_factory: CandidateFactory,
    exit_geometry: ExitGeometry | None,
    *,
    candidate_id: str,
) -> ExitGeometry:
    """Precedencia del genoma sobre la config (§1.4 del diseño), reimplementación local."""
    if isinstance(candidate_factory, ExitGeometryProvider):
        return candidate_factory.exit_geometry
    if exit_geometry is not None:
        return exit_geometry
    message = (
        f"Sin ExitGeometry para candidate_id={candidate_id!r}: la CandidateFactory no "
        "implementa ExitGeometryProvider y no se pasó un exit_geometry explícito (§1.4)."
    )
    raise BacktestConfigError(message)


def _run_combo(
    combo: tuple[int, float, float],
    *,
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    exit_geometry: ExitGeometry,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    tick_store: RawParquetStore | None,
    starting_balance: float,
    dataset_hash: str,
    stress: float,
    candidate_factory: CandidateFactory,
) -> Ledger:
    """Instancia un candidato/motor de simulación **nuevos** para `combo` (R38-R41).

    Reimplementación local (mismo criterio que `dsr_pbo._run_combo`, sin
    importar símbolos privados de `wfa.py`), con `stress` explícito reutilizando
    el parámetro que `Simulator.__init__` ya acepta (R41).
    """
    n_minutes, atr_stop_frac, risk_pct = combo
    candidate = candidate_factory(
        figure=figure,
        reference_balance=starting_balance,
        params={
            "n_minutes": n_minutes,
            "atr_stop_frac": atr_stop_frac,
            "risk_pct": risk_pct,
        },
    )
    simulator = Simulator(
        candidate,
        symbol=symbol,
        firm_profile=firm_profile,
        exit_geometry=exit_geometry,
        figure=figure,
        funnel_config=funnel_config,
        costs_config=costs_config,
        news_events=news_events,
        tick_store=tick_store,
        starting_balance=starting_balance,
        dataset_hash=dataset_hash,
        stress=stress,
    )
    return simulator.run(frame)


def run_sensitivity(
    wfa_result: WfaResult,
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    exit_geometry: ExitGeometry | None,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    dataset_store: RawParquetStore,
    tick_store: RawParquetStore | None,
    starting_balance: float,
    config: SensitivityConfig | None = None,
    candidate_factory: CandidateFactory | None = None,
) -> SensitivityResult:
    """Perturbación ±10% eje-por-eje + stress de costos sobre la última ventana WFA (R37-R42).

    `SensitivityConfigError` si `wfa_result.windows` está vacío (R3a). Opera
    **solo** sobre `wfa_result.windows[-1]` (R38): recupera su `winning_combo` y
    trocea el `frame` original al tramo OOS de esa ventana
    (`_windowing.slice_frame_by_day_range`). Para cada uno de los 3 ejes del
    combo, ejecuta 2 backtests perturbados (`valor × (1 ± perturbation_fraction)`,
    otros dos ejes fijos, R39); adicionalmente, un backtest por cada
    `cost_stress_multipliers` (por defecto `1.5`/`2.0`) sin perturbar (R41). En
    total 9 backtests: 1 baseline + 6 perturbaciones + 2 stress — volumen
    acotado y constante (decisión 7 §3), loop secuencial (R63).
    """
    resolved_config = config if config is not None else SensitivityConfig()
    resolved_candidate_factory = (
        candidate_factory
        if candidate_factory is not None
        else default_factory_for(wfa_result.candidate_id)
    )
    resolved_exit_geometry = _resolve_exit_geometry(
        resolved_candidate_factory, exit_geometry, candidate_id=wfa_result.candidate_id
    )

    if not wfa_result.windows:
        message = (
            f"candidate_id={wfa_result.candidate_id!r} symbol={symbol!r}: wfa_result.windows "
            "está vacío, no hay ventana ganadora que perturbar (R3a)."
        )
        raise SensitivityConfigError(message)

    last_window = wfa_result.windows[-1]
    winning_combo = last_window.winning_combo
    frame_oos = slice_frame_by_day_range(
        frame, symbol, firm_profile, last_window.oos_trading_day_range
    )
    dataset_hash_oos = dataset_store.chunk_hash(frame_oos)

    def _profit_factor_for(combo: tuple[int, float, float], *, stress: float = 1.0) -> float:
        ledger = _run_combo(
            combo,
            frame=frame_oos,
            symbol=symbol,
            firm_profile=firm_profile,
            exit_geometry=resolved_exit_geometry,
            figure=figure,
            funnel_config=funnel_config,
            costs_config=costs_config,
            news_events=news_events,
            tick_store=tick_store,
            starting_balance=starting_balance,
            dataset_hash=dataset_hash_oos,
            stress=stress,
            candidate_factory=resolved_candidate_factory,
        )
        return profit_factor(ledger)

    baseline_pf = _profit_factor_for(winning_combo)

    perturbations: list[PerturbationOutcome] = []
    axis_base_values = dict(zip(_AXES, winning_combo, strict=True))
    for axis in _AXES:
        base_value = axis_base_values[axis]
        for direction in _DIRECTIONS:
            perturbed_value = base_value * (1 + direction * resolved_config.perturbation_fraction)
            if axis == "n_minutes":
                perturbed_value = max(1, round(perturbed_value))
            combo = _replace_axis(winning_combo, axis, perturbed_value)
            perturbed_pf = _profit_factor_for(combo)
            relative_drop, is_cliff = _relative_drop_and_cliff(
                baseline_pf, perturbed_pf, resolved_config
            )
            perturbations.append(
                PerturbationOutcome(
                    axis=axis,
                    direction=direction,
                    perturbed_value=float(perturbed_value),
                    profit_factor=perturbed_pf,
                    relative_drop=relative_drop,
                    is_cliff=is_cliff,
                )
            )

    cost_stress = [
        CostStressOutcome(
            multiplier=multiplier,
            profit_factor=_profit_factor_for(winning_combo, stress=multiplier),
        )
        for multiplier in resolved_config.cost_stress_multipliers
    ]

    return SensitivityResult(
        candidate_id=wfa_result.candidate_id,
        symbol=symbol,
        config_version=CONFIG_VERSION,
        baseline_profit_factor=baseline_pf,
        perturbations=perturbations,
        cost_stress=cost_stress,
        has_cliff=any(perturbation.is_cliff for perturbation in perturbations),
    )
