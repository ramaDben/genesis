"""Tests de `monte_carlo_portfolio`: canasta por `trading_day` (R42-R46, R51-R52)."""

from datetime import date, timedelta

import numpy as np
import pytest

from genesis.backtest.risk_profile import RiskProfile
from genesis.validation.errors import MonteCarloConfigError
from genesis.validation.montecarlo import (
    _build_basket,
    _resample_day_sequence,
    monte_carlo_portfolio,
)
from tests.validation.fixtures.ledgers import build_empty_ledger, build_ledger_with_daily_trades

pytestmark = pytest.mark.unit

_N_DAYS = 40


def _correlated_daily_deltas(
    seed: int,
) -> tuple[list[tuple[date, float]], list[tuple[date, float]]]:
    """Series diarias correlacionadas por construcción para `sym_a`/`sym_b` (R46)."""
    rng = np.random.default_rng(seed)
    base = date(2024, 1, 1)
    days = [base + timedelta(days=i) for i in range(_N_DAYS)]
    series_a = rng.normal(0.0, 10.0, size=_N_DAYS)
    noise = rng.normal(0.0, 1.0, size=_N_DAYS)
    series_b = 0.9 * series_a + noise  # fuertemente correlacionada con series_a
    deltas_a = list(zip(days, series_a.tolist(), strict=True))
    deltas_b = list(zip(days, series_b.tolist(), strict=True))
    return deltas_a, deltas_b


def test_monte_carlo_portfolio_produce_block_bootstrap_finito(
    risk_profile_fixture: RiskProfile,
) -> None:
    deltas_a, deltas_b = _correlated_daily_deltas(seed=1)
    ledger_a = build_ledger_with_daily_trades(deltas_a, symbol="US500")
    ledger_b = build_ledger_with_daily_trades(deltas_b, symbol="NAS100")

    result = monte_carlo_portfolio(
        {"US500": ledger_a, "NAS100": ledger_b}, risk_profile_fixture, n_paths=200, seed=42
    )

    assert len(result.block_bootstrap.max_drawdown_per_path) == 200
    assert set(result.provenance_by_symbol) == {"US500", "NAS100"}
    assert result.block_bootstrap.block_size == 5  # default (R44)


def test_monte_carlo_portfolio_block_size_explicito(risk_profile_fixture: RiskProfile) -> None:
    deltas_a, deltas_b = _correlated_daily_deltas(seed=2)
    ledger_a = build_ledger_with_daily_trades(deltas_a, symbol="US500")
    ledger_b = build_ledger_with_daily_trades(deltas_b, symbol="NAS100")

    result = monte_carlo_portfolio(
        {"US500": ledger_a, "NAS100": ledger_b},
        risk_profile_fixture,
        n_paths=50,
        seed=1,
        block_size=10,
    )
    assert result.block_bootstrap.block_size == 10


def test_monte_carlo_portfolio_determinismo(risk_profile_fixture: RiskProfile) -> None:
    deltas_a, deltas_b = _correlated_daily_deltas(seed=3)
    ledger_a = build_ledger_with_daily_trades(deltas_a, symbol="US500")
    ledger_b = build_ledger_with_daily_trades(deltas_b, symbol="NAS100")
    ledgers = {"US500": ledger_a, "NAS100": ledger_b}

    result1 = monte_carlo_portfolio(ledgers, risk_profile_fixture, n_paths=100, seed=9)
    result2 = monte_carlo_portfolio(ledgers, risk_profile_fixture, n_paths=100, seed=9)

    assert np.array_equal(
        result1.block_bootstrap.max_drawdown_per_path,
        result2.block_bootstrap.max_drawdown_per_path,
    )
    assert np.array_equal(
        result1.block_bootstrap.breach_per_path, result2.block_bootstrap.breach_per_path
    )


def test_monte_carlo_portfolio_todos_los_ledgers_vacios_lanza(
    risk_profile_fixture: RiskProfile,
) -> None:
    ledgers = {"US500": build_empty_ledger(), "NAS100": build_empty_ledger()}
    with pytest.raises(MonteCarloConfigError):
        monte_carlo_portfolio(ledgers, risk_profile_fixture, n_paths=10, seed=1)


def test_monte_carlo_portfolio_n_paths_no_positivo_lanza(risk_profile_fixture: RiskProfile) -> None:
    deltas_a, deltas_b = _correlated_daily_deltas(seed=4)
    ledgers = {
        "US500": build_ledger_with_daily_trades(deltas_a, symbol="US500"),
        "NAS100": build_ledger_with_daily_trades(deltas_b, symbol="NAS100"),
    }
    with pytest.raises(MonteCarloConfigError):
        monte_carlo_portfolio(ledgers, risk_profile_fixture, n_paths=0, seed=1)


def test_correlation_preserved_golden() -> None:
    """R43/R46: la canasta por día preserva qué símbolos co-ocurrieron durante el resampleo.

    Golden: dos series diarias correlacionadas por construcción (`series_b = 0.9 *
    series_a + ruido`); tras un resampleo de bloques de días, la correlación entre
    las series reconstruidas de `sym_a`/`sym_b` (leídas de la MISMA canasta atómica
    por día) se mantiene alta, dentro de una tolerancia fijada en este test — porque
    cada día resampleado arrastra intacto el par `(sym_a, sym_b)` de ese día.
    """
    deltas_a, deltas_b = _correlated_daily_deltas(seed=5)
    ledger_a = build_ledger_with_daily_trades(deltas_a, symbol="US500")
    ledger_b = build_ledger_with_daily_trades(deltas_b, symbol="NAS100")

    basket_days, basket = _build_basket({"US500": ledger_a, "NAS100": ledger_b})
    assert len(basket_days) == _N_DAYS

    original_a = [_delta_for(basket[day], "US500") for day in basket_days]
    original_b = [_delta_for(basket[day], "NAS100") for day in basket_days]
    original_corr = float(np.corrcoef(original_a, original_b)[0, 1])
    assert original_corr > 0.8  # correlacionadas por construcción

    rng = np.random.default_rng(123)
    resampled_days = _resample_day_sequence(basket_days, block_size=5, rng=rng, target_len=_N_DAYS)
    resampled_a = [_delta_for(basket[day], "US500") for day in resampled_days]
    resampled_b = [_delta_for(basket[day], "NAS100") for day in resampled_days]
    resampled_corr = float(np.corrcoef(resampled_a, resampled_b)[0, 1])

    assert resampled_corr > 0.8
    assert abs(resampled_corr - original_corr) < 0.2


def _delta_for(basket_entries: list[tuple[str, float]], symbol: str) -> float:
    for entry_symbol, delta in basket_entries:
        if entry_symbol == symbol:
            return delta
    raise AssertionError(f"símbolo {symbol!r} no encontrado en la canasta del día")
