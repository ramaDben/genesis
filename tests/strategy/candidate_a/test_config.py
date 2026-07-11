"""`CandidateAConfig`, `load_candidate_a_config`, `load_placeholder_symbol_figures` (T2.3/T2.4)."""

import json
from pathlib import Path

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_a.config import (
    CandidateAConfig,
    DiagnosticsConfig,
    SmcEngineConfig,
    load_candidate_a_config,
    load_placeholder_symbol_figures,
)
from genesis.strategy.candidate_a.errors import CandidateAConfigError

pytestmark = pytest.mark.unit


def test_load_candidate_a_config_default_empaquetado() -> None:
    config = load_candidate_a_config()
    assert config == CandidateAConfig(
        smc=SmcEngineConfig(
            fractal_n=3,
            eq_tolerance_atr=0.15,
            sweep_tolerance_atr=0.05,
            sweep_window_k=5,
            sweep_validity_m=30,
            free_path_radius_sigma=1.0,
            ct_zscore_min=2.0,
            atr_period=14,
        ),
        diagnostics=DiagnosticsConfig(
            horizons_minutes=(5, 15, 30, 60),
            bootstrap_resamples=2000,
            bootstrap_block_size=None,
            bootstrap_seed=12345,
            stop_distance_atr_buffer_multiple=1.0,
        ),
    )


def test_load_candidate_a_config_sin_namespace_candidates_a_lanza_error_con_fuente(
    tmp_path: Path,
) -> None:
    payload = {"candidates": {"B": {"n_minutes": 15}}}
    path = tmp_path / "sin_candidates_a.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CandidateAConfigError) as exc_info:
        load_candidate_a_config(path)
    assert str(path) in str(exc_info.value)


def test_load_candidate_a_config_bloque_smc_incompleto_lanza_error(tmp_path: Path) -> None:
    payload = {
        "candidates": {
            "A": {
                "smc": {"fractal_n": 3},
                "diagnostics": {
                    "horizons_minutes": [5, 15, 30, 60],
                    "bootstrap_resamples": 2000,
                    "bootstrap_block_size": None,
                    "bootstrap_seed": 12345,
                    "stop_distance_atr_buffer_multiple": 1.0,
                },
            }
        }
    }
    path = tmp_path / "smc_incompleto.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CandidateAConfigError):
        load_candidate_a_config(path)


def test_load_candidate_a_config_json_corrupto_lanza_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupto.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CandidateAConfigError):
        load_candidate_a_config(path)


def test_load_placeholder_symbol_figures_default_empaquetado() -> None:
    figures = load_placeholder_symbol_figures()
    assert set(figures.keys()) == {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY"}
    for symbol, figure in figures.items():
        assert isinstance(figure, SymbolFigure)
        assert figure.symbol == symbol


def test_load_placeholder_symbol_figures_bloque_faltante_lanza_error(tmp_path: Path) -> None:
    payload = {
        "candidates": {
            "A": {
                "smc": {
                    "fractal_n": 3,
                    "eq_tolerance_atr": 0.15,
                    "sweep_tolerance_atr": 0.05,
                    "sweep_window_k": 5,
                    "sweep_validity_m": 30,
                    "free_path_radius_sigma": 1.0,
                    "ct_zscore_min": 2.0,
                    "atr_period": 14,
                },
                "diagnostics": {
                    "horizons_minutes": [5, 15, 30, 60],
                    "bootstrap_resamples": 2000,
                    "bootstrap_block_size": None,
                    "bootstrap_seed": 12345,
                    "stop_distance_atr_buffer_multiple": 1.0,
                },
            }
        }
    }
    path = tmp_path / "sin_placeholders.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CandidateAConfigError):
        load_placeholder_symbol_figures(path)
