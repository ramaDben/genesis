"""Tests unitarios de `genesis.data.profile` (ficha de firma, `HouseRule` embebido)."""

import json
from datetime import time
from pathlib import Path

import pytest

from genesis.data.errors import GenesisDataError
from genesis.data.house_rule import ConsistencySemantics, MaxLossLimitKind
from genesis.data.profile import (
    CONFIG_VERSION,
    FirmProfile,
    SymbolAliases,
    firm_profile_hash,
    load_firm_profile,
)

_PROFILES_DIR = Path("src/genesis/data/profiles")

pytestmark = pytest.mark.unit


def _minimal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "config_version": CONFIG_VERSION,
        "name": "Fixture",
        "daily_reset_time": "00:00:00",
        "daily_reset_tz": "America/New_York",
        "server_tz": "America/New_York",
        "news_bracket_before_minutes": 15,
        "news_bracket_after_minutes": 15,
        "symbols": {
            "US500": {"expected": "US500", "aliases": ["SP500"]},
        },
        "house_rule": None,
    }
    payload.update(overrides)
    return payload


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_firm_profile_returns_conservative_defaults() -> None:
    profile = load_firm_profile()
    assert profile.daily_reset_time == time(0, 0)
    assert profile.daily_reset_tz == "America/New_York"


def test_load_firm_profile_symbol_table_matches_spec() -> None:
    profile = load_firm_profile()
    assert profile.symbols["US500"].expected == "US500"
    assert profile.symbols["NAS100"].expected == "US100"
    assert profile.symbols["US30"].expected == "US30"
    assert profile.symbols["GER40"].expected == "GER40"


def test_firm_profile_hash_is_deterministic() -> None:
    profile = load_firm_profile()
    assert firm_profile_hash(profile) == firm_profile_hash(profile)


def test_firm_profile_hash_differs_for_different_profiles() -> None:
    profile = load_firm_profile()
    other = FirmProfile(
        name="otro nombre",
        daily_reset_time=profile.daily_reset_time,
        daily_reset_tz=profile.daily_reset_tz,
        server_tz=profile.server_tz,
        symbols=profile.symbols,
        news_bracket_before=profile.news_bracket_before,
        news_bracket_after=profile.news_bracket_after,
        house_rule=profile.house_rule,
    )
    assert firm_profile_hash(profile) != firm_profile_hash(other)


def test_load_firm_profile_missing_field_raises_domain_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "broken_profile.json"
    incomplete.write_text('{"name": "The5ers"}', encoding="utf-8")
    with pytest.raises(GenesisDataError, match=r"The5ers|ficha|perfil|profile"):
        load_firm_profile(incomplete)


def test_symbol_aliases_structure() -> None:
    aliases = SymbolAliases(expected="US100", aliases=("NAS100", "USTEC"))
    assert aliases.expected == "US100"
    assert "NAS100" in aliases.aliases


def test_u2_house_rule_sin_daily_loss_limit_es_none(tmp_path: Path) -> None:
    """Eval U2: JSON con `house_rule` sin la clave `daily_loss_limit` -> `None`, sin excepción."""
    payload = _minimal_payload(
        house_rule={
            "max_loss_limit": {"amount": 2000.0, "kind": "trailing_eod"},
            "threshold_lock_at": 52100.0,
            "consistency_rule": None,
            "weekend_holding_allowed": False,
            "payout_buffer": 0.0,
            "min_net_profit_between_payouts": 0.0,
            "funded_starting_balance": 0.0,
            "account_size": 50000.0,
        }
    )
    profile = load_firm_profile(_write(tmp_path, payload))
    assert profile.house_rule is not None
    assert profile.house_rule.daily_loss_limit is None
    assert profile.house_rule.max_loss_limit.kind == MaxLossLimitKind.TRAILING_EOD


def test_u3_config_version_ausente_falla_con_esperado_en_el_mensaje(tmp_path: Path) -> None:
    """Eval U3: ficha sin `config_version` -> `GenesisDataError` citando el valor esperado."""
    payload = _minimal_payload()
    del payload["config_version"]
    with pytest.raises(GenesisDataError, match=CONFIG_VERSION):
        load_firm_profile(_write(tmp_path, payload))


def test_config_version_incorrecto_falla_con_esperado_y_recibido(tmp_path: Path) -> None:
    payload = _minimal_payload(config_version="genesis-data-firm-profile/1")
    with pytest.raises(GenesisDataError, match=CONFIG_VERSION):
        load_firm_profile(_write(tmp_path, payload))


def test_house_rule_null_es_valido_para_una_ficha_que_no_es_prop_firm(tmp_path: Path) -> None:
    payload = _minimal_payload(house_rule=None)
    profile = load_firm_profile(_write(tmp_path, payload))
    assert profile.house_rule is None


def test_house_rule_malformado_lanza_genesis_data_error_con_ficha_y_campo(tmp_path: Path) -> None:
    payload = _minimal_payload(house_rule={"max_loss_limit": {"amount": 2000.0}})
    path = _write(tmp_path, payload)
    with pytest.raises(GenesisDataError, match=r"kind"):
        load_firm_profile(path)


def test_house_rule_ausente_del_json_falla_fail_fast(tmp_path: Path) -> None:
    payload = _minimal_payload()
    del payload["house_rule"]
    with pytest.raises(GenesisDataError, match="house_rule"):
        load_firm_profile(_write(tmp_path, payload))


def test_u1_ficha_mffu_rapid_eod_50k_valores_normativos() -> None:
    """Eval U1 (AC1): la ficha activa MFFU carga los valores normativos de SSoT §1.3.0."""
    profile = load_firm_profile(_PROFILES_DIR / "mffu_rapid_eod_50k.json")
    assert profile.house_rule is not None
    house_rule = profile.house_rule
    assert house_rule.max_loss_limit.amount == 2000.0
    assert house_rule.max_loss_limit.kind == MaxLossLimitKind.TRAILING_EOD
    assert house_rule.threshold_lock_at == 52100.0
    assert house_rule.daily_loss_limit is None
    assert house_rule.consistency_rule is not None
    assert house_rule.consistency_rule.pct == 30.0
    assert house_rule.consistency_rule.semantics == ConsistencySemantics.TERMINATE
    assert house_rule.payout_buffer == 2100.0
    assert house_rule.min_net_profit_between_payouts == 500.0
    assert house_rule.account_size == 50000.0


def test_u13_ficha_the5ers_migrada_a_house_rule() -> None:
    """Eval U13: `the5ers.json` migrado conserva sus tres valores exactos (D3)."""
    profile = load_firm_profile(_PROFILES_DIR / "the5ers.json")
    assert profile.house_rule is not None
    house_rule = profile.house_rule
    assert house_rule.account_size == 100000.0
    assert house_rule.max_loss_limit.amount == 10000.0
    assert house_rule.max_loss_limit.kind == MaxLossLimitKind.STATIC
    assert house_rule.daily_loss_limit is not None
    assert house_rule.daily_loss_limit.amount == 5000.0
    assert house_rule.threshold_lock_at is None


def test_u14_ficha_binance_futures_no_es_prop_firm() -> None:
    """Eval U14: `binance_futures.json` no declara contrato de casa, y sin números inventados."""
    profile = load_firm_profile(_PROFILES_DIR / "binance_futures.json")
    assert profile.house_rule is None
    raw = (_PROFILES_DIR / "binance_futures.json").read_text(encoding="utf-8")
    assert "daily_loss_limit" not in raw
    assert "max_loss_limit" not in raw
    assert "account_size" not in raw
