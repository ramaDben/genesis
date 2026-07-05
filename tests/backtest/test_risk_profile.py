"""Tests de la ficha propia de riesgo `RiskProfile` (R10–R14)."""

import dataclasses
import json
from pathlib import Path

import pytest

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.risk_profile import (
    MaxLossLimitKind,
    RiskProfile,
    load_risk_profile,
    risk_profile_hash,
)

pytestmark = pytest.mark.unit


def test_max_loss_limit_kind_tiene_los_dos_valores_normativos() -> None:
    assert MaxLossLimitKind.STATIC == "static"
    assert MaxLossLimitKind.TRAILING == "trailing"


def test_risk_profile_es_frozen() -> None:
    profile = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.max_loss_limit_pct = 5.0  # type: ignore[misc]


def test_load_risk_profile_default_empaquetado() -> None:
    profile = load_risk_profile()
    assert profile.max_loss_limit_pct == 10.0
    assert profile.max_loss_limit_kind == MaxLossLimitKind.STATIC
    assert profile.weekend_holding_allowed is True


def test_load_risk_profile_config_incompleta_lanza_backtest_config_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "risk_profile.json"
    incomplete.write_text(
        json.dumps({"max_loss_limit_kind": "static", "weekend_holding_allowed": True}),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError) as excinfo:
        load_risk_profile(incomplete)
    assert "max_loss_limit_pct" in str(excinfo.value)


def test_risk_profile_hash_es_determinista() -> None:
    profile = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
    )
    assert risk_profile_hash(profile) == risk_profile_hash(profile)


def test_risk_profile_hash_cambia_con_el_contenido() -> None:
    base = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
    )
    distinto = RiskProfile(
        max_loss_limit_pct=8.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
    )
    assert risk_profile_hash(base) != risk_profile_hash(distinto)
