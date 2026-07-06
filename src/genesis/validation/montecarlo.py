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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from genesis.backtest.ledger import FillRecord, Ledger, RunProvenance
from genesis.backtest.risk_profile import RiskProfile
from genesis.validation.errors import MonteCarloConfigError

_MIN_BLOCK_SIZE = 5
_MAX_BLOCK_SIZE = 60
_DEFAULT_PORTFOLIO_BLOCK_SIZE_DAYS = 5
"""Default de `monte_carlo_portfolio` cuando no se fija `block_size` (R44, decisión 4 §3)."""


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


@dataclass(frozen=True, slots=True)
class McPortfolioResult:
    """Resultado de Monte Carlo de portafolio: solo block bootstrap temporal (R45).

    El reshuffle puro no aplica a portafolio: destruiría la correlación cruzada
    entre símbolos del mismo día que este método existe para preservar.
    """

    provenance_by_symbol: Mapping[str, RunProvenance]
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


def _first_fill_record_or_none(ledger: Ledger) -> FillRecord | None:
    """Primer `FillRecord` del `ledger`, o `None` si no contiene ninguno."""
    for entry in ledger.entries:
        if isinstance(entry.payload, FillRecord):
            return entry.payload
    return None


def _first_fill_record(ledger: Ledger) -> FillRecord:
    """Primer `FillRecord` del `ledger`, base de `base_equity` (ADR-H7) y del `symbol` (R38)."""
    first_fill = _first_fill_record_or_none(ledger)
    if first_fill is None:
        message = "El ledger no contiene ningún FillRecord: no hay base de equity extraíble (R51)."
        raise MonteCarloConfigError(message)
    return first_fill


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


def _extract_exit_returns_by_day(ledger: Ledger) -> list[tuple[date, float]]:
    """Deltas de salida etiquetados por `trading_day` (proxy `timestamp_utc.date()`, ADR-H8).

    `montecarlo.py` no recibe `firm_profile` (R42): usar `timestamp_utc.date()` como
    proxy de `trading_day` es válido para el universo homogéneo del Candidato B
    (Rg-5, documentado como límite para universos con calendarios heterogéneos).
    """
    deltas_by_day: list[tuple[date, float]] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                trading_day = payload.timestamp_utc.date()
                deltas_by_day.append((trading_day, payload.equity_after - previous_equity))
            previous_equity = payload.equity_after
    return deltas_by_day


def _build_basket(
    oos_ledgers_by_symbol: Mapping[str, Ledger],
) -> tuple[list[date], dict[date, list[tuple[str, float]]]]:
    """Agrupa `(symbol, delta)` por `trading_day` en una canasta indivisible (R43).

    `basket_days` ordenados cronológicamente; `basket[day]` contiene todos los
    `(symbol, delta)` de ese día, de cualquier símbolo del universo — bloque atómico
    durante el resampleo (preserva la correlación cruzada del mismo día).
    """
    basket: dict[date, list[tuple[str, float]]] = {}
    for symbol, ledger in oos_ledgers_by_symbol.items():
        for trading_day, delta in _extract_exit_returns_by_day(ledger):
            basket.setdefault(trading_day, []).append((symbol, delta))
    basket_days = sorted(basket)
    return basket_days, basket


def _resample_day_sequence(
    basket_days: Sequence[date],
    block_size: int,
    rng: np.random.Generator,
    *,
    target_len: int,
) -> list[date]:
    """Moving-block bootstrap circular sobre `basket_days` (R43, R44): bloques de días.

    Cada bloque arrastra `block_size` días consecutivos de `basket_days` (envuelto
    circularmente); el `trading_day` resultante indexa la canasta completa de ese
    día, preservando qué símbolos co-ocurrieron (R46).
    """
    n = len(basket_days)
    n_blocks_needed = -(-target_len // block_size)  # ceil division
    starts = rng.integers(0, n, size=n_blocks_needed)
    resampled_days: list[date] = []
    for start in starts:
        for offset in range(block_size):
            resampled_days.append(basket_days[(start + offset) % n])
    return resampled_days[:target_len]


def _portfolio_block_bootstrap_paths(
    basket_days: Sequence[date],
    daily_totals: Mapping[date, float],
    n_paths: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """`n_paths` trayectorias de retorno diario de canasta, resampleadas por bloques (R43)."""
    n = len(basket_days)
    paths = np.empty((n_paths, n), dtype=float)
    for path_index in range(n_paths):
        resampled_days = _resample_day_sequence(basket_days, block_size, rng, target_len=n)
        paths[path_index] = np.array([daily_totals[day] for day in resampled_days], dtype=float)
    return paths


def monte_carlo_portfolio(
    oos_ledgers_by_symbol: Mapping[str, Ledger],
    risk_profile: RiskProfile,
    n_paths: int,
    seed: int,
    block_size: int | None = None,
) -> McPortfolioResult:
    """Monte Carlo de portafolio: canasta indivisible por `trading_day` (R42-R46).

    Combina los `Ledger` OOS de todos los símbolos por `trading_day` antes de
    resamplear en bloques temporales (`block_size` días consecutivos, default `5`,
    R44), preservando la correlación cruzada entre símbolos que ocurren el mismo día
    (R43). Solo block bootstrap (R45): el reshuffle puro destruiría esa correlación.
    `seed` es requerido (R48); RNG explícito `numpy.random.default_rng(seed)` (R47).
    """
    _validate_montecarlo_inputs(n_paths, block_size, context="monte_carlo_portfolio")

    basket_days, basket = _build_basket(oos_ledgers_by_symbol)
    if not basket_days:
        message = "Ningún ledger de oos_ledgers_by_symbol contiene trades OOS extraíbles (R51)."
        raise MonteCarloConfigError(message)

    daily_totals = {day: sum(delta for _symbol, delta in basket[day]) for day in basket_days}
    resolved_block_size = (
        block_size if block_size is not None else _DEFAULT_PORTFOLIO_BLOCK_SIZE_DAYS
    )

    provenance_by_symbol: dict[str, RunProvenance] = {}
    base_equity_portfolio = 0.0
    for symbol, ledger in oos_ledgers_by_symbol.items():
        provenance_by_symbol[symbol] = ledger.provenance
        first_fill = _first_fill_record_or_none(ledger)
        if first_fill is not None:
            base_equity_portfolio += first_fill.equity_after

    rng = np.random.default_rng(seed)
    block_bootstrap_result = _paths_to_result(
        _portfolio_block_bootstrap_paths(
            basket_days, daily_totals, n_paths, resolved_block_size, rng
        ),
        base_equity=base_equity_portfolio,
        max_loss_limit_pct=risk_profile.max_loss_limit_pct,
        seed=seed,
        n_paths=n_paths,
        block_size=resolved_block_size,
    )

    return McPortfolioResult(
        provenance_by_symbol=provenance_by_symbol,
        block_bootstrap=block_bootstrap_result,
    )
