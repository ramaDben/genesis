"""Tests unitarios de `genesis.data.quality` (contrato de calidad fail-fast)."""

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from genesis.data.errors import GenesisDataError
from genesis.data.quality import QualityError, check_quality
from genesis.data.symbols import SymbolSpec

pytestmark = pytest.mark.unit


def _m1_frame(start: datetime, n_bars: int, *, gap_after: int | None = None) -> pd.DataFrame:
    """Construye un mini-frame M1 sintético sin gaps, salvo el que indique `gap_after`."""
    timestamps = []
    current = start
    for i in range(n_bars):
        timestamps.append(current)
        step = timedelta(minutes=2) if gap_after == i else timedelta(minutes=1)
        current = current + step
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * n_bars,
            "high": [101.0] * n_bars,
            "low": [99.0] * n_bars,
            "close": [100.5] * n_bars,
            "tick_volume": [10] * n_bars,
        }
    )


def _spec(min_full_sessions: int = 1) -> SymbolSpec:
    return SymbolSpec(symbol="US500", figure=None, min_full_sessions=min_full_sessions)


def test_check_quality_no_anomalies_on_clean_frame() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 10)
    report = check_quality(frame, _spec())
    assert report.gaps == []
    assert report.duplicates_count == 0
    assert report.corrupt_bars_count == 0


def test_check_quality_detects_gap() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 10, gap_after=3)
    report = check_quality(frame, _spec())
    assert len(report.gaps) == 1
    assert report.gaps[0].missing_bars >= 1


def test_check_quality_detects_duplicates() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 5)
    duplicated_row = frame.iloc[[2]]
    frame_with_dup = pd.concat([frame, duplicated_row], ignore_index=True)
    report = check_quality(frame_with_dup, _spec())
    assert report.duplicates_count == 1


def test_check_quality_detects_corrupt_bars_low_greater_than_high() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 3)
    frame.loc[1, "low"] = 200.0  # low > high, vela corrupta
    report = check_quality(frame, _spec())
    assert report.corrupt_bars_count == 1


def test_check_quality_detects_corrupt_bars_close_out_of_range() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 3)
    frame.loc[1, "close"] = 500.0  # close fuera de [low, high]
    report = check_quality(frame, _spec())
    assert report.corrupt_bars_count == 1


def test_check_quality_no_anomaly_left_out_of_report_silently() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 5, gap_after=2)
    frame.loc[4, "low"] = 999.0
    duplicated_row = frame.iloc[[0]]
    frame_full = pd.concat([frame, duplicated_row], ignore_index=True)
    report = check_quality(frame_full, _spec())
    assert len(report.gaps) == 1
    assert report.corrupt_bars_count == 1
    assert report.duplicates_count == 1


def test_check_quality_m1_coverage_window() -> None:
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    frame = _m1_frame(start, 10)
    report = check_quality(frame, _spec())
    assert report.m1_coverage_window == (date(2024, 3, 1), date(2024, 3, 1))


def test_check_quality_ticks_coverage_window_when_kind_ticks() -> None:
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    frame = pd.DataFrame(
        {
            "timestamp": [start, start + timedelta(seconds=1), start + timedelta(seconds=2)],
            "bid": [100.0, 100.1, 100.2],
            "ask": [100.1, 100.2, 100.3],
        }
    )
    report = check_quality(frame, _spec(), kind="ticks")
    assert report.ticks_coverage_window == (date(2024, 3, 1), date(2024, 3, 1))


def test_check_quality_ticks_coverage_window_none_for_m1() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 5)
    report = check_quality(frame, _spec())
    assert report.ticks_coverage_window is None


def test_check_quality_sufficiency_verdict_true_when_enough_sessions() -> None:
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    frames = [_m1_frame(start + timedelta(days=d), 5) for d in range(3)]
    frame = pd.concat(frames, ignore_index=True)
    report = check_quality(frame, _spec(min_full_sessions=2))
    assert report.sufficiency_verdict is True
    assert report.sufficiency_reason


def test_check_quality_sufficiency_verdict_false_when_history_insufficient() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 5)
    report = check_quality(frame, _spec(min_full_sessions=100))
    assert report.sufficiency_verdict is False
    assert report.sufficiency_reason != ""
    assert report.row_count == len(frame)


def test_check_quality_never_interpolates_row_count_matches_input() -> None:
    frame = _m1_frame(datetime(2024, 3, 1, 14, 30, tzinfo=UTC), 7, gap_after=3)
    report = check_quality(frame, _spec())
    assert report.row_count == len(frame)


def test_check_quality_docstring_clarifies_not_g1() -> None:
    assert check_quality.__doc__ is not None
    doc_lower = check_quality.__doc__.lower()
    assert "g1" in doc_lower


def test_check_quality_empty_frame_raises_quality_error() -> None:
    with pytest.raises(QualityError):
        check_quality(pd.DataFrame(), _spec())


def test_check_quality_missing_ohlc_columns_raises_quality_error() -> None:
    frame = pd.DataFrame({"timestamp": [datetime(2024, 3, 1, tzinfo=UTC)]})
    with pytest.raises(QualityError):
        check_quality(frame, _spec())


def test_quality_error_is_a_genesis_data_error() -> None:
    assert issubclass(QualityError, GenesisDataError)
