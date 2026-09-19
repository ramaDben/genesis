"""Tests del contrato de la casa `HouseRule` (capa 1, Change #109).

Recibe, por redistribución declarada en `tasks.md` DT-3 (opción a), la mitad "casa"
de los tests que vivían en `tests/backtest/test_risk_profile.py`: el enum de
`MaxLossLimitKind` (ahora con tres miembros, no dos) y la mitad de los tests de
`frozen`/hash.
"""

import dataclasses

import pytest

from genesis.data.house_rule import (
    ConsistencyRule,
    ConsistencySemantics,
    DailyLossLimit,
    DailyLossLimitSemantics,
    HouseRule,
    MaxLossLimit,
    MaxLossLimitKind,
    house_rule_hash,
)

pytestmark = pytest.mark.unit


def _house_rule(**overrides: object) -> HouseRule:
    defaults: dict[str, object] = {
        "max_loss_limit": MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.TRAILING_EOD),
        "threshold_lock_at": 52100.0,
        "daily_loss_limit": None,
        "consistency_rule": ConsistencyRule(pct=30.0, semantics=ConsistencySemantics.TERMINATE),
        "weekend_holding_allowed": False,
        "payout_buffer": 2100.0,
        "min_net_profit_between_payouts": 500.0,
        "funded_starting_balance": 0.0,
        "account_size": 50000.0,
    }
    defaults.update(overrides)
    return HouseRule(**defaults)  # type: ignore[arg-type]


def test_max_loss_limit_kind_tiene_los_tres_valores_normativos() -> None:
    assert MaxLossLimitKind.STATIC == "static"
    assert MaxLossLimitKind.TRAILING_INTRADAY == "trailing_intraday"
    assert MaxLossLimitKind.TRAILING_EOD == "trailing_eod"


def test_max_loss_limit_es_frozen() -> None:
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.STATIC)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(limit, "amount", 1.0)  # noqa: B010


def test_house_rule_es_frozen() -> None:
    rule = _house_rule()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(rule, "payout_buffer", 0.0)  # noqa: B010


def test_u4_trailing_eod_congela_en_threshold_lock_at() -> None:
    """Eval U4: el ancla no se mueve más allá de `threshold_lock_at` (congelamiento)."""
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.TRAILING_EOD)
    nueva_ancla = limit.next_anchor(
        52100.0,
        floating_equity=53000.0,
        session_close_balance=53000.0,
        threshold_lock_at=52100.0,
    )
    assert nueva_ancla == 52100.0
    assert limit.threshold_from(nueva_ancla) == 50100.0


def test_hallazgo1_trailing_eod_acota_el_salto_al_threshold_lock_at() -> None:
    """El ancla nunca sobrepasa `threshold_lock_at` en un solo salto (bug de correctitud).

    `current_anchor=50_000.0` está por debajo de `threshold_lock_at=52_100.0` (no
    congelada todavía), pero el `session_close_balance` de la sesión salta a
    `53_000.0` en un solo paso: el ancla resultante debe quedar acotada en
    `52_100.0`, no en `53_000.0`.
    """
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.TRAILING_EOD)
    nueva_ancla = limit.next_anchor(
        50000.0,
        floating_equity=53000.0,
        session_close_balance=53000.0,
        threshold_lock_at=52100.0,
    )
    assert nueva_ancla == 52100.0


def test_hallazgo1_trailing_intraday_acota_el_salto_al_threshold_lock_at() -> None:
    """Mismo bug, vía `TRAILING_INTRADAY`: el salto de `floating_equity` se acota."""
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.TRAILING_INTRADAY)
    nueva_ancla = limit.next_anchor(
        50000.0,
        floating_equity=53000.0,
        session_close_balance=None,
        threshold_lock_at=52100.0,
    )
    assert nueva_ancla == 52100.0


def test_u5_trailing_eod_ignora_equity_flotante_sin_cierre_de_sesion() -> None:
    """Eval U5: sin `session_close_balance`, el ancla TRAILING_EOD no cambia."""
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.TRAILING_EOD)
    ancla = limit.next_anchor(
        50000.0,
        floating_equity=60000.0,
        session_close_balance=None,
        threshold_lock_at=None,
    )
    assert ancla == 50000.0


def test_max_loss_limit_static_nunca_mueve_el_ancla() -> None:
    limit = MaxLossLimit(amount=10000.0, kind=MaxLossLimitKind.STATIC)
    ancla = limit.next_anchor(
        100000.0,
        floating_equity=999999.0,
        session_close_balance=999999.0,
        threshold_lock_at=None,
    )
    assert ancla == 100000.0


def test_max_loss_limit_trailing_intraday_sigue_el_pico_de_equity_flotante() -> None:
    limit = MaxLossLimit(amount=10000.0, kind=MaxLossLimitKind.TRAILING_INTRADAY)
    ancla = limit.next_anchor(
        100000.0,
        floating_equity=105000.0,
        session_close_balance=None,
        threshold_lock_at=None,
    )
    assert ancla == 105000.0


def test_max_loss_limit_is_breached() -> None:
    limit = MaxLossLimit(amount=2000.0, kind=MaxLossLimitKind.STATIC)
    assert limit.is_breached(anchor=50000.0, equity=48000.0) is True
    assert limit.is_breached(anchor=50000.0, equity=48000.01) is False


def test_house_rule_hash_es_determinista() -> None:
    rule = _house_rule()
    assert house_rule_hash(rule) == house_rule_hash(rule)


def test_house_rule_hash_cambia_con_el_max_loss_limit() -> None:
    base = _house_rule()
    distinto = _house_rule(max_loss_limit=MaxLossLimit(amount=1000.0, kind=MaxLossLimitKind.STATIC))
    assert house_rule_hash(base) != house_rule_hash(distinto)


def test_house_rule_hash_cambia_con_consistency_rule() -> None:
    base = _house_rule()
    distinto = _house_rule(
        consistency_rule=ConsistencyRule(pct=40.0, semantics=ConsistencySemantics.TERMINATE)
    )
    assert house_rule_hash(base) != house_rule_hash(distinto)


def test_house_rule_hash_cambia_con_daily_loss_limit() -> None:
    base = _house_rule()
    distinto = _house_rule(
        daily_loss_limit=DailyLossLimit(amount=5000.0, semantics=DailyLossLimitSemantics.BREACH)
    )
    assert house_rule_hash(base) != house_rule_hash(distinto)


def test_u4b_house_rule_hash_excluye_funded_starting_balance() -> None:
    """Eval U4b (DH-4): `funded_starting_balance` no mueve `house_rule_hash` (issue #112)."""
    base = _house_rule(funded_starting_balance=0.0)
    distinto = _house_rule(funded_starting_balance=500.0)
    assert house_rule_hash(base) == house_rule_hash(distinto)
