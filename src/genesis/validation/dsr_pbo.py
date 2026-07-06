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

from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation._returns import extract_trade_returns
from genesis.validation.errors import DsrPboConfigError
from genesis.validation.wfa import WfaResult

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
