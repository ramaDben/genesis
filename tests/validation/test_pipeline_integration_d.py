"""Integración end-to-end del pipeline `iter_bars -> smc_engine -> diagnostics ->
signal_diagnostic` (T6.2, R126): un símbolo del universo de índices (`SessionSpec`
existente) y, con `--allow-placeholder-figures`, un símbolo de oro/majors
(`FixedUtcWindowSpec`). Reutiliza `tests/strategy/fixtures/sample_m1.csv` (patrón de
los golden tests de `candidate_b`).
"""

import time
from pathlib import Path

import pandas as pd
import pytest

from genesis.data.profile import load_firm_profile
from genesis.data.store import RawParquetStore
from genesis.strategy.candidate_a.config import (
    CandidateAConfig,
    DiagnosticsConfig,
    SmcEngineConfig,
    load_placeholder_symbol_figures,
)
from genesis.validation.signal_diagnostic import ArchiveOrContinue, run_signal_diagnostic
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.integration

_FIXTURE_PATH = Path(__file__).parents[1] / "strategy" / "fixtures" / "sample_m1.csv"


def _config() -> CandidateAConfig:
    return CandidateAConfig(
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
            bootstrap_resamples=200,
            bootstrap_block_size=None,
            bootstrap_seed=12345,
            stop_distance_atr_buffer_multiple=1.0,
        ),
    )


def _load_frame() -> pd.DataFrame:
    frame = pd.read_csv(_FIXTURE_PATH)
    frame = frame.rename(columns={"time": "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    # `_to_utc` reinterpreta como hora local del servidor: se elimina el tzinfo 'Z'
    # (ya UTC) para que la conversión de `iter_bars` sea la identidad (server_tz del
    # perfil de firma se usa igual, sin desplazamiento adicional relevante para esta
    # prueba de humo de integración).
    frame["timestamp"] = frame["timestamp"].dt.tz_localize(None)
    # Recorte a las primeras horas del primer día (2024-03-09): evita cruzar la
    # transición de DST de EE. UU. (2024-03-10), fuera de alcance de esta prueba de
    # integración (smoke test del pipeline, no del comportamiento DST de `sessions.py`).
    return frame.iloc[:600].reset_index(drop=True)


@pytest.mark.timeout(30)
def test_pipeline_completo_para_indice_y_para_simbolo_placeholder(tmp_path: Path) -> None:
    profile = load_firm_profile()
    config = _config()
    frame = _load_frame()
    store = RawParquetStore(tmp_path)

    started = time.monotonic()

    # (a) al menos un índice del universo existente (SessionSpec, US500).
    index_figure = _default_symbol_figure("US500")
    index_report = run_signal_diagnostic(
        store,
        frame,
        "US500",
        "us_index_session",
        profile,
        config,
        index_figure,
        symbol_figure_is_placeholder=False,
        git_commit="integration-test",
    )
    assert index_report.symbol == "US500"
    assert index_report.symbol_figure_is_placeholder is False
    assert index_report.verdict in (ArchiveOrContinue.ARCHIVE, ArchiveOrContinue.CONTINUE)

    # (b) con --allow-placeholder-figures, al menos uno de XAUUSD/EURUSD/GBPUSD/USDJPY.
    placeholders = load_placeholder_symbol_figures()
    gold_figure = placeholders["XAUUSD"]
    gold_report = run_signal_diagnostic(
        store,
        frame,
        "XAUUSD",
        "london_ny_overlap",
        profile,
        config,
        gold_figure,
        symbol_figure_is_placeholder=True,
        git_commit="integration-test",
    )
    assert gold_report.symbol == "XAUUSD"
    assert gold_report.symbol_figure_is_placeholder is True
    assert gold_report.verdict in (ArchiveOrContinue.ARCHIVE, ArchiveOrContinue.CONTINUE)

    elapsed = time.monotonic() - started
    assert elapsed < 20.0  # "en segundos, no minutos" (spec eval 9)
