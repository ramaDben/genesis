"""`CandidateBConfig` + `load_candidate_b_config` (T3, R48, R49, R72, R73)."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from genesis.strategy.candidate_b.config import CandidateBConfig, load_candidate_b_config
from genesis.strategy.errors import CandidateBConfigError

pytestmark = pytest.mark.unit


def test_load_candidate_b_config_default_empaquetado() -> None:
    config = load_candidate_b_config()
    assert config == CandidateBConfig(
        n_minutes=15,
        atr_stop_frac=1.0,
        risk_pct=0.00375,
        atr_period=14,
        tp_rr_multiple=3.0,
    )


def test_candidate_b_config_es_frozen() -> None:
    config = load_candidate_b_config()
    with pytest.raises(FrozenInstanceError):
        config.n_minutes = 30  # ty: ignore[invalid-assignment]


def test_load_candidate_b_config_sin_namespace_candidates_b_lanza_error_con_fuente(
    tmp_path: Path,
) -> None:
    payload = {"inspector": {"min_rr": 2.0, "min_lot": 0.01, "max_lot": 50.0}}
    path = tmp_path / "sin_candidates_b.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CandidateBConfigError) as exc_info:
        load_candidate_b_config(path)

    assert str(path) in str(exc_info.value)


def test_load_candidate_b_config_atr_stop_frac_null_es_none(tmp_path: Path) -> None:
    payload = {
        "candidates": {
            "B": {
                "n_minutes": 15,
                "atr_stop_frac": None,
                "risk_pct": 0.00375,
                "atr_period": 14,
                "tp_rr_multiple": 3.0,
            }
        }
    }
    path = tmp_path / "atr_stop_frac_null.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    config = load_candidate_b_config(path)

    assert config.atr_stop_frac is None


def test_load_candidate_b_config_campo_faltante_lanza_error(tmp_path: Path) -> None:
    payload = {"candidates": {"B": {"n_minutes": 15}}}
    path = tmp_path / "incompleto.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CandidateBConfigError):
        load_candidate_b_config(path)
