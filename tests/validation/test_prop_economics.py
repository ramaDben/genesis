"""Tests de `PropEconomicsProfile`/`load_prop_economics_profile`/hash (R7-R14)."""

import pytest

from genesis.validation.errors import PropSimConfigError
from genesis.validation.prop_sim import (
    _DEFAULT_PROFILE_HASH,
    PhaseSpec,
    PropEconomicsProfile,
    load_prop_economics_profile,
    prop_economics_profile_hash,
)

pytestmark = pytest.mark.unit


def test_load_prop_economics_profile_retorna_ficha_default_the5ers() -> None:
    profile = load_prop_economics_profile()

    assert profile.name == "The5ers"
    assert len(profile.phases) == 2
    assert profile.phases[0].profit_target_pct == pytest.approx(8.0)
    assert profile.phases[0].min_profitable_days == 3
    assert profile.phases[0].min_profit_per_day_pct == pytest.approx(0.5)
    assert profile.phases[0].max_calendar_days is None
    assert profile.phases[1].profit_target_pct == pytest.approx(5.0)
    assert profile.challenge_cost_pct_of_balance == pytest.approx(3.0)
    assert profile.profit_split_pct == pytest.approx(80.0)
    assert profile.payout_cycle_days == 14
    assert profile.max_lots is None
    assert profile.max_positions is None
    assert profile.consistency_rule_pct is None


def test_prop_economics_profile_hash_es_determinista() -> None:
    profile_a = load_prop_economics_profile()
    profile_b = load_prop_economics_profile()

    assert prop_economics_profile_hash(profile_a) == prop_economics_profile_hash(profile_b)


def test_prop_economics_profile_hash_default_es_estable() -> None:
    assert prop_economics_profile_hash(load_prop_economics_profile()) == _DEFAULT_PROFILE_HASH


def test_prop_economics_profile_hash_cambia_con_valores_distintos() -> None:
    profile_a = load_prop_economics_profile()
    profile_b = PropEconomicsProfile(
        name=profile_a.name,
        phases=profile_a.phases,
        challenge_cost_pct_of_balance=5.0,
        profit_split_pct=profile_a.profit_split_pct,
        payout_cycle_days=profile_a.payout_cycle_days,
        max_lots=profile_a.max_lots,
        max_positions=profile_a.max_positions,
        consistency_rule_pct=profile_a.consistency_rule_pct,
    )

    assert prop_economics_profile_hash(profile_a) != prop_economics_profile_hash(profile_b)


def _valid_phase() -> PhaseSpec:
    return PhaseSpec(
        profit_target_pct=8.0,
        min_profitable_days=3,
        min_profit_per_day_pct=0.5,
        max_calendar_days=None,
    )


def test_phases_vacio_lanza_prop_sim_config_error() -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(),
            challenge_cost_pct_of_balance=3.0,
            profit_split_pct=80.0,
            payout_cycle_days=14,
            max_lots=None,
            max_positions=None,
            consistency_rule_pct=None,
        )


def test_profit_target_pct_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(
                PhaseSpec(
                    profit_target_pct=0.0,
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


def test_payout_cycle_days_no_positivo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(_valid_phase(),),
            challenge_cost_pct_of_balance=3.0,
            profit_split_pct=80.0,
            payout_cycle_days=0,
            max_lots=None,
            max_positions=None,
            consistency_rule_pct=None,
        )


@pytest.mark.parametrize("profit_split_pct", [0.0, -1.0, 100.1, 200.0])
def test_profit_split_pct_fuera_de_rango_lanza(profit_split_pct: float) -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(_valid_phase(),),
            challenge_cost_pct_of_balance=3.0,
            profit_split_pct=profit_split_pct,
            payout_cycle_days=14,
            max_lots=None,
            max_positions=None,
            consistency_rule_pct=None,
        )


def test_challenge_cost_negativo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(_valid_phase(),),
            challenge_cost_pct_of_balance=-1.0,
            profit_split_pct=80.0,
            payout_cycle_days=14,
            max_lots=None,
            max_positions=None,
            consistency_rule_pct=None,
        )


def test_min_profitable_days_negativo_lanza() -> None:
    with pytest.raises(PropSimConfigError):
        PropEconomicsProfile(
            name="Test",
            phases=(
                PhaseSpec(
                    profit_target_pct=8.0,
                    min_profitable_days=-1,
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
