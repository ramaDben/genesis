"""Motor de Monte Carlo por símbolo y de portafolio (R38-R52).

Capa 4 (`genesis.validation`). `monte_carlo_symbol` ejecuta siempre ambos métodos
de resampleo (reshuffle + block bootstrap, R38); `monte_carlo_portfolio` combina los
`Ledger` OOS de varios símbolos por `trading_day` en una canasta indivisible antes de
resamplear en bloques temporales, preservando la correlación cruzada del mismo día
(R43). Todo generador aleatorio es una instancia explícita de
`numpy.random.Generator` (`numpy.random.default_rng(seed)`), nunca el estado global
`numpy.random` (R47) — determinismo total: misma semilla + dataset + config ⇒
resultados bit-idénticos.

`n_paths` recomendado en el punto de invocación de más alto nivel: `1000` (R49),
suficiente resolución para los percentiles de los gates G6 (MaxDD p95) y G7
(P(breach) < 5%) que evaluará Issue J — este módulo no evalúa ningún gate (R50).
"""

from dataclasses import dataclass

import numpy as np

from genesis.backtest.ledger import FillRecord, Ledger, RunProvenance
from genesis.backtest.risk_profile import RiskProfile
from genesis.validation.errors import MonteCarloConfigError

_MIN_BLOCK_SIZE = 5
_MAX_BLOCK_SIZE = 60


@dataclass(frozen=True, slots=True)
class McPathsResult:
    """Resultado de un método de resampleo (reshuffle o block bootstrap) (R40).

    `block_size` es `None` para reshuffle (permutación completa, sin bloques) y un
    entero positivo para block bootstrap.
    """

    max_drawdown_per_path: np.ndarray
    breach_per_path: np.ndarray
    max_drawdown_p95: float
    breach_probability: float
    seed: int
    n_paths: int
    block_size: int | None


@dataclass(frozen=True, slots=True)
class McSymbolResult:
    """Resultado de Monte Carlo por símbolo: ambos métodos siempre (R38, R40)."""

    symbol: str
    provenance: RunProvenance
    reshuffle: McPathsResult
    block_bootstrap: McPathsResult


def _extract_exit_returns(ledger: Ledger) -> list[float]:
    """Deltas de `equity_after` de los `FillRecord` de salida del `ledger` (§2 del spec).

    Duplicado a propósito respecto a `wfa.py._extract_exit_returns` (ADR-H5): evita
    acoplar `wfa` <-> `montecarlo`. NO importa ningún símbolo privado de
    `genesis.backtest.metrics` (R61).
    """
    deltas: list[float] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                deltas.append(payload.equity_after - previous_equity)
            previous_equity = payload.equity_after
    return deltas


def _first_fill_record(ledger: Ledger) -> FillRecord:
    """Primer `FillRecord` del `ledger`, base de `base_equity` (ADR-H7) y del `symbol` (R38)."""
    for entry in ledger.entries:
        if isinstance(entry.payload, FillRecord):
            return entry.payload
    message = "El ledger no contiene ningún FillRecord: no hay base de equity extraíble (R51)."
    raise MonteCarloConfigError(message)


def _clip(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _default_block_size(n_trades: int) -> int:
    """`clip(round(n_trades ** (1/3)), 5, 60)` (R41, decisión 4 §3)."""
    return _clip(round(n_trades ** (1.0 / 3.0)), _MIN_BLOCK_SIZE, _MAX_BLOCK_SIZE)


def _path_max_drawdown(equity_path: np.ndarray) -> float:
    """Máxima caída pico-a-valle sobre `equity_path` (mismo criterio que `metrics.max_drawdown`).

    Reimplementado internamente sobre `numpy.ndarray` (ADR-H7): no reconstruye un
    `Ledger` sintético por trayectoria (costoso e innecesario).
    """
    if equity_path.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(equity_path)
    drawdown = running_peak - equity_path
    return float(drawdown.max())


def _block_resample(
    returns: np.ndarray,
    block_size: int,
    rng: np.random.Generator,
    *,
    target_len: int,
) -> np.ndarray:
    """Moving-block bootstrap circular: bloques contiguos de `block_size`, con reemplazo.

    Muestrea bloques hasta cubrir `target_len`, truncado al final (R38, ADR-H6). El
    índice de inicio de cada bloque se envuelve circularmente sobre `returns`
    (`wrap-around`) para admitir cualquier `block_size` respecto a `len(returns)`.
    """
    n = len(returns)
    n_blocks_needed = -(-target_len // block_size)  # ceil division
    starts = rng.integers(0, n, size=n_blocks_needed)
    blocks = [np.take(returns, np.arange(start, start + block_size) % n) for start in starts]
    return np.concatenate(blocks)[:target_len]


def _reshuffle_paths(returns: np.ndarray, n_paths: int, rng: np.random.Generator) -> np.ndarray:
    """`n_paths` permutaciones completas sin reemplazo de `returns` (R38)."""
    paths = np.empty((n_paths, len(returns)), dtype=float)
    for path_index in range(n_paths):
        paths[path_index] = rng.permutation(returns)
    return paths


def _block_bootstrap_paths(
    returns: np.ndarray,
    n_paths: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """`n_paths` trayectorias de block bootstrap circular de `returns` (R38)."""
    n = len(returns)
    paths = np.empty((n_paths, n), dtype=float)
    for path_index in range(n_paths):
        paths[path_index] = _block_resample(returns, block_size, rng, target_len=n)
    return paths


def _paths_to_result(
    paths: np.ndarray,
    *,
    base_equity: float,
    max_loss_limit_pct: float,
    seed: int,
    n_paths: int,
    block_size: int | None,
) -> McPathsResult:
    """Reduce `paths` (deltas por trayectoria) a MaxDD/breach por trayectoria (R39, R40)."""
    max_drawdown_per_path = np.empty(n_paths, dtype=float)
    breach_per_path = np.empty(n_paths, dtype=bool)
    threshold = (max_loss_limit_pct / 100.0) * base_equity
    for path_index in range(n_paths):
        equity_path = np.concatenate(([base_equity], base_equity + np.cumsum(paths[path_index])))
        maxdd = _path_max_drawdown(equity_path)
        max_drawdown_per_path[path_index] = maxdd
        breach_per_path[path_index] = maxdd > threshold

    max_drawdown_p95 = float(np.percentile(max_drawdown_per_path, 95))
    breach_probability = float(breach_per_path.mean())
    return McPathsResult(
        max_drawdown_per_path=max_drawdown_per_path,
        breach_per_path=breach_per_path,
        max_drawdown_p95=max_drawdown_p95,
        breach_probability=breach_probability,
        seed=seed,
        n_paths=n_paths,
        block_size=block_size,
    )


def _validate_montecarlo_inputs(n_paths: int, block_size: int | None, *, context: str) -> None:
    if n_paths <= 0:
        message = f"n_paths={n_paths!r} debe ser positivo ({context}, R51)."
        raise MonteCarloConfigError(message)
    if block_size is not None and block_size <= 0:
        message = (
            f"block_size={block_size!r} debe ser positivo si se fija explícitamente "
            f"({context}, R51)."
        )
        raise MonteCarloConfigError(message)


def monte_carlo_symbol(
    oos_ledger: Ledger,
    risk_profile: RiskProfile,
    n_paths: int,
    seed: int,
    block_size: int | None = None,
) -> McSymbolResult:
    """Monte Carlo por símbolo: reshuffle + block bootstrap, siempre ambos (R38-R41).

    `seed` es requerido (R48): construye un único `numpy.random.Generator`
    (`numpy.random.default_rng(seed)`), consumido en orden fijo — reshuffle primero,
    block bootstrap después (R47, ADR-H6). NO evalúa ningún gate G6/G7 (R50): solo
    produce `max_drawdown_p95`/`breach_probability` como insumo de Issue J.
    """
    _validate_montecarlo_inputs(n_paths, block_size, context="monte_carlo_symbol")

    returns_list = _extract_exit_returns(oos_ledger)
    if not returns_list:
        message = "oos_ledger no contiene ningún trade OOS extraíble (R51)."
        raise MonteCarloConfigError(message)
    returns = np.asarray(returns_list, dtype=float)

    resolved_block_size = (
        block_size if block_size is not None else _default_block_size(len(returns))
    )
    first_fill = _first_fill_record(oos_ledger)
    base_equity = first_fill.equity_after

    rng = np.random.default_rng(seed)
    reshuffle_result = _paths_to_result(
        _reshuffle_paths(returns, n_paths, rng),
        base_equity=base_equity,
        max_loss_limit_pct=risk_profile.max_loss_limit_pct,
        seed=seed,
        n_paths=n_paths,
        block_size=None,
    )
    block_bootstrap_result = _paths_to_result(
        _block_bootstrap_paths(returns, n_paths, resolved_block_size, rng),
        base_equity=base_equity,
        max_loss_limit_pct=risk_profile.max_loss_limit_pct,
        seed=seed,
        n_paths=n_paths,
        block_size=resolved_block_size,
    )

    return McSymbolResult(
        symbol=first_fill.symbol,
        provenance=oos_ledger.provenance,
        reshuffle=reshuffle_result,
        block_bootstrap=block_bootstrap_result,
    )
