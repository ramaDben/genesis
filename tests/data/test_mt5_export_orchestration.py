"""Tests unitarios de la orquestación de `genesis.data.mt5_export` (guard, cache, export)."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from genesis.data.mt5_export import (
    AccountScopeError,
    Granularity,
    RawParquetStore,
    assert_demo_account,
    run_export,
)
from genesis.data.profile import load_firm_profile
from tests.data.fakes import ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL, FakeMt5Terminal

pytestmark = pytest.mark.unit


# --- assert_demo_account / guard de cuenta (R3, R50) --------------------------------


def test_assert_demo_account_passes_for_demo_terminal() -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    assert_demo_account(terminal)  # no debe lanzar


def test_assert_demo_account_raises_for_real_terminal() -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_REAL)
    with pytest.raises(AccountScopeError):
        assert_demo_account(terminal)


def test_run_export_non_demo_account_aborts_before_any_download(tmp_path) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_REAL, available_symbols=["US500"])
    profile = load_firm_profile()
    store = RawParquetStore(tmp_path / "raw")
    with pytest.raises(AccountScopeError):
        run_export(
            terminal,
            ["US500"],
            datetime(2024, 3, 1, tzinfo=UTC),
            datetime(2024, 3, 2, tzinfo=UTC),
            profile,
            store,
        )
    assert terminal.copy_rates_range_calls == 0
    assert terminal.copy_ticks_range_calls == 0


# --- RawParquetStore: cache-first + determinismo (R7, R8, R36) ----------------------


def _sample_m1_frame() -> pd.DataFrame:
    start = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start, periods=5, freq="1min", tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "tick_volume": [10] * 5,
        }
    )


def test_raw_parquet_store_write_and_read_round_trip(tmp_path) -> None:
    from genesis.data.metadata import CONFIG_VERSION, ArtifactMetadata, sha256_of
    from genesis.data.mt5_export import ChunkWindow

    store = RawParquetStore(tmp_path / "raw")
    frame = _sample_m1_frame()
    window = ChunkWindow(start=frame["timestamp"].iloc[0], end=frame["timestamp"].iloc[-1])
    metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash=sha256_of(b"profile"),
        time_range=(window.start, window.end),
        git_commit="deadbeef",
    )
    path = store.write_chunk(frame, "US500", Granularity.M1, window, metadata)
    assert path.exists()
    assert store.has_chunk("US500", Granularity.M1, window)
    restored = store.read_chunk("US500", Granularity.M1, window)
    pd.testing.assert_frame_equal(
        restored.reset_index(drop=True), frame.reset_index(drop=True), check_dtype=False
    )


def test_raw_parquet_store_two_writes_produce_bit_identical_files(tmp_path) -> None:
    from genesis.data.metadata import CONFIG_VERSION, ArtifactMetadata, sha256_of
    from genesis.data.mt5_export import ChunkWindow

    frame = _sample_m1_frame()
    window = ChunkWindow(start=frame["timestamp"].iloc[0], end=frame["timestamp"].iloc[-1])

    store_a = RawParquetStore(tmp_path / "raw_a")
    store_b = RawParquetStore(tmp_path / "raw_b")
    metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=store_a.chunk_hash(frame),
        firm_profile_hash=sha256_of(b"profile"),
        time_range=(window.start, window.end),
        git_commit="deadbeef",
    )
    path_a = store_a.write_chunk(frame.copy(), "US500", Granularity.M1, window, metadata)
    path_b = store_b.write_chunk(frame.copy(), "US500", Granularity.M1, window, metadata)
    assert sha256_of(path_a.read_bytes()) == sha256_of(path_b.read_bytes())


def test_raw_parquet_store_chunk_hash_is_deterministic(tmp_path) -> None:
    store = RawParquetStore(tmp_path / "raw")
    frame = _sample_m1_frame()
    assert store.chunk_hash(frame) == store.chunk_hash(frame.copy())


# --- run_export end-to-end sobre fake (R4, R10, R37, R38, R39) ----------------------


def test_run_export_writes_chunks_and_captures_symbol_figure(tmp_path) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    profile = load_firm_profile()
    store = RawParquetStore(tmp_path / "raw")
    results = run_export(
        terminal,
        ["US500"],
        datetime(2024, 3, 1, tzinfo=UTC),
        datetime(2024, 3, 1, 0, 5, tzinfo=UTC),
        profile,
        store,
        pause_range=(0.0, 0.0),
    )
    assert len(results) == 1
    result = results[0]
    assert result.symbol == "US500"
    assert result.resolved_symbol == "US500"
    assert result.figure.symbol == "US500"
    assert result.chunks_written >= 1


def test_run_export_is_cache_first_on_second_run(tmp_path) -> None:
    profile = load_firm_profile()
    store = RawParquetStore(tmp_path / "raw")
    start = datetime(2024, 3, 1, tzinfo=UTC)
    end = datetime(2024, 3, 1, 0, 5, tzinfo=UTC)

    terminal_1 = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    run_export(terminal_1, ["US500"], start, end, profile, store, pause_range=(0.0, 0.0))
    assert terminal_1.copy_rates_range_calls >= 1

    terminal_2 = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    results_2 = run_export(
        terminal_2, ["US500"], start, end, profile, store, pause_range=(0.0, 0.0)
    )
    assert terminal_2.copy_rates_range_calls == 0
    assert results_2[0].chunks_cached >= 1


def test_run_export_resolves_symbol_alias_before_download(tmp_path) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["NAS100"])
    profile = load_firm_profile()
    store = RawParquetStore(tmp_path / "raw")
    results = run_export(
        terminal,
        ["NAS100"],
        datetime(2024, 3, 1, tzinfo=UTC),
        datetime(2024, 3, 1, 0, 5, tzinfo=UTC),
        profile,
        store,
        pause_range=(0.0, 0.0),
    )
    # NAS100 -> esperado US100 (no presente) -> cae al alias NAS100 (presente).
    assert results[0].resolved_symbol == "NAS100"
