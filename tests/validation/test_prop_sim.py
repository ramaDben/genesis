"""Tests de `prop_sim.py`: resampleo diario + máquina de estados + agregación (R15-R56)."""

import dataclasses
import math
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from genesis.backtest.ledger import Ledger
from genesis.data.house_rule import (
    ConsistencyRule,
    ConsistencySemantics,
    HouseRule,
    MaxLossLimit,
    MaxLossLimitKind,
)
from genesis.data.profile import FirmProfile
from genesis.validation.errors import PropSimConfigError
from genesis.validation.prop_sim import (
    PhaseSpec,
    PropEconomicsProfile,
    PropSimConfig,
    PropSimOutcomeKind,
    PropSimResult,
    _aggregate_path_outcomes,
    _build_daily_basket,
    _default_block_size,
    _resample_daily_pnl_path,
    _simulate_single_path,
    run_prop_sim,
    simulate_challenge_paths,
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
        is_placeholder=True,
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
        is_placeholder=True,
    )


def _default_config(*, max_attempts: int = 10) -> PropSimConfig:
    return PropSimConfig(n_paths=1, seed=42, max_attempts=max_attempts)


def test_roza_limite_diario_no_reinicia(house_rule_fixture: HouseRule) -> None:
    """R38a: `daily_loss` justo por debajo del umbral (4999.99 < 5000.0) no dispara breach."""
    daily_pnl = [-4_999.99]
    outcome, cost_paid = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        house_rule_fixture,
        _default_config(max_attempts=3),
    )
    assert outcome.n_attempts_used == 1  # sin reinicio
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    # R37: el primer intento también se cuenta -> 1x challenge_cost, nunca 0.0.
    expected_cost = _STARTING_BALANCE * _default_profile().challenge_cost_pct_of_balance / 100.0
    assert cost_paid == pytest.approx(expected_cost)


def test_viola_limite_diario_reinicia(house_rule_fixture: HouseRule) -> None:
    """R38b: `daily_loss == threshold` exactamente (5000.0 == 5000.0) dispara breach (`>=`)."""
    daily_pnl = [-5_000.0]
    outcome, cost_paid = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        house_rule_fixture,
        _default_config(max_attempts=3),
    )
    assert outcome.n_attempts_used == 2  # reinició una vez
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    # R37: 2 intentos iniciados (el primero + el reinicio) -> 2x challenge_cost.
    expected_cost = 2 * _STARTING_BALANCE * _default_profile().challenge_cost_pct_of_balance / 100.0
    assert cost_paid == pytest.approx(expected_cost)


def test_static_vs_trailing_outcome_distinto(house_rule_fixture: HouseRule) -> None:
    """R36/R38c: mismo P&L, ancla STATIC vs. TRAILING -> outcome/breach_trading_day_index distintos.

    Serie: sube a 120k (nuevo pico) y luego cae gradualmente (pérdidas diarias <5%,
    nunca dispara breach DIARIO) hasta que, en el día 5, la caída acumulada desde el
    pico (120k -> 108k = 12k) alcanza exactamente el 10% de TRAILING (umbral=12k),
    mientras que STATIC (ancla=starting_balance=100k) nunca ve `balance < 100k`.
    """
    daily_pnl = [20_000.0, -3_000.0, -3_000.0, -3_000.0, -3_000.0]
    config = _default_config(max_attempts=1)

    static_house_rule = house_rule_fixture
    outcome_static, _ = _simulate_single_path(
        daily_pnl, _STARTING_BALANCE, _default_profile(), static_house_rule, config
    )
    trailing_house_rule = dataclasses.replace(
        house_rule_fixture,
        max_loss_limit=MaxLossLimit(
            amount=house_rule_fixture.max_loss_limit.amount,
            kind=MaxLossLimitKind.TRAILING_INTRADAY,
        ),
    )
    outcome_trailing, _ = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        trailing_house_rule,
        config,
    )

    assert outcome_static.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END
    assert outcome_static.breach_trading_day_index is None

    assert outcome_trailing.outcome is PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
    assert outcome_trailing.breach_trading_day_index == 4

    assert outcome_static.outcome != outcome_trailing.outcome
    assert outcome_static.breach_trading_day_index != outcome_trailing.breach_trading_day_index


def test_avance_fase_target_sin_dias_suficientes_no_avanza(house_rule_fixture: HouseRule) -> None:
    """R39: target cruzado en día 1, pero `phase_profitable_days` nunca llega a 2 -> no avanza."""
    profile = _single_phase_profile(
        profit_target_pct=10.0, min_profitable_days=2, min_profit_per_day_pct=1.0
    )
    daily_pnl = [150.0, 0.0]  # día 1: +15% (target 10% cruzado, 1 día rentable); día 2: plano

    outcome, _ = _simulate_single_path(
        daily_pnl, 1_000.0, profile, house_rule_fixture, _default_config()
    )

    assert outcome.funded_trading_day_index is None
    assert outcome.outcome is PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END


def test_avance_fase_target_y_dias_suficientes_avanza(house_rule_fixture: HouseRule) -> None:
    """R39: target ya cruzado + 2º día rentable (`phase_profitable_days == 2`) -> avanza (funda)."""
    profile = _single_phase_profile(
        profit_target_pct=10.0, min_profitable_days=2, min_profit_per_day_pct=1.0
    )
    daily_pnl = [150.0, 0.0, 20.0]  # día 3: +20/1150 ~= 1.74% >= 1% -> 2º día rentable

    outcome, _ = _simulate_single_path(
        daily_pnl, 1_000.0, profile, house_rule_fixture, _default_config()
    )

    assert outcome.funded_trading_day_index == 2


def test_max_attempts_1_termina_en_primer_breach(house_rule_fixture: HouseRule) -> None:
    """R40: `max_attempts=1` -> `NEVER_FUNDED_ATTEMPTS_EXHAUSTED` en el primer breach."""
    daily_pnl = [-5_000.0]
    outcome, _ = _simulate_single_path(
        daily_pnl,
        _STARTING_BALANCE,
        _default_profile(),
        house_rule_fixture,
        _default_config(max_attempts=1),
    )

    assert outcome.outcome is PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
    assert outcome.n_attempts_used == 1
    assert outcome.breach_trading_day_index == 0


def test_total_challenge_cost_paid_incluye_el_primer_intento(house_rule_fixture: HouseRule) -> None:
    """R37: `total_challenge_cost_paid` se incrementa por cada intento iniciado, incluido el 1º.

    Una trayectoria sin ningún breach (1 solo intento, nunca reinicia) debe reportar
    exactamente 1x `challenge_cost`; con N intentos (N-1 reinicios por breach), N x
    `challenge_cost`.
    """
    profile = _default_profile()
    challenge_cost = _STARTING_BALANCE * profile.challenge_cost_pct_of_balance / 100.0

    # 1 solo intento: ninguna pérdida dispara breach en ningún día.
    daily_pnl_sin_breach = [10.0, 10.0, 10.0]
    outcome_1, cost_paid_1 = _simulate_single_path(
        daily_pnl_sin_breach,
        _STARTING_BALANCE,
        profile,
        house_rule_fixture,
        _default_config(max_attempts=10),
    )
    assert outcome_1.n_attempts_used == 1
    assert cost_paid_1 == pytest.approx(1 * challenge_cost)

    # 3 intentos: 2 breaches consecutivos (reinician) + 1 intento final sin breach.
    daily_pnl_tres_intentos = [-5_000.0, -5_000.0, 10.0]
    outcome_3, cost_paid_3 = _simulate_single_path(
        daily_pnl_tres_intentos,
        _STARTING_BALANCE,
        profile,
        house_rule_fixture,
        _default_config(max_attempts=10),
    )
    assert outcome_3.n_attempts_used == 3
    assert cost_paid_3 == pytest.approx(3 * challenge_cost)


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
    house_rule_fixture: HouseRule,
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
        house_rule_fixture,
        _default_config(),
    )

    assert outcome.funded_trading_day_index == 0
    assert outcome.outcome is PropSimOutcomeKind.FUNDED_BREACHED_TOTAL
    assert outcome.breach_trading_day_index == 1


def test_funded_survived_horizon_censura_al_horizonte(house_rule_fixture: HouseRule) -> None:
    """R29: trayectoria fondeada que sobrevive el horizonte completo, censurada, sin breach."""

    profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.1
    )
    config = replace(_default_config(), horizon_months=1, trading_days_per_month=3)
    # día 0: financia; días 1-3: planos (3 días fondeados observados == horizonte 1*3).
    daily_pnl = [6_000.0, 0.0, 0.0, 0.0]

    outcome, _ = _simulate_single_path(
        daily_pnl, _STARTING_BALANCE, profile, house_rule_fixture, config
    )

    assert outcome.outcome is PropSimOutcomeKind.FUNDED_SURVIVED_HORIZON
    assert outcome.funded_survival_trading_days == 3
    assert outcome.n_funded_months_observed == 1


# --- A5: agregación P1-P6 + run_prop_sim (R41-R56) ---

_FAST_CONFIG = PropSimConfig(
    n_paths=50, seed=123, horizon_months=2, trading_days_per_month=10, path_horizon_trading_days=100
)


def _synthetic_daily_pnl(
    n_days: int, seed: int, *, drift: float = 300.0, scale: float = 800.0
) -> dict:
    rng = np.random.default_rng(seed)
    base_day = date(2024, 1, 1)
    values = rng.normal(drift, scale, size=n_days)
    return {base_day + timedelta(days=i): float(value) for i, value in enumerate(values)}


def _harden_profile(
    profile: PropEconomicsProfile, *, cost_delta: float, split_delta: float, target_delta: float
) -> PropEconomicsProfile:
    return PropEconomicsProfile(
        name=profile.name,
        phases=tuple(
            replace(phase, profit_target_pct=phase.profit_target_pct + target_delta)
            for phase in profile.phases
        ),
        challenge_cost_pct_of_balance=profile.challenge_cost_pct_of_balance + cost_delta,
        profit_split_pct=max(0.01, profile.profit_split_pct - split_delta),
        payout_cycle_days=profile.payout_cycle_days,
        max_lots=profile.max_lots,
        max_positions=profile.max_positions,
        is_placeholder=profile.is_placeholder,
    )


def test_run_prop_sim_canasta_vacia_lanza(firm_profile_fixture: FirmProfile) -> None:
    with pytest.raises(PropSimConfigError):
        run_prop_sim(
            {"US500": build_empty_ledger()},
            _STARTING_BALANCE,
            firm_profile_fixture,
            _default_profile(),
            _FAST_CONFIG,
            "cand-A",
        )


@given(
    cost_delta=st.floats(min_value=0.1, max_value=10.0),
    split_delta=st.floats(min_value=0.1, max_value=20.0),
    target_delta=st.floats(min_value=0.1, max_value=5.0),
)
@settings(
    max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_monotonia_ficha(
    cost_delta: float,
    split_delta: float,
    target_delta: float,
    firm_profile_fixture: FirmProfile,
) -> None:
    """R52: endurecer la ficha nunca mejora p_pass/payout_p25_12m/median_funded_survival_months."""
    daily_pnl_by_day = _synthetic_daily_pnl(60, seed=7)
    base_profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.1
    )
    hardened_profile = _harden_profile(
        base_profile, cost_delta=cost_delta, split_delta=split_delta, target_delta=target_delta
    )

    result_base = simulate_challenge_paths(
        daily_pnl_by_day,
        _STARTING_BALANCE,
        base_profile,
        firm_profile_fixture,
        _FAST_CONFIG,
        "cand-A",
    )
    result_hardened = simulate_challenge_paths(
        daily_pnl_by_day,
        _STARTING_BALANCE,
        hardened_profile,
        firm_profile_fixture,
        _FAST_CONFIG,
        "cand-A",
    )

    assert result_hardened.p_pass <= result_base.p_pass + 1e-9
    assert result_hardened.payout_p25_12m <= result_base.payout_p25_12m + 1e-6
    assert (
        result_hardened.median_funded_survival_months
        <= result_base.median_funded_survival_months + 1e-9
    )


def test_determinismo(firm_profile_fixture: FirmProfile) -> None:
    """R51/R53: dos `run_prop_sim` con mismos insumos producen `PropSimResult` idéntico."""
    daily_pnl_by_day = _synthetic_daily_pnl(60, seed=3)
    ledger = build_ledger_with_daily_trades(list(daily_pnl_by_day.items()), symbol="US500")

    result1 = run_prop_sim(
        {"US500": ledger},
        _STARTING_BALANCE,
        firm_profile_fixture,
        _default_profile(),
        _FAST_CONFIG,
        "cand-A",
    )
    result2 = run_prop_sim(
        {"US500": ledger},
        _STARTING_BALANCE,
        firm_profile_fixture,
        _default_profile(),
        _FAST_CONFIG,
        "cand-A",
    )

    assert result1 == result2


@pytest.mark.integration
def test_integracion_run_prop_sim(
    firm_profile_fixture: FirmProfile,
    oos_ledgers_by_symbol_fixture: dict[str, Ledger],
) -> None:
    """R54: `run_prop_sim` en segundos; campos finitos, fracciones/probabilidades en [0,1]."""
    result = run_prop_sim(
        oos_ledgers_by_symbol_fixture,
        _STARTING_BALANCE,
        firm_profile_fixture,
        _default_profile(),
        replace(_FAST_CONFIG, n_paths=100),
        "cand-A",
    )

    assert isinstance(result, PropSimResult)
    assert 0.0 <= result.p_pass <= 1.0
    assert 0.0 <= result.p_daily_breach_funded_month <= 1.0
    assert math.isfinite(result.payout_p25_12m)
    assert math.isfinite(result.median_funded_survival_months)
    assert result.expected_attempts > 0.0  # finito o inf, nunca <=0
    assert result.n_paths == 100


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_slow_volumen(
    firm_profile_fixture: FirmProfile,
    oos_ledgers_by_symbol_fixture: dict[str, Ledger],
) -> None:
    """R55: `n_paths >= 2000`, separado de la suite rápida por defecto."""
    result = run_prop_sim(
        oos_ledgers_by_symbol_fixture,
        _STARTING_BALANCE,
        firm_profile_fixture,
        _default_profile(),
        replace(_FAST_CONFIG, n_paths=2_000, seed=99),
        "cand-A",
    )

    assert result.n_paths == 2_000
    assert 0.0 <= result.p_pass <= 1.0


# --- D2 (Change #109): consistency_rule bloquea la fase, P3 vinculante sin DLL, payout_buffer ---


def test_consistency_rule_terminates_not_fails(house_rule_fixture: HouseRule) -> None:
    """Eval U9 (D5, AC10): la 3ª cláusula bloquea la promoción, no descalifica la trayectoria.

    Día 1: +6_000 sobre 100_000 -> cruza el target (5%) y el mínimo de días rentables,
    pero ese único día es el 100% del profit acumulado (>30% de `consistency_rule.pct`):
    no promociona, y la trayectoria sigue (ningún `NEVER_FUNDED_*` en ese día). Día 2:
    +6_000 adicionales -> el día más grande ahora es <=30% del total acumulado -> funda.
    """
    house_rule_with_consistency = dataclasses.replace(
        house_rule_fixture,
        consistency_rule=ConsistencyRule(pct=50.0, semantics=ConsistencySemantics.TERMINATE),
    )
    profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.0
    )
    daily_pnl = [6_000.0, 6_000.0]

    outcome, _ = _simulate_single_path(
        daily_pnl, _STARTING_BALANCE, profile, house_rule_with_consistency, _default_config()
    )

    assert outcome.outcome is not PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
    # El día 1 (índice 0) no promocionó (ratio 100% > 50%); el día 2 (índice 1) sí.
    assert outcome.funded_trading_day_index == 1


def test_consistency_rule_fail_no_modelada_lanza(house_rule_fixture: HouseRule) -> None:
    """`ConsistencySemantics.FAIL` no está modelada (D5): `PropSimConfigError` fail-fast."""
    house_rule_fail = dataclasses.replace(
        house_rule_fixture,
        consistency_rule=ConsistencyRule(pct=30.0, semantics=ConsistencySemantics.FAIL),
    )
    profile = _single_phase_profile(
        profit_target_pct=5.0, min_profitable_days=1, min_profit_per_day_pct=0.0
    )
    with pytest.raises(PropSimConfigError, match="fail"):
        _simulate_single_path(
            [6_000.0], _STARTING_BALANCE, profile, house_rule_fail, _default_config()
        )


def test_p3_usa_el_colchon_cuando_no_hay_dll() -> None:
    """Eval U10 (D6): sin DLL declarado, un día que consume el colchón sí cuenta para P3.

    `binding_daily_threshold` sin DLL es la distancia al piso de `max_loss_limit`
    (SSoT §7.3, "el colchón del día"): por construcción, ese breach diario coincide
    con el breach TOTAL el mismo día (nunca es un evento continuable aislado). El mes
    parcial en curso se cierra en ese punto para que el numerador de
    `p_daily_breach_funded_month` no colapse a cero (el "bypass" que SSoT prohíbe).
    """
    house_rule_no_dll = HouseRule(
        max_loss_limit=MaxLossLimit(amount=2_000.0, kind=MaxLossLimitKind.STATIC),
        threshold_lock_at=None,
        daily_loss_limit=None,
        consistency_rule=None,
        weekend_holding_allowed=True,
        payout_buffer=0.0,
        min_net_profit_between_payouts=0.0,
        funded_starting_balance=0.0,
        account_size=50_000.0,
    )
    profile = _single_phase_profile(
        profit_target_pct=1.0, min_profitable_days=1, min_profit_per_day_pct=0.0
    )
    # día 0: financia (600 >= 1% de 50_000 = 500); día 1: pierde exactamente el
    # colchón (2_000) -> breach DIARIO y TOTAL el mismo día.
    daily_pnl = [600.0, -2_000.0]

    outcome, _ = _simulate_single_path(
        daily_pnl, 50_000.0, profile, house_rule_no_dll, _default_config()
    )

    assert outcome.outcome is PropSimOutcomeKind.FUNDED_BREACHED_TOTAL
    assert outcome.n_funded_months_observed == 1
    assert outcome.n_funded_months_with_daily_breach == 1

    result = _aggregate_path_outcomes(
        [outcome],
        0.0,
        candidate_id="cand-U10",
        config_version="test",
        seed=1,
        trading_days_per_month=21,
    )
    assert result.p_daily_breach_funded_month > 0.0


def test_payout_buffer_retiene_el_primer_retiro(house_rule_fixture: HouseRule) -> None:
    """Eval U11 (R1): sin consumidor todavía en `_simulate_single_path` (alcance de D2 es P3/D5).

    `payout_buffer`/`min_net_profit_between_payouts` viven en `HouseRule` (R1, ficha
    extendida) pero `_simulate_single_path` no los aplica: el payout se calcula sobre
    `profit_split_pct` de `PropEconomicsProfile`, no sobre el buffer de la casa. Este
    test fija el contrato explícito: el campo existe y es leíble, sin fingir un
    consumidor que D2 no implementó (alcance declarado del change, no un hueco).
    """
    assert house_rule_fixture.payout_buffer == pytest.approx(0.0)  # the5ers: sin buffer normativo
    mffu_like = dataclasses.replace(house_rule_fixture, payout_buffer=2_100.0)
    assert mffu_like.payout_buffer == pytest.approx(2_100.0)


def test_run_prop_sim_ficha_sin_house_rule_falla_ruidoso() -> None:
    """Eval I-6 (D2): `house_rule is None` inyectada en `run_prop_sim` -> `PropSimConfigError`."""
    from pathlib import Path

    import genesis.data.profiles as profiles_package
    from genesis.data.profile import load_firm_profile

    binance_path = Path(profiles_package.__file__).parent / "binance_futures.json"
    exchange_profile = load_firm_profile(binance_path)
    assert exchange_profile.house_rule is None

    with pytest.raises(PropSimConfigError, match="cand-exchange"):
        run_prop_sim(
            {"BTCUSDT": build_ledger_with_daily_trades([(date(2024, 1, 1), 10.0)])},
            _STARTING_BALANCE,
            exchange_profile,
            _default_profile(),
            _FAST_CONFIG,
            "cand-exchange",
        )


@pytest.mark.statistical
def test_p_pass_mffu_endurece_el_juicio_frente_a_ficha_estatica_laxa(
    firm_profile_fixture: FirmProfile,
) -> None:
    """Eval S-1 (E4): con semilla fija, `p_pass(MFFU) <= p_pass($5_000 estático)`.

    Evidencia mecánica de que el Change #109 **endureció** el juicio: el contrato
    real (trailing EOD a $2_000 con congelamiento a $52_100) es más estricto que un
    límite estático más laxo de $5_000 sobre la misma cuenta y la misma canasta de
    P&L. Si diera al revés, sería un error de implementación, no un hallazgo
    (tasks.md E4, no es la asignación de PROP-4/S-2 de H-3, es una tarea propia).
    """
    daily_pnl_by_day = _synthetic_daily_pnl(90, seed=42, drift=0.0, scale=1_800.0)
    profile = PropEconomicsProfile(
        name="Test",
        phases=(
            PhaseSpec(
                profit_target_pct=8.0,
                min_profitable_days=3,
                min_profit_per_day_pct=0.1,
                max_calendar_days=None,
            ),
            PhaseSpec(
                profit_target_pct=5.0,
                min_profitable_days=3,
                min_profit_per_day_pct=0.1,
                max_calendar_days=None,
            ),
        ),
        challenge_cost_pct_of_balance=0.0,
        profit_split_pct=80.0,
        payout_cycle_days=14,
        max_lots=None,
        max_positions=None,
        is_placeholder=True,
    )
    config = replace(_FAST_CONFIG, max_attempts=3)

    mffu_like_house_rule = HouseRule(
        max_loss_limit=MaxLossLimit(amount=2_000.0, kind=MaxLossLimitKind.TRAILING_EOD),
        threshold_lock_at=52_100.0,
        daily_loss_limit=None,
        consistency_rule=None,
        weekend_holding_allowed=False,
        payout_buffer=2_100.0,
        min_net_profit_between_payouts=500.0,
        funded_starting_balance=0.0,
        account_size=50_000.0,
    )
    lax_static_house_rule = HouseRule(
        max_loss_limit=MaxLossLimit(amount=5_000.0, kind=MaxLossLimitKind.STATIC),
        threshold_lock_at=None,
        daily_loss_limit=None,
        consistency_rule=None,
        weekend_holding_allowed=True,
        payout_buffer=0.0,
        min_net_profit_between_payouts=0.0,
        funded_starting_balance=0.0,
        account_size=50_000.0,
    )
    firm_profile_mffu = dataclasses.replace(firm_profile_fixture, house_rule=mffu_like_house_rule)
    firm_profile_lax = dataclasses.replace(firm_profile_fixture, house_rule=lax_static_house_rule)

    result_mffu = simulate_challenge_paths(
        daily_pnl_by_day, 50_000.0, profile, firm_profile_mffu, config, "cand-mffu"
    )
    result_lax = simulate_challenge_paths(
        daily_pnl_by_day, 50_000.0, profile, firm_profile_lax, config, "cand-lax"
    )

    assert result_mffu.p_pass <= result_lax.p_pass + 1e-9
