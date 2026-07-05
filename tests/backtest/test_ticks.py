"""Tests del lector de ticks forward-only `iter_ticks` (R15–R19, ADR-G6/G8)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import _day_window, has_sufficient_tick_coverage, iter_ticks
from genesis.data.metadata import ArtifactMetadata
from genesis.data.mt5_export import Granularity, RawParquetStore
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_TRADING_DAY = date(2024, 1, 2)


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


def test_iter_ticks_sin_chunk_persistido_retorna_secuencia_vacia_sin_excepcion(
    tmp_path: Path,
) -> None:
    store = RawParquetStore(tmp_path)
    assert list(iter_ticks(store, _SYMBOL, _TRADING_DAY)) == []


def test_iter_ticks_con_esquema_invalido_lanza_backtest_config_error(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([datetime(2024, 1, 2, 14, 30, 30, tzinfo=UTC)], utc=True),
            "ask": [100.1],
            "last": [100.05],
        }
    )
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, frame)
    with pytest.raises(BacktestConfigError):
        list(iter_ticks(store, _SYMBOL, _TRADING_DAY))


def test_iter_ticks_emite_filas_ordenadas_por_timestamp_ascendente(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    datetime(2024, 1, 2, 14, 30, 40, tzinfo=UTC),
                    datetime(2024, 1, 2, 14, 30, 10, tzinfo=UTC),
                ],
                utc=True,
            ),
            "bid": [100.0, 99.9],
            "ask": [100.1, 100.0],
            "last": [100.05, 99.95],
        }
    )
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, frame)
    ticks = list(iter_ticks(store, _SYMBOL, _TRADING_DAY))
    assert [tick.timestamp_utc for tick in ticks] == [
        datetime(2024, 1, 2, 14, 30, 10, tzinfo=UTC),
        datetime(2024, 1, 2, 14, 30, 40, tzinfo=UTC),
    ]


def test_has_sufficient_tick_coverage_cobertura_parcial_intradia(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([datetime(2024, 1, 2, 14, 30, 30, tzinfo=UTC)], utc=True),
            "bid": [100.0],
            "ask": [100.1],
            "last": [100.05],
        }
    )
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, frame)
    day_ticks = list(iter_ticks(store, _SYMBOL, _TRADING_DAY))

    bar_con_cobertura = make_annotated_bar(
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC), trading_day=_TRADING_DAY
    )
    bar_sin_cobertura = make_annotated_bar(
        datetime(2024, 1, 2, 14, 40, tzinfo=UTC), trading_day=_TRADING_DAY
    )

    assert has_sufficient_tick_coverage(store, _SYMBOL, bar_con_cobertura, day_ticks) is True
    assert has_sufficient_tick_coverage(store, _SYMBOL, bar_sin_cobertura, day_ticks) is False


def test_has_sufficient_tick_coverage_sin_chunk_es_false(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    bar = make_annotated_bar(datetime(2024, 1, 2, 14, 31, tzinfo=UTC), trading_day=_TRADING_DAY)
    assert has_sufficient_tick_coverage(store, _SYMBOL, bar, []) is False
