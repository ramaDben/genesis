"""Tests de `prop_sim.py`: resampleo diario + máquina de estados + agregación (R15-R56)."""

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile
from genesis.data.profile import FirmProfile
from genesis.validation.errors import PropSimConfigError
from genesis.validation.prop_sim import (
    PhaseSpec,
    PropEconomicsProfile,
    PropSimConfig,
    PropSimOutcomeKind,
    _build_daily_basket,
    _default_block_size,
    _resample_daily_pnl_path,
    _simulate_single_path,
)
from tests.validation.fixtures.ledgers import build_empty_ledger, build_ledger_with_daily_trades

pytestmark = pytest.mark.unit


def test_build_daily_basket_suma_por_dia_across_simbolos() -> None:
    day1, day2 = date(2024, 1, 1), date(2024, 1, 2)
    ledger_a = build_ledger_with_daily_trades([(day1, 10.0), (day2, -5.0)], symbol="US500")
    ledger_b = build_ledger_with_daily_trades([(day1, 3.0), (day2, 7.0)], symbol="NAS100")

    basket_days, daily_totals = _build_daily_basket({"US500": ledger_a, "NAS100": ledger_b})

    assert basket_days == [day1, day2]
    assert daily_totals[day1] == pytest.approx(13.0)
    assert daily_totals[day2] == pytest.approx(2.0)


def test_build_daily_basket_vacio_si_ledgers_sin_trades() -> None:
    basket_days, daily_totals = _build_daily_basket(
        {"US500": build_empty_ledger(), "NAS100": build_empty_ledger()}
    )
    assert basket_days == []
    assert daily_totals == {}


def test_default_block_size_formula() -> None:
    assert _default_block_size(1) == 5  # clip inferior
    assert _default_block_size(1_000_000) == 60  # clip superior
    assert _default_block_size(1000) == 10  # round(1000 ** (1/3)) == 10


def test_resample_daily_pnl_path_produce_exactamente_target_len() -> None:
    basket_days = [date(2024, 1, d) for d in range(1, 11)]
    daily_totals = {day: float(index) for index, day in enumerate(basket_days)}
    rng = np.random.default_rng(42)

    path = _resample_daily_pnl_path(basket_days, daily_totals, block_size=3, rng=rng, target_len=25)

    assert len(path) == 25
    assert all(value in daily_totals.values() for value in path)


def test_resample_daily_pnl_path_es_determinista_con_mismo_seed() -> None:
    basket_days = [date(2024, 1, d) for d in range(1, 11)]
    daily_totals = {day: float(index) for index, day in enumerate(basket_days)}

    path1 = _resample_daily_pnl_path(
        basket_days, daily_totals, block_size=3, rng=np.random.default_rng(7), target_len=20
    )
    path2 = _resample_daily_pnl_path(
        basket_days, daily_totals, block_size=3, rng=np.random.default_rng(7), target_len=20
    )

    assert np.array_equal(path1, path2)


def test_prop_sim_config_defaults() -> None:
    config = PropSimConfig(n_paths=100, seed=1)
    assert config.max_attempts == 10
    assert config.horizon_months == 12
    assert config.trading_days_per_month == 21
    assert config.path_horizon_trading_days == 750
    assert config.block_size is None


def test_prop_sim_config_n_paths_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=0, seed=1)


def test_prop_sim_config_max_attempts_invalido_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, max_attempts=0)


def test_prop_sim_config_horizon_months_invalido_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, horizon_months=0)


def test_prop_sim_config_path_horizon_insuficiente_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(
            n_paths=10,
            seed=1,
            horizon_months=12,
            trading_days_per_month=21,
            path_horizon_trading_days=10,
        )


def test_prop_sim_config_block_size_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropSimConfig(n_paths=10, seed=1, block_size=0)


# --- Golden de la máquina de estados (A4, R23-R40, seed=42 documental) ---

_STARTING_BALANCE = 100_000.0


def _default_profile() -> PropEconomicsProfile:
    return PropEconomicsProfile(
        name="Test",
        phases=(
            PhaseSpec(
                profit_target_pct=8.0,
                min_profitable_days=3,
                min_profit_per_day_pct=0.5,
                max_calendar_days=None,
            ),
            PhaseSpec(
                profit_target_pct=5.0,
                min_profitable_days=3,
                min_profit_per_day_pct=0.5,
                max_calendar_days=None,
            ),
        ),
        challenge_cost_pct_of_balance=3.0,
        profit_split_pct=80.0,
        payout_cycle_days=14,
        max_lots=None,
        max_positions=None,
        consistency_rule_pct=None,
    )


def _single_phase_profile(
    *, profit_target_pct: float, min_profitable_days: int, min_profit_per_day_pct: float
) -> PropEconomicsProfile:
    return PropEconomicsProfile(
        name="Test",
        phases=(
            PhaseSpec(
                profit_target_pct=profit_target_pct,
                min_profitable_days=min_profitable_days,
                min_profit_per_day_pct=min_profit_per_day_pct,
                max_calendar_days=None,
            ),
        ),
        challenge_cost_pct_of_balance=0.0,
        profit_split_pct=80.0,
        payout_cycle_days=14,
        max_lots=None,
        max_positions=None,
        consistency_rule_pct=None,
    )


def _default_config(*, max_attempts: int = 10) -> PropSimConfig:
    return PropSimConfig(n_paths=1, seed=42, max_attempts=max_attempts)


def test_roza_limite_diario_no_reinicia(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R38a: `daily_loss` justo por debajo del umbral (4999.99 < 5000.0) no dispara breach."""
    daily_pnl = [-4_999.99]
    outcome, cost_paid = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        firm_profile_fixture,
        risk_profile_fixture,
        _default_config(max_attempts=3),
    )
    assert outcome.n_attempts_used == 1  # sin reinicio
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    assert cost_paid == pytest.approx(0.0)


def test_viola_limite_diario_reinicia(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R38b: `daily_loss == threshold` exactamente (5000.0 == 5000.0) dispara breach (`>=`)."""
    daily_pnl = [-5_000.0]
    outcome, cost_paid = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        firm_profile_fixture,
        risk_profile_fixture,
        _default_config(max_attempts=3),
    )
    assert outcome.n_attempts_used == 2  # reinició una vez
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    assert cost_paid > 0.0


def test_static_vs_trailing_outcome_distinto(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R36/R38c: mismo P&L, ancla STATIC vs. TRAILING -> outcome/breach_trading_day_index distintos.

    Serie: sube a 120k (nuevo pico) y luego cae gradualmente (pérdidas diarias <5%,
    nunca dispara breach DIARIO) hasta que, en el día 5, la caída acumulada desde el
    pico (120k -> 108k = 12k) alcanza exactamente el 10% de TRAILING (umbral=12k),
    mientras que STATIC (ancla=starting_balance=100k) nunca ve `balance < 100k`.
    """
    daily_pnl = [20_000.0, -3_000.0, -3_000.0, -3_000.0, -3_000.0]
    config = _default_config(max_attempts=1)

    static_risk = risk_profile_fixture
    outcome_static, _ = _simulate_single_path(
        daily_pnl, _STARTING_BALANCE, _default_profile(), firm_profile_fixture, static_risk, config
    )
    trailing_risk = RiskProfile(
        max_loss_limit_pct=risk_profile_fixture.max_loss_limit_pct,
        max_loss_limit_kind=MaxLossLimitKind.TRAILING,
        weekend_holding_allowed=risk_profile_fixture.weekend_holding_allowed,
    )
    outcome_trailing, _ = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        firm_profile_fixture,
        trailing_risk,
        config,
    )

    assert outcome_static.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    assert outcome_static.breach_trading_day_index is None

    assert outcome_trailing.outcome is PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
    assert outcome_trailing.breach_trading_day_index == 4

    assert outcome_static.outcome != outcome_trailing.outcome
    assert outcome_static.breach_trading_day_index != outcome_trailing.breach_trading_day_index


def test_avance_fase_target_sin_dias_suficientes_no_avanza(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R39: target cruzado en día 1, pero `phase_profitable_days` nunca llega a 2 -> no avanza."""
    profile = _single_phase_profile(
        profit_target_pct=10.0, min_profitable_days=2, min_profit_per_day_pct=1.0
    )
    daily_pnl = [150.0, 0.0]  # día 1: +15% (target 10% cruzado, 1 día rentable); día 2: plano

    outcome, _ = _simulate_single_path(
        daily_pnl, 1_000.0, profile, firm_profile_fixture, risk_profile_fixture, _default_config()
    )

    assert outcome.funded_trading_day_index is None
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END


def test_avance_fase_target_y_dias_suficientes_avanza(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R39: target ya cruzado + 2º día rentable (`phase_profitable_days == 2`) -> avanza (funda)."""
    profile = _single_phase_profile(
        profit_target_pct=10.0, min_profitable_days=2, min_profit_per_day_pct=1.0
    )
    daily_pnl = [150.0, 0.0, 20.0]  # día 3: +20/1150 ~= 1.74% >= 1% -> 2º día rentable

    outcome, _ = _simulate_single_path(
        daily_pnl, 1_000.0, profile, firm_profile_fixture, risk_profile_fixture, _default_config()
    )

    assert outcome.funded_trading_day_index == 2


def test_max_attempts_1_termina_en_primer_breach(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R40: `max_attempts=1` -> `NEVER_FUNDED_ATTEMPTS_EXHAUSTED` en el primer breach."""
    daily_pnl = [-5_000.0]
    outcome, _ = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        firm_profile_fixture,
        risk_profile_fixture,
        _default_config(max_attempts=1),
    )

    assert outcome.outcome is PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
    assert outcome.n_attempts_used == 1
    assert outcome.breach_trading_day_index == 0


def test_prop_sim_outcome_kind_tiene_exactamente_4_miembros() -> None:
    assert len(PropSimOutcomeKind) == 4


def test_prop_sim_outcome_kind_valores_esperados() -> None:
    assert {member.value for member in PropSimOutcomeKind} == {
        "funded_survived_horizon",
        "funded_breached_total",
        "never_funded_attempts_exhausted",
        "in_progress_unfunded_at_path_end",
    }


def test_funded_breached_total_registra_breach_y_supervivencia(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """Camino completo: financia y luego rompe el límite total (R27/R33)."""
    profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.1
    )
    # día 0: financia (target 5% cruzado, 1 día rentable); día 1: rompe el 10% total.
    daily_pnl = [6_000.0, -12_000.0]

    outcome, _ = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        profile,
        firm_profile_fixture,
        risk_profile_fixture,
        _default_config(),
    )

    assert outcome.funded_trading_day_index == 0
    assert outcome.outcome is PropSimOutcomeKind.FUNDED_BREACHED_TOTAL
    assert outcome.breach_trading_day_index == 1


def test_funded_survived_horizon_censura_al_horizonte(
    firm_profile_fixture: FirmProfile, risk_profile_fixture: RiskProfile
) -> None:
    """R29: trayectoria fondeada que sobrevive el horizonte completo, censurada, sin breach."""

    profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.1
    )
    config = replace(_default_config(), horizon_months=1, trading_days_per_month=3)
    # día 0: financia; días 1-3: planos (3 días fondeados observados == horizonte 1*3).
    daily_pnl = [6_000.0, 0.0, 0.0, 0.0]

    outcome, _ = _simulate_single_path(
        daily_pnl, _STARTING_BALANCE, profile, firm_profile_fixture, risk_profile_fixture, config
    )

    assert outcome.outcome is PropSimOutcomeKind.FUNDED_SURVIVED_HORIZON
    assert outcome.funded_survival_trading_days == 3
    assert outcome.n_funded_months_observed == 1
