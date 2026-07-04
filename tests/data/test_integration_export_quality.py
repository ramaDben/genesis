"""Test de integración export → quality (spec §9, R52): en segundos, sin terminal real."""

from datetime import UTC, datetime

import pytest

from genesis.data.mt5_export import Granularity, RawParquetStore, plan_chunks, run_export
from genesis.data.profile import load_firm_profile
from genesis.data.quality import check_quality
from genesis.data.symbols import SymbolSpec
from tests.data.fakes import ACCOUNT_TRADE_MODE_DEMO, FakeMt5Terminal

pytestmark = pytest.mark.integration


def test_export_then_quality_over_fake_terminal(tmp_path) -> None:
    """`run_export` (fake) produce un chunk M1 que `check_quality` evalúa sin errores."""
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    profile = load_firm_profile()
    store = RawParquetStore(tmp_path / "raw")
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    end = datetime(2024, 3, 1, 15, 0, tzinfo=UTC)

    results = run_export(terminal, ["US500"], start, end, profile, store, pause_range=(0.0, 0.0))
    assert len(results) == 1
    resolved_symbol = results[0].resolved_symbol

    window = plan_chunks(start, end, Granularity.M1)[0]
    raw_frame = store.read_chunk(resolved_symbol, Granularity.M1, window)

    symbol_spec = SymbolSpec(symbol=resolved_symbol, figure=results[0].figure, min_full_sessions=1)
    report = check_quality(raw_frame, symbol_spec)

    assert report.row_count == len(raw_frame)
    assert report.symbol == resolved_symbol
    assert report.m1_coverage_window[0] <= report.m1_coverage_window[1]
