"""DSR normativo de gate (G4) y PBO vía CSCV (G5) del candidato aislado, Issue I.

Reutiliza `_dsr.deflated_sharpe_ratio` (H) tal cual para el DSR de gate, sin
duplicar la fórmula; el PBO (Bailey, Borwein, López de Prado & Zhu, 2015) es
código propio de este módulo, sin equivalente en `_dsr.py`. Calcula DSR/PBO
**por candidato aislado** (insumo de los gates G4/G5); nunca aplica ninguna
deflación adicional (esa responsabilidad, distinta y posterior, es exclusiva
de `verdict.py`, Issue J). `combinatorial_symmetric_cross_validation` (CSCV) es
una función **pura**, desacoplada de cualquier re-run de backtest: `math.comb`
(stdlib) cubre exactamente la combinatoria `C(S, S/2)`, sin `scipy.special.comb`.
"""

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from genesis.backtest.costs import CostsConfig
from genesis.backtest.ledger import Ledger
from genesis.backtest.risk_profile import RiskProfile
from genesis.backtest.simulator import Simulator
from genesis.data.calendar import EconomicEvent
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.factories import CandidateFactory, default_factory_for
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation._returns import extract_trade_returns
from genesis.validation._windowing import iter_is_oos_bounds, plan_trading_days, slice_frame_by_days
from genesis.validation.errors import DsrPboConfigError
from genesis.validation.wfa import WfaResult
from genesis.validation.window_config import GridConfig, WfaWindowConfig

CONFIG_VERSION: str = "genesis-validation-i/1"
"""Versión del esquema de configuración de este Change (Issue I, decisión 10 §3)."""

MIN_TRADES_IS: int = 10
"""Umbral mínimo de trades IS agregados por configuración de señal de una ventana
(R2b/R34): por debajo de este umbral esa configuración recibe DSR-IS `-inf` en
`SignalTrialMatrix.dsr_is_by_window`. Constante propia de este módulo — NO
reimportada de `wfa.py` (mismo valor que H por diseño, declarada localmente)."""

_MIN_CSCV_SPLITS = 4
"""Techo mínimo de `S`/`n_splits` de CSCV (decisión 4 §3, R2a/R28): con historias
WFA de pocas ventanas, `C(4, 2) = 6` combinaciones es la resolución mínima
aceptable."""

_N_TRIALS_SIGNAL_PER_WINDOW = 9
"""`n_trials` del DSR-IS agregado por ventana en `build_signal_trial_matrix` (R26):
mismo criterio mecánico que `wfa._N_TRIALS_SIGNAL`, redeclarado localmente."""

_CSCV_OMEGA_EPSILON = 1e-6
"""Recorte de `ω` a `[ε, 1-ε]` (R29d) para evitar división por cero en los
extremos del logit."""


def deflated_sharpe_ratio_gate(wfa_result: WfaResult) -> float:
    """DSR normativo del gate G4 sobre el `oos_ledger_cosido` de `wfa_result` (R21-R23).

    `n_trials` proviene **exclusivamente** de `wfa_result.n_trials_signal_total`
    (= `n_windows * 9`, señal, decisión 1 §3 del spec) — nunca un literal
    hardcodeado, de modo que revertir al conteo de ejecución
    (`n_trials_execution_total`, 27 por ventana) sea un cambio de una línea
    (Rg-1). NO aplica ninguna deflación adicional posterior: esa
    responsabilidad (T1) es exclusiva de `verdict.py` (Issue J).
    """
    returns = [trade.pnl_delta for trade in extract_trade_returns(wfa_result.oos_ledger_cosido)]
    return deflated_sharpe_ratio(returns, n_trials=wfa_result.n_trials_signal_total)


@dataclass(frozen=True, slots=True)
class SignalTrialMatrix:
    """Matriz de `N` trials (configuraciones de señal) x `T` períodos (ventanas WFA), R27.

    `dsr_is_by_window[k]` es el mapa configuración de señal -> DSR-IS agregado de
    la ventana `k` (`signal_configs` fija el universo y el orden canónico de
    configuraciones — el orden de inserción de las claves dentro de cada mapa de
    `dsr_is_by_window` es irrelevante, R48).
    """

    signal_configs: Sequence[tuple[int, float]]
    n_windows: int
    dsr_is_by_window: Sequence[Mapping[tuple[int, float], float]]


@dataclass(frozen=True, slots=True)
class CscvResult:
    """Resultado congelado de `combinatorial_symmetric_cross_validation` (R30)."""

    pbo: float
    n_splits: int
    n_combinations: int
    logit_by_combination: Sequence[float]


def _contiguous_blocks(n_items: int, n_parts: int) -> list[list[int]]:
    """`n_parts` bloques contiguos de índices `[0, n_items)`, de tamaño `±1` (R29).

    Mismo criterio de partición contigua que `purged_cv._contiguous_partition_bounds`
    (duplicado deliberado: algoritmo genérico de 5 líneas sobre dominios distintos
    — trades vs. ventanas —, mismo criterio de ADR-H5/ADR-I1 para no forzar un
    acoplamiento cruzado por una utilidad trivial).
    """
    base, remainder = divmod(n_items, n_parts)
    blocks: list[list[int]] = []
    start = 0
    for part_index in range(n_parts):
        size = base + (1 if part_index < remainder else 0)
        blocks.append(list(range(start, start + size)))
        start += size
    return blocks


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _relative_rank(target: tuple[int, float], means: Mapping[tuple[int, float], float]) -> float:
    """Rango relativo de `target` en `means`, ascendente, empates por rango promedio (R29c).

    `rango / (N + 1) ∈ (0, 1)`: un `target` con el peor valor (rango más bajo)
    produce un `ω` pequeño.
    """
    ordered = sorted(means.items(), key=lambda item: item[1])
    n = len(ordered)
    index = 0
    while index < n:
        tie_end = index
        while tie_end + 1 < n and ordered[tie_end + 1][1] == ordered[index][1]:
            tie_end += 1
        average_rank = (index + 1 + tie_end + 1) / 2.0
        for position in range(index, tie_end + 1):
            if ordered[position][0] == target:
                return average_rank / (n + 1)
        index = tie_end + 1
    message = (
        f"target={target!r} no encontrado en means={list(means)!r} (invariante interno de CSCV)."
    )
    raise AssertionError(message)


def _resolve_cscv_splits(n_windows: int, n_splits: int | None) -> int:
    """Resuelve `S`/`n_splits` (R28): default determinista o valor explícito validado."""
    if n_splits is None:
        resolved = n_windows if n_windows % 2 == 0 else n_windows - 1
        resolved = max(resolved, _MIN_CSCV_SPLITS)
    else:
        resolved = n_splits
    if resolved % 2 != 0 or resolved > n_windows:
        message = (
            f"n_splits={resolved!r} inválido para n_windows={n_windows!r}: debe ser un entero "
            "par y <= n_windows (R2c/R28)."
        )
        raise DsrPboConfigError(message)
    return resolved


def combinatorial_symmetric_cross_validation(
    trial_matrix: SignalTrialMatrix, n_splits: int | None = None
) -> CscvResult:
    """PBO vía CSCV (Bailey, Borwein, López de Prado & Zhu, 2015) sobre `trial_matrix` (R28-R31).

    Función **pura**, desacoplada de cualquier re-run de backtest (testable con
    matrices sintéticas pequeñas). Agrupa las `n_windows` ventanas en `S` bloques
    contiguos (`±1`); para cada una de las `math.comb(S, S // 2)` combinaciones de
    bloques: calcula el DSR-IS medio por configuración sobre el bloque IS-CSCV y
    su complemento OOS-CSCV (R29a), selecciona la configuración con mayor media
    IS-CSCV (R29b), calcula el rango relativo `ω` de esa configuración dentro del
    ranking OOS-CSCV (R29c) y el logit `λ = ln(ω / (1 - ω))` (R29d). `PBO` es la
    fracción de combinaciones con `λ <= 0` (R30). Un DSR-IS `-inf` (config bajo
    `MIN_TRADES_IS` en alguna ventana) propaga `-inf` a su media: nunca gana la
    selección IS-CSCV, comportamiento determinista y documentado.
    """
    n_windows = trial_matrix.n_windows
    resolved_splits = _resolve_cscv_splits(n_windows, n_splits)

    blocks = _contiguous_blocks(n_windows, resolved_splits)
    configs = trial_matrix.signal_configs
    logits: list[float] = []
    for combination in itertools.combinations(range(resolved_splits), resolved_splits // 2):
        is_windows = [window for block_index in combination for window in blocks[block_index]]
        oos_windows = [
            window
            for block_index in range(resolved_splits)
            if block_index not in combination
            for window in blocks[block_index]
        ]
        mean_is = {
            config: _mean([trial_matrix.dsr_is_by_window[window][config] for window in is_windows])
            for config in configs
        }
        mean_oos = {
            config: _mean([trial_matrix.dsr_is_by_window[window][config] for window in oos_windows])
            for config in configs
        }
        best_config = max(mean_is, key=lambda config: mean_is[config])
        omega = _relative_rank(best_config, mean_oos)
        omega = min(max(omega, _CSCV_OMEGA_EPSILON), 1.0 - _CSCV_OMEGA_EPSILON)
        logits.append(math.log(omega / (1.0 - omega)))

    n_combinations = math.comb(resolved_splits, resolved_splits // 2)
    pbo = sum(1 for logit in logits if logit <= 0.0) / n_combinations
    return CscvResult(
        pbo=pbo,
        n_splits=resolved_splits,
        n_combinations=n_combinations,
        logit_by_combination=logits,
    )


def _run_combo(
    combo: tuple[int, float, float],
    *,
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    tick_store: RawParquetStore | None,
    starting_balance: float,
    dataset_hash: str,
    candidate_factory: CandidateFactory,
) -> Ledger:
    """Instancia un candidato/motor de simulación **nuevos** para `combo` y corre `frame` (R26).

    Reimplementación local (no importa `wfa._run_execution_combo`, R25): mismo
    patrón de kwargs directos que H, sin depender de ningún cargador de
    configuración de perfil.
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
        risk_profile=risk_profile,
        figure=figure,
        funnel_config=funnel_config,
        costs_config=costs_config,
        news_events=news_events,
        tick_store=tick_store,
        starting_balance=starting_balance,
        dataset_hash=dataset_hash,
    )
    return simulator.run(frame)


def build_signal_trial_matrix(
    candidate_id: str,
    symbol: str,
    frame: pd.DataFrame,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    dataset_store: RawParquetStore,
    tick_store: RawParquetStore | None,
    starting_balance: float,
    window_config: WfaWindowConfig | None = None,
    grid_config: GridConfig | None = None,
    candidate_factory: CandidateFactory | None = None,
) -> SignalTrialMatrix:
    """Reconstruye, de forma independiente, el DSR-IS de las 9 configs x N ventanas (R24-R27).

    Reproduce la misma geometría IS/OOS que `wfa.py` (vía `_windowing`, sin
    importar símbolos privados de `wfa.py`, R25). Para cada ventana y cada
    configuración de señal (`grid_config.signal_configs()`), instancia
    candidato/motor de simulación **nuevos** (R26) sobre el tramo IS para las 3
    combinaciones de `risk_pct_levels`, agrega los trades IS extraídos y calcula
    el DSR-IS agregado (`n_trials=9`) o `-inf` si agrega menos de
    `MIN_TRADES_IS` (R34) — sin abortar la construcción completa a menos que
    **todas** las configuraciones de **todas** las ventanas caigan en ese caso
    (R2b). Único uso deliberado de trades **IS** en este Change (R57): reconstruye
    la métrica de selección IS del WFA, nunca sustituye al OOS del DSR/PF
    normativos de los gates. Loop puramente secuencial (R63), sin ninguna forma
    de paralelismo de hilos ni procesos.
    """
    resolved_window_config = window_config if window_config is not None else WfaWindowConfig()
    resolved_grid_config = grid_config if grid_config is not None else GridConfig()
    resolved_candidate_factory = (
        candidate_factory if candidate_factory is not None else default_factory_for(candidate_id)
    )

    days, row_span = plan_trading_days(frame, symbol, firm_profile)
    bounds = list(iter_is_oos_bounds(len(days), resolved_window_config))
    if len(bounds) < _MIN_CSCV_SPLITS:
        message = (
            f"candidate_id={candidate_id!r} symbol={symbol!r}: n_windows={len(bounds)!r} "
            f"insuficiente para CSCV, se requiere >= {_MIN_CSCV_SPLITS!r} (R2a)."
        )
        raise DsrPboConfigError(message)

    signal_configs = resolved_grid_config.signal_configs()
    dsr_is_by_window: list[dict[tuple[int, float], float]] = []
    for _window_index, is_start, is_end, _oos_end in bounds:
        frame_is = slice_frame_by_days(frame, row_span, days[is_start:is_end])
        dataset_hash_is = dataset_store.chunk_hash(frame_is)

        dsr_by_config: dict[tuple[int, float], float] = {}
        for n_minutes, atr_stop_frac in signal_configs:
            aggregated_returns: list[float] = []
            for risk_pct in resolved_grid_config.risk_pct_levels:
                ledger_is = _run_combo(
                    (n_minutes, atr_stop_frac, risk_pct),
                    frame=frame_is,
                    symbol=symbol,
                    firm_profile=firm_profile,
                    risk_profile=risk_profile,
                    figure=figure,
                    funnel_config=funnel_config,
                    costs_config=costs_config,
                    news_events=news_events,
                    tick_store=tick_store,
                    starting_balance=starting_balance,
                    dataset_hash=dataset_hash_is,
                    candidate_factory=resolved_candidate_factory,
                )
                aggregated_returns.extend(
                    trade.pnl_delta for trade in extract_trade_returns(ledger_is)
                )
            dsr_by_config[(n_minutes, atr_stop_frac)] = (
                float("-inf")
                if len(aggregated_returns) < MIN_TRADES_IS
                else deflated_sharpe_ratio(aggregated_returns, n_trials=_N_TRIALS_SIGNAL_PER_WINDOW)
            )
        dsr_is_by_window.append(dsr_by_config)

    if all(value == float("-inf") for window in dsr_is_by_window for value in window.values()):
        message = (
            f"candidate_id={candidate_id!r} symbol={symbol!r}: las {len(signal_configs)!r} "
            f"configuraciones de señal de las {len(bounds)!r} ventanas quedaron por debajo de "
            f"MIN_TRADES_IS={MIN_TRADES_IS!r} (R2b/R34)."
        )
        raise DsrPboConfigError(message)

    return SignalTrialMatrix(
        signal_configs=signal_configs,
        n_windows=len(bounds),
        dsr_is_by_window=dsr_is_by_window,
    )


@dataclass(frozen=True, slots=True)
class DsrPboResult:
    """Resultado congelado del DSR de gate + PBO vía CSCV para `(candidate_id, symbol)` (R32).

    Ningún campo evalúa el umbral G4 (`>= 0.95`) ni G5 (`< 25%`) contra un
    booleano de pasa/no-pasa (R33): solo produce los números; la comparación
    contra el umbral es responsabilidad de `verdict.py` (Issue J).
    """

    candidate_id: str
    symbol: str
    config_version: str
    dsr: float
    n_trials_signal_total: int
    pbo: float
    cscv: CscvResult


def run_dsr_pbo(
    wfa_result: WfaResult,
    trial_matrix: SignalTrialMatrix,
    n_splits: int | None = None,
) -> DsrPboResult:
    """Compone `deflated_sharpe_ratio_gate` + `combinatorial_symmetric_cross_validation` (R32-R33).

    `wfa_result` y `trial_matrix` son insumos independientes (el DSR de gate se
    calcula sobre el `oos_ledger_cosido` de `wfa_result`; el PBO, sobre
    `trial_matrix`) — no se exige que compartan el mismo `n_windows`. Si
    `wfa_result.n_windows < 4`, `DsrPboConfigError` (R2a, coherente con la guarda
    de `build_signal_trial_matrix`).
    """
    if wfa_result.n_windows < _MIN_CSCV_SPLITS:
        message = (
            f"candidate_id={wfa_result.candidate_id!r} symbol={wfa_result.symbol!r}: "
            f"n_windows={wfa_result.n_windows!r} insuficiente para CSCV, se requiere >= "
            f"{_MIN_CSCV_SPLITS!r} (R2a)."
        )
        raise DsrPboConfigError(message)

    dsr = deflated_sharpe_ratio_gate(wfa_result)
    cscv = combinatorial_symmetric_cross_validation(trial_matrix, n_splits)
    return DsrPboResult(
        candidate_id=wfa_result.candidate_id,
        symbol=wfa_result.symbol,
        config_version=CONFIG_VERSION,
        dsr=dsr,
        n_trials_signal_total=wfa_result.n_trials_signal_total,
        pbo=cscv.pbo,
        cscv=cscv,
    )
