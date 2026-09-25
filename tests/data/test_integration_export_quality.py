"""Test de integración store → quality: en segundos, sin terminal real."""

from datetime import UTC, datetime

import pytest

from genesis.data.metadata import ArtifactMetadata, current_git_commit
from genesis.data.quality import check_quality
from genesis.data.store import Granularity, RawParquetStore, plan_chunks
from genesis.data.symbols import SymbolSpec
from tests.data.fakes import _default_symbol_figure, _deterministic_m1_frame

pytestmark = pytest.mark.integration


def test_export_then_quality_over_fake_terminal(tmp_path) -> None:
    """Store produce un chunk M1 que `check_quality` evalúa sin errores."""
    symbol = "US500"
    store = RawParquetStore(tmp_path / "raw")
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    end = datetime(2024, 3, 1, 15, 0, tzinfo=UTC)

    window = plan_chunks(start, end, Granularity.M1)[0]
    frame = _deterministic_m1_frame(symbol, start, end)
    metadata = ArtifactMetadata(
        config_version="genesis-data-raw-store/1",
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash="fake",
        time_range=(start, end),
        git_commit=current_git_commit(),
        symbol_figure=_default_symbol_figure(symbol),
    )
    store.write_chunk(frame, symbol, Granularity.M1, window, metadata)

    raw_frame = store.read_chunk(symbol, Granularity.M1, window)
    figure = _default_symbol_figure(symbol)
    symbol_spec = SymbolSpec(symbol=symbol, figure=figure, min_full_sessions=1)
    report = check_quality(raw_frame, symbol_spec)

    assert report.row_count == len(raw_frame)
    assert report.symbol == symbol
    assert report.m1_coverage_window[0] <= report.m1_coverage_window[1]
