"""Tests para el filtro de volumen relativo (RVOL) en CandidateB (T3, R137, R138)."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit


def test_rvol_en_fase_warmup_no_habilita_senal(us500_figure: SymbolFigure) -> None:
    # Sin histórico de días previos (< 20 días), la sesión queda en warmup
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=5,
        risk_pct=0.00375,
        rvol_threshold=1.50,
        rvol_lookback_days=20,
    )

    # 5 barras de ventana de apertura
    for i in range(5):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i),
            open_=5000.0,
            close=5010.0,
            high=5015.0,
            low=4995.0,
            tick_volume=500,
            in_session=True,
        )
        candidate.on_bar(bar)

    # Barra 5: Ruptura masiva por encima del rango
    breakout_bar = make_annotated_bar(
        BASE_TIME + timedelta(minutes=5),
        open_=5010.0,
        close=5200.0,
        high=5210.0,
        low=5005.0,
        tick_volume=1000,
        in_session=True,
    )
    result = candidate.on_bar(breakout_bar)
    # Debe ser rechazado porque no ha completado el warmup de 20 días
    assert result == []
    assert candidate._session_rvol_passed is False


def test_rvol_bajo_umbral_inhibe_senales(us500_figure: SymbolFigure) -> None:
    # Con 20 días previos de 1000 de volumen cada uno (mediana = 1000)
    prev_volumes = [1000.0] * 20
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=5,
        risk_pct=0.00375,
        rvol_threshold=1.50,
        rvol_lookback_days=20,
        initial_daily_volumes=prev_volumes,
    )

    # 5 barras con 200 de volumen cada una -> total 1000.0
    # RVOL = 1000 / 1000 = 1.00 < 1.50 -> No pasa el filtro
    for i in range(5):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i),
            open_=5000.0,
            close=5010.0,
            high=5015.0,
            low=4995.0,
            tick_volume=200,
            in_session=True,
        )
        candidate.on_bar(bar)

    # Barra 5: Ruptura alcista
    breakout_bar = make_annotated_bar(
        BASE_TIME + timedelta(minutes=5),
        open_=5010.0,
        close=5200.0,
        high=5210.0,
        low=5005.0,
        tick_volume=500,
        in_session=True,
    )
    result = candidate.on_bar(breakout_bar)
    assert result == []
    assert candidate._session_rvol_passed is False
    assert candidate._session_rvol == pytest.approx(1.00)


def test_rvol_supera_umbral_habilita_senal(us500_figure: SymbolFigure) -> None:
    # Con 20 días previos de 1000 de volumen cada uno (mediana = 1000)
    prev_volumes = [1000.0] * 20
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=5,
        risk_pct=0.00375,
        rvol_threshold=1.50,
        rvol_lookback_days=20,
        initial_daily_volumes=prev_volumes,
    )

    # 5 barras con 350 de volumen cada una -> total 1750.0
    # RVOL = 1750 / 1000 = 1.75 >= 1.50 -> Pasa el filtro
    for i in range(5):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i),
            open_=5000.0 + i * 5,
            close=5010.0 + i * 5,
            high=5015.0 + i * 5,
            low=4995.0 + i * 5,
            tick_volume=350,
            in_session=True,
        )
        candidate.on_bar(bar)

    # Barra 5: Ruptura alcista por encima de range_high (5035)
    breakout_bar = make_annotated_bar(
        BASE_TIME + timedelta(minutes=5),
        open_=5030.0,
        close=5050.0,
        high=5055.0,
        low=5025.0,
        tick_volume=500,
        in_session=True,
    )
    result = candidate.on_bar(breakout_bar)
    assert len(result) == 1
    assert candidate._session_rvol_passed is True
    assert candidate._session_rvol == pytest.approx(1.75)
