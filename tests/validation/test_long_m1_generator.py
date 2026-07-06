"""Tests del generador de barras M1 largo (Rg-6, T4): determinismo y volumen de días."""

import pandas as pd
import pytest

from genesis.data.profile import FirmProfile
from genesis.data.store import iter_bars
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

pytestmark = pytest.mark.unit


def test_generador_es_determinista_misma_semilla() -> None:
    frame1 = generate_long_m1_frame("US500", n_trading_days=5, seed=7)
    frame2 = generate_long_m1_frame("US500", n_trading_days=5, seed=7)
    assert frame1.equals(frame2)


def test_generador_semillas_distintas_producen_frames_distintos() -> None:
    frame1 = generate_long_m1_frame("US500", n_trading_days=5, seed=1)
    frame2 = generate_long_m1_frame("US500", n_trading_days=5, seed=2)
    assert not frame1.equals(frame2)


def test_generador_produce_al_menos_378_trading_days(
    firm_profile_fixture: FirmProfile,
) -> None:
    frame = generate_long_m1_frame("US500", n_trading_days=378, seed=0)
    days = {bar.trading_day for bar in iter_bars(frame, "US500", firm_profile_fixture)}
    assert len(days) >= 378


def test_generador_columnas_canonicas() -> None:
    frame = generate_long_m1_frame("US500", n_trading_days=2, seed=0)
    expected_columns = {"timestamp", "open", "high", "low", "close", "tick_volume"}
    assert expected_columns <= set(frame.columns)
    assert pd.api.types.is_datetime64_any_dtype(frame["timestamp"])
