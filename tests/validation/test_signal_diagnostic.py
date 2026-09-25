"""`signal_diagnostic.py`: coste round-trip de ticks + informe compuesto (T5.2/T5.3)."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.ticks import _day_window
from genesis.data.metadata import ArtifactMetadata
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import Granularity, RawParquetStore
from genesis.strategy.candidate_a.config import CandidateAConfig, DiagnosticsConfig, SmcEngineConfig
from genesis.strategy.candidate_a.diagnostics import ConditionalReturnEvent
from genesis.strategy.contract import Direction
from genesis.validation.signal_diagnostic import estimate_roundtrip_cost, run_signal_diagnostic
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_TRADING_DAY = date(2024, 1, 2)


def _utc_profile() -> FirmProfile:
    """Ficha de firma con `server_tz="UTC"` (R71/R83): regresión, mismos valores pre-fix."""
    return replace(load_firm_profile(), server_tz="UTC")


def _write_tick_chunk(
    store: RawParquetStore, symbol: str, trading_day: date, frame: pd.DataFrame
) -> None:
    window = _day_window(trading_day)
    metadata = ArtifactMetadata(
        config_version="test",
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash="test",
        time_range=(window.start, window.end),
        git_commit="test",
    )
    store.write_chunk(frame, symbol, Granularity.TICK, window, metadata)


def _event(event_time: datetime, entry_price: float = 100.0) -> ConditionalReturnEvent:
    return ConditionalReturnEvent(
        symbol=_SYMBOL,
        session_label="test",
        event_time=event_time,
        trading_day=_TRADING_DAY,
        expected_reversion=Direction.LONG,
        entry_price=entry_price,
        stop_distance=1.0,
        vwap_at_event=99.5,
    )


def test_estimate_roundtrip_cost_evento_sin_ticks_es_excluido(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    event = _event(datetime(2024, 1, 2, 14, 31, tzinfo=UTC))

    cost, excluded = estimate_roundtrip_cost(store, _SYMBOL, [event], _utc_profile())

    assert excluded == 1
    assert cost == 0.0


def test_estimate_roundtrip_cost_con_cobertura_calcula_spread_relativo(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([datetime(2024, 1, 2, 14, 30, 30, tzinfo=UTC)], utc=True),
            "bid": [99.9],
            "ask": [100.1],
            "last": [100.0],
        }
    )
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, frame)
    event = _event(datetime(2024, 1, 2, 14, 31, tzinfo=UTC), entry_price=100.0)

    cost, excluded = estimate_roundtrip_cost(store, _SYMBOL, [event], _utc_profile())

    assert excluded == 0
    assert cost == pytest.approx(0.2 / 100.0)


def test_run_signal_diagnostic_compone_artifact_metadata(tmp_path: Path) -> None:
    profile = load_firm_profile()
    config = CandidateAConfig(
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
    # NY_local = UTC - 5h en enero (EST): naive "10:00" -> UTC 15:00.
    timestamps = pd.date_range("2024-01-02 10:00:00", periods=20, freq="min")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 20,
            "high": [100.2] * 20,
            "low": [99.8] * 20,
            "close": [100.0] * 20,
            "tick_volume": [10] * 20,
        }
    )
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
    )

    assert isinstance(report.data_metadata, ArtifactMetadata)
    assert report.data_metadata.dataset_hash == store.chunk_hash(frame)
    assert report.data_metadata.symbol_figure == figure
    assert report.candidate_id == "A"
    assert report.symbol == _SYMBOL
    assert report.symbol_figure_is_placeholder is False
