"""Golden test del `SignalDiagnosticReport`: determinismo byte a byte (T5.4, R120, R124)."""

from pathlib import Path

import pandas as pd
import pytest

from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import load_firm_profile
from genesis.strategy.candidate_a.config import CandidateAConfig, DiagnosticsConfig, SmcEngineConfig
from genesis.validation.signal_diagnostic import (
    render_signal_diagnostic_markdown,
    run_signal_diagnostic,
    signal_diagnostic_report_to_json,
)
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "signal_diagnostic_report_golden.json"
_FIXED_GIT_COMMIT = "deadbeef" * 5  # 40 caracteres hex, mismo patrón que test_verdict.py


def _config() -> CandidateAConfig:
    return CandidateAConfig(
        smc=SmcEngineConfig(
            fractal_n=1,
            eq_tolerance_atr=0.15,
            sweep_tolerance_atr=0.05,
            sweep_window_k=3,
            sweep_validity_m=5,
            free_path_radius_sigma=1.0,
            ct_zscore_min=2.0,
            atr_period=3,
        ),
        diagnostics=DiagnosticsConfig(
            horizons_minutes=(5, 15),
            bootstrap_resamples=100,
            bootstrap_block_size=None,
            bootstrap_seed=1,
            stop_distance_atr_buffer_multiple=1.0,
        ),
    )


def _frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02 10:00:00", periods=20, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 20,
            "high": [100.2] * 20,
            "low": [99.8] * 20,
            "close": [100.0] * 20,
            "tick_volume": [10] * 20,
        }
    )


def _run(tmp_path: Path) -> str:
    profile = load_firm_profile()
    config = _config()
    frame = _frame()
    store = RawParquetStore(tmp_path)
    figure = _default_symbol_figure(_SYMBOL)

    report = run_signal_diagnostic(
        store,
        frame,
        _SYMBOL,
        "test_session",
        profile,
        config,
        figure,
        symbol_figure_is_placeholder=False,
        git_commit=_FIXED_GIT_COMMIT,
    )
    return signal_diagnostic_report_to_json(report)


def test_dos_ejecuciones_producen_json_byte_a_byte_identico(tmp_path: Path) -> None:
    json_a = _run(tmp_path / "run_a")
    json_b = _run(tmp_path / "run_b")
    assert json_a == json_b


def test_json_coincide_con_el_golden_versionado(tmp_path: Path) -> None:
    produced = _run(tmp_path)
    expected = _FIXTURE_PATH.read_text(encoding="utf-8")
    assert produced == expected.strip()


def test_render_markdown_es_puro_y_reproducible(tmp_path: Path) -> None:
    profile = load_firm_profile()
    config = _config()
    frame = _frame()
    store = RawParquetStore(tmp_path)
    figure = _default_symbol_figure(_SYMBOL)

    report = run_signal_diagnostic(
        store,
        frame,
        _SYMBOL,
        "test_session",
        profile,
        config,
        figure,
        symbol_figure_is_placeholder=False,
        git_commit=_FIXED_GIT_COMMIT,
    )
    markdown_a = render_signal_diagnostic_markdown(report)
    markdown_b = render_signal_diagnostic_markdown(report)
    assert markdown_a == markdown_b
    assert _SYMBOL in markdown_a
    assert report.verdict.value.upper() in markdown_a
