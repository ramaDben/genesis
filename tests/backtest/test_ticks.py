"""Tests del lector de ticks forward-only `iter_ticks` (R15–R19, ADR-G6/G8)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import (
    TickCache,
    _day_window,
    has_sufficient_tick_coverage,
    iter_ticks,
)
from genesis.data.metadata import ArtifactMetadata
from genesis.data.mt5_export import ChunkWindow, Granularity, RawParquetStore
from genesis.data.profile import FirmProfile, load_firm_profile
from tests.backtest.fakes import build_server_local_tick_chunk
from tests.strategy.fakes import make_annotated_bar

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


def test_iter_ticks_sin_chunk_persistido_retorna_secuencia_vacia_sin_excepcion(
    tmp_path: Path,
) -> None:
    store = RawParquetStore(tmp_path)
    assert list(iter_ticks(store, _SYMBOL, _TRADING_DAY, _utc_profile())) == []


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
        list(iter_ticks(store, _SYMBOL, _TRADING_DAY, _utc_profile()))


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
    ticks = list(iter_ticks(store, _SYMBOL, _TRADING_DAY, _utc_profile()))
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
    day_ticks = list(iter_ticks(store, _SYMBOL, _TRADING_DAY, _utc_profile()))

    bar_con_cobertura = make_annotated_bar(
        datetime(2024, 1, 2, 14, 31, tzinfo=UTC), trading_day=_TRADING_DAY
    )
    bar_sin_cobertura = make_annotated_bar(
        datetime(2024, 1, 2, 14, 40, tzinfo=UTC), trading_day=_TRADING_DAY
    )

    assert (
        has_sufficient_tick_coverage(store, _SYMBOL, bar_con_cobertura, day_ticks, _utc_profile())
        is True
    )
    assert (
        has_sufficient_tick_coverage(store, _SYMBOL, bar_sin_cobertura, day_ticks, _utc_profile())
        is False
    )


def test_has_sufficient_tick_coverage_sin_chunk_es_false(tmp_path: Path) -> None:
    store = RawParquetStore(tmp_path)
    bar = make_annotated_bar(datetime(2024, 1, 2, 14, 31, tzinfo=UTC), trading_day=_TRADING_DAY)
    assert has_sufficient_tick_coverage(store, _SYMBOL, bar, [], _utc_profile()) is False


def test_iter_ticks_repro_reinterpreta_server_tz_no_utc(tmp_path: Path) -> None:
    """R79: repro TDD del bug — réplica del piloto corrida D (FTMO, `server_tz=Europe/Athens`).

    El chunk crudo persiste el wall-clock del servidor `23:49:58` (viernes, cierre real
    de sesión US500 ~20:49 UTC). Sin reinterpretar como `server_tz`, `iter_ticks` emitiría
    `23:49:58+00:00` (offset +3 sin corregir). El valor correcto es `20:49:58+00:00`.
    """
    store = RawParquetStore(tmp_path)
    server_date = date(2026, 6, 26)
    build_server_local_tick_chunk(
        store,
        _SYMBOL,
        server_date,
        [(datetime(2026, 6, 26, 23, 49, 58), 100.0, 100.1, 100.05)],
    )
    profile = replace(load_firm_profile(), server_tz="Europe/Athens")

    ticks = list(iter_ticks(store, _SYMBOL, server_date, profile))

    assert [tick.timestamp_utc for tick in ticks] == [datetime(2026, 6, 26, 20, 49, 58, tzinfo=UTC)]


def test_iter_ticks_multi_chunk_fusiona_y_ordena_chunks_de_servidor_adyacentes(
    tmp_path: Path,
) -> None:
    """R81: dos chunks de servidor adyacentes (D/D+1, Athens +3) se fusionan y ordenan.

    `trading_day=2026-06-26` (UTC) intersecta dos chunks físicos de servidor: el tick
    tardío del chunk `D` (wall-clock `23:00` Athens -> `20:00` UTC) y el tick temprano
    del chunk `D+1` (wall-clock `00:30` Athens del día siguiente -> `21:30` UTC del
    MISMO `trading_day` UTC). `has_sufficient_tick_coverage` (mismo
    `_candidate_server_dates`, R68) no diverge del resultado fusionado de `iter_ticks`.
    """
    store = RawParquetStore(tmp_path)
    trading_day = date(2026, 6, 26)
    profile = replace(load_firm_profile(), server_tz="Europe/Athens")

    build_server_local_tick_chunk(
        store,
        _SYMBOL,
        date(2026, 6, 26),
        [(datetime(2026, 6, 26, 23, 0, 0), 100.0, 100.1, 100.05)],
    )
    build_server_local_tick_chunk(
        store,
        _SYMBOL,
        date(2026, 6, 27),
        [(datetime(2026, 6, 27, 0, 30, 0), 101.0, 101.1, 101.05)],
    )

    ticks = list(iter_ticks(store, _SYMBOL, trading_day, profile))

    assert [tick.timestamp_utc for tick in ticks] == [
        datetime(2026, 6, 26, 20, 0, 0, tzinfo=UTC),
        datetime(2026, 6, 26, 21, 30, 0, tzinfo=UTC),
    ]

    bar_en_chunk_d = make_annotated_bar(
        datetime(2026, 6, 26, 20, 0, 30, tzinfo=UTC), trading_day=trading_day
    )
    bar_en_chunk_d_mas_1 = make_annotated_bar(
        datetime(2026, 6, 26, 21, 30, 30, tzinfo=UTC), trading_day=trading_day
    )
    assert has_sufficient_tick_coverage(store, _SYMBOL, bar_en_chunk_d, ticks, profile) is True
    assert (
        has_sufficient_tick_coverage(store, _SYMBOL, bar_en_chunk_d_mas_1, ticks, profile) is True
    )


def test_has_sufficient_tick_coverage_multi_chunk_or_solo_un_candidato_persistido(
    tmp_path: Path,
) -> None:
    """R69: condición OR — solo el chunk `D` persistido (`D+1` aún no exportado) y ya
    cubre la vela real de la sesión -> `True` (nunca AND, que reportaría falsamente
    "sin cobertura").
    """
    store = RawParquetStore(tmp_path)
    trading_day = date(2026, 6, 26)
    profile = replace(load_firm_profile(), server_tz="Europe/Athens")

    build_server_local_tick_chunk(
        store,
        _SYMBOL,
        date(2026, 6, 26),
        [(datetime(2026, 6, 26, 23, 0, 0), 100.0, 100.1, 100.05)],
    )
    # D+1 NO persistido: el candidato correspondiente no existe todavía.

    day_ticks = list(iter_ticks(store, _SYMBOL, trading_day, profile))
    bar = make_annotated_bar(datetime(2026, 6, 26, 20, 0, 30, tzinfo=UTC), trading_day=trading_day)

    assert has_sufficient_tick_coverage(store, _SYMBOL, bar, day_ticks, profile) is True


def _single_tick_frame(moment: datetime) -> pd.DataFrame:
    """Frame de un único tick en `moment`, suficiente para poblar un día del caché."""
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([moment], utc=True),
            "bid": [100.0],
            "ask": [100.1],
            "last": [100.05],
        }
    )


def test_tick_cache_reutiliza_el_dia_ya_leido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pedir dos veces el mismo día lee el store una sola vez (Change #46, R30)."""
    store = RawParquetStore(tmp_path)
    profile = _utc_profile()
    moment = datetime(2024, 1, 2, 14, 0, tzinfo=UTC)
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, _single_tick_frame(moment))

    lecturas = 0
    original_read = store.read_chunk

    def contar_lecturas(symbol: str, granularity: Granularity, window: ChunkWindow) -> pd.DataFrame:
        nonlocal lecturas
        lecturas += 1
        return original_read(symbol, granularity, window)

    monkeypatch.setattr(store, "read_chunk", contar_lecturas)

    cache = TickCache()
    primero = cache.ticks_for_day(store, _SYMBOL, _TRADING_DAY, profile)
    segundo = cache.ticks_for_day(store, _SYMBOL, _TRADING_DAY, profile)

    assert primero is segundo, "el caché debe devolver la misma lista, no una copia"
    assert lecturas == 1


def test_tick_cache_no_retiene_mas_dias_que_la_cota(tmp_path: Path) -> None:
    """La cota es lo que impide el consumo que motivó el Change (R33): 4 GB medidos."""
    store = RawParquetStore(tmp_path)
    profile = _utc_profile()
    cache = TickCache(max_days=2)

    for offset in range(3):
        day = _TRADING_DAY + timedelta(days=offset)
        moment = datetime(2024, 1, 2, 14, 0, tzinfo=UTC) + timedelta(days=offset)
        _write_tick_chunk(store, _SYMBOL, day, _single_tick_frame(moment))
        cache.ticks_for_day(store, _SYMBOL, day, profile)

    assert cache.cached_days() == 2


def test_tick_cache_max_days_invalido_lanza_backtest_config_error() -> None:
    """Cota inválida aborta al construir, con contexto: nunca degradación silenciosa."""
    with pytest.raises(BacktestConfigError):
        TickCache(max_days=0)


def test_tick_cache_distingue_simbolos_con_el_mismo_dia(tmp_path: Path) -> None:
    """La clave es `(símbolo, día)`: dos símbolos del mismo día no se pisan."""
    store = RawParquetStore(tmp_path)
    profile = _utc_profile()
    moment = datetime(2024, 1, 2, 14, 0, tzinfo=UTC)
    _write_tick_chunk(store, _SYMBOL, _TRADING_DAY, _single_tick_frame(moment))
    _write_tick_chunk(store, "OTRO", _TRADING_DAY, _single_tick_frame(moment))

    cache = TickCache(max_days=2)
    ticks_uno = cache.ticks_for_day(store, _SYMBOL, _TRADING_DAY, profile)
    ticks_otro = cache.ticks_for_day(store, "OTRO", _TRADING_DAY, profile)

    assert cache.cached_days() == 2
    assert ticks_uno is not ticks_otro
