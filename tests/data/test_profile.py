"""Tests unitarios de `genesis.data.profile` (ficha de firma The5ers, defaults conservadores)."""

from datetime import time

import pytest

from genesis.data.errors import GenesisDataError
from genesis.data.profile import FirmProfile, SymbolAliases, firm_profile_hash, load_firm_profile

pytestmark = pytest.mark.unit


def test_load_firm_profile_returns_conservative_defaults() -> None:
    profile = load_firm_profile()
    assert profile.daily_reset_time == time(0, 0)
    assert profile.daily_reset_tz == "America/New_York"
    assert profile.daily_loss_limit_pct == 5.0


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
        name=profile.name,
        daily_reset_time=profile.daily_reset_time,
        daily_reset_tz=profile.daily_reset_tz,
        daily_loss_limit_pct=99.0,
        server_tz=profile.server_tz,
        symbols=profile.symbols,
        news_bracket_before=profile.news_bracket_before,
        news_bracket_after=profile.news_bracket_after,
    )
    assert firm_profile_hash(profile) != firm_profile_hash(other)


def test_load_firm_profile_missing_field_raises_domain_error(tmp_path) -> None:
    incomplete = tmp_path / "broken_profile.json"
    incomplete.write_text('{"name": "The5ers"}', encoding="utf-8")
    with pytest.raises(GenesisDataError, match=r"The5ers|ficha|perfil|profile"):
        load_firm_profile(incomplete)


def test_symbol_aliases_structure() -> None:
    aliases = SymbolAliases(expected="US100", aliases=("NAS100", "USTEC"))
    assert aliases.expected == "US100"
    assert "NAS100" in aliases.aliases
