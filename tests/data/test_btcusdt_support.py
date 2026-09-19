"""Tests unitarios para el soporte institucional de BTCUSDT (Capa 1)."""

from datetime import UTC, date, datetime, time
from pathlib import Path

import pandas as pd
import pytest

from genesis.data.calendar import SYMBOL_CURRENCIES
from genesis.data.profile import firm_profile_hash, load_firm_profile
from genesis.data.sessions import SESSIONS, FixedUtcWindowSpec, session_window
from genesis.data.store import iter_bars
from genesis.data.symbols import SymbolFigure
from scripts.run_pipeline import _symbol_figure_from_store

pytestmark = pytest.mark.unit


def test_btcusdt_session_window() -> None:
    session_date = date(2026, 6, 15)
    open_utc, close_utc = session_window("BTCUSDT", session_date)
    assert open_utc == datetime(2026, 6, 15, 13, 30, tzinfo=UTC)
    assert close_utc == datetime(2026, 6, 15, 20, 0, tzinfo=UTC)
    assert isinstance(SESSIONS["BTCUSDT"], FixedUtcWindowSpec)


def test_btcusdt_symbol_figure_invariants() -> None:
    fig = SymbolFigure(
        symbol="BTCUSDT",
        tick_value=0.10,
        tick_size=0.10,
        volume_step=0.001,
        stops_level=0,
        freeze_level=0,
        digits=1,
        swap_long=0.0,
        swap_short=0.0,
        swap_rollover_day=0,
    )
    assert fig.value_per_point == 1.0
    assert fig.volume_step == 0.001
    assert fig.digits == 1
    assert fig.tick_size == 0.10
    assert fig.tick_value == 0.10


def test_load_binance_futures_profile() -> None:
    profile_path = Path("src/genesis/data/profiles/binance_futures.json")
    assert profile_path.exists()
    profile = load_firm_profile(profile_path)
    assert profile.name == "binance_futures"
    assert profile.server_tz == "UTC"
    assert profile.daily_reset_time == time(0, 0)
    assert profile.daily_reset_tz == "UTC"
    assert profile.house_rule is None
    assert "BTCUSDT" in profile.symbols
    assert profile.symbols["BTCUSDT"].expected == "BTCUSDT"

    h = firm_profile_hash(profile)
    assert len(h) == 64
    assert h == firm_profile_hash(profile)


def test_btcusdt_calendar_currency_mapping() -> None:
    assert "BTCUSDT" in SYMBOL_CURRENCIES
    assert SYMBOL_CURRENCIES["BTCUSDT"] == frozenset({"USD"})


def test_btcusdt_metadata_store_recovery() -> None:
    store_root = Path("data/raw")
    if not (store_root / "BTCUSDT").is_dir():
        pytest.skip("data/raw/BTCUSDT no presente en el entorno (CI sin datos crudos)")
    try:
        figure = _symbol_figure_from_store(store_root, "BTCUSDT")
    except SystemExit:
        pytest.skip("Sidecars de BTCUSDT no disponibles o sin symbol_figure en CI")
    assert figure.symbol == "BTCUSDT"
    assert figure.tick_size == 0.10
    assert figure.tick_value == 0.10
    assert figure.volume_step == 0.001
    assert figure.digits == 1
    assert figure.value_per_point == 1.0



def test_iter_bars_in_session_btcusdt() -> None:
    profile = load_firm_profile(Path("src/genesis/data/profiles/binance_futures.json"))
    times = [
        datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        datetime(2026, 6, 15, 13, 30, tzinfo=UTC),
        datetime(2026, 6, 15, 16, 0, tzinfo=UTC),
        datetime(2026, 6, 15, 20, 0, tzinfo=UTC),
        datetime(2026, 6, 15, 21, 0, tzinfo=UTC),
    ]
    frame = pd.DataFrame(
        {
            "timestamp": times,
            "open": [65000.0] * 5,
            "high": [65010.0] * 5,
            "low": [64990.0] * 5,
            "close": [65005.0] * 5,
            "tick_volume": [100] * 5,
        }
    )

    bars = list(iter_bars(frame, "BTCUSDT", profile))
    assert len(bars) == 5

    # 12:00 -> fuera de sesión
    assert not bars[0].in_session
    assert bars[0].trading_day == date(2026, 6, 15)

    # 13:30 -> apertura de sesión
    assert bars[1].in_session
    assert bars[1].trading_day == date(2026, 6, 15)

    # 16:00 -> en sesión
    assert bars[2].in_session

    # 20:00 -> cierre de sesión
    assert bars[3].in_session

    # 21:00 -> fuera de sesión
    assert not bars[4].in_session
