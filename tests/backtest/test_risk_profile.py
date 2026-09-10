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
        setattr(profile, "max_loss_limit_pct", 5.0)  # noqa: B010


def test_load_risk_profile_default_empaquetado() -> None:
    profile = load_risk_profile()
    assert profile.max_loss_limit_pct == 10.0
    assert profile.max_loss_limit_kind == MaxLossLimitKind.STATIC
    assert profile.weekend_holding_allowed is True
    assert profile.trailing_lookback == 22
    assert profile.trailing_atr_mult == 3.0


def test_load_risk_profile_config_incompleta_lanza_backtest_config_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "risk_profile.json"
    incomplete.write_text(
        json.dumps({"max_loss_limit_kind": "static", "weekend_holding_allowed": True}),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError) as excinfo:
        load_risk_profile(incomplete)
    assert "max_loss_limit_pct" in str(excinfo.value)


def test_load_risk_profile_falta_trailing_lanza_backtest_config_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "risk_profile.json"
    incomplete.write_text(
        json.dumps({
            "max_loss_limit_pct": 10.0,
            "max_loss_limit_kind": "static",
            "weekend_holding_allowed": True,
            "trailing_lookback": 22,
        }),
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError) as excinfo:
        load_risk_profile(incomplete)
    assert "trailing_atr_mult" in str(excinfo.value)


def test_risk_profile_validacion_parametros_trailing() -> None:
    with pytest.raises(BacktestConfigError, match="trailing_lookback"):
        RiskProfile(
            max_loss_limit_pct=10.0,
            max_loss_limit_kind=MaxLossLimitKind.STATIC,
            weekend_holding_allowed=True,
            trailing_lookback=0,
            trailing_atr_mult=3.0,
        )

    with pytest.raises(BacktestConfigError, match="trailing_atr_mult"):
        RiskProfile(
            max_loss_limit_pct=10.0,
            max_loss_limit_kind=MaxLossLimitKind.STATIC,
            weekend_holding_allowed=True,
            trailing_lookback=22,
            trailing_atr_mult=0.0,
        )


def test_risk_profile_hash_es_determinista() -> None:
    profile = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.0,
    )
    assert risk_profile_hash(profile) == risk_profile_hash(profile)


def test_risk_profile_hash_cambia_con_el_contenido() -> None:
    base = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.0,
    )
    distinto = RiskProfile(
        max_loss_limit_pct=8.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.0,
    )
    assert risk_profile_hash(base) != risk_profile_hash(distinto)


def test_risk_profile_hash_criterio_a23_sensibilidad_trailing() -> None:
    """Criterio A23: Sensibilidad del hash canónico (R14).

    Modificar trailing_lookback (22 -> 23) o trailing_atr_mult (3.0 -> 3.5) altera
    risk_profile_hash(profile), mientras que perfiles idénticos producen el mismo hash.
    """
    base = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.0,
    )
    cambio_lookback = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=23,
        trailing_atr_mult=3.0,
    )
    cambio_mult = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.5,
    )
    identico = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=True,
        trailing_lookback=22,
        trailing_atr_mult=3.0,
    )

    assert risk_profile_hash(base) != risk_profile_hash(cambio_lookback)
    assert risk_profile_hash(base) != risk_profile_hash(cambio_mult)
    assert risk_profile_hash(cambio_lookback) != risk_profile_hash(cambio_mult)
    assert risk_profile_hash(base) == risk_profile_hash(identico)
