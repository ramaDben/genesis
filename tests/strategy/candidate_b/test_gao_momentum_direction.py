"""Tests para la dirección de momentum Gao et al. (2018) en CandidateB (T2, R136)."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB, _infer_gao_direction
from genesis.strategy.contract import Direction
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit


def test_infer_gao_direction_long() -> None:
    assert _infer_gao_direction(100.0, 101.0) is Direction.LONG


def test_infer_gao_direction_short() -> None:
    assert _infer_gao_direction(100.0, 99.0) is Direction.SHORT


def test_infer_gao_direction_doji_neutro() -> None:
    assert _infer_gao_direction(100.0, 100.0) is None


def test_infer_gao_direction_epsilon_threshold() -> None:
    # Retorno insignificante <= 1e-7 se considera doji/neutro
    assert _infer_gao_direction(100.0, 100.000005, epsilon=1e-5) is None


def test_candidate_b_evalua_direccion_gao_al_terminar_ventana(
    us500_figure: SymbolFigure,
) -> None:
    # Ventana de 5 minutos para test rápido, rvol_threshold=0 para omitir filtro de volumen
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=5,
        risk_pct=0.00375,
        rvol_threshold=0.0,
    )

    # Barras 0 a 4 (minutos 0 a 4)
    # Minuto 0: Open = 5000.0
    # Minuto 4: Close = 5050.0 (Retorno positivo acumulado)
    for i in range(5):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i),
            open_=5000.0 + i * 10,
            close=5010.0 + i * 10,
            high=5015.0 + i * 10,
            low=4995.0 + i * 10,
            tick_volume=100,
            in_session=True,
        )
        result = candidate.on_bar(bar)
        assert result == []
        # Durante la formación de la ventana, la dirección aún no se congela
        assert candidate._reference_direction is None

    # Minuto 5: Primera barra post-ventana
    bar_5 = make_annotated_bar(
        BASE_TIME + timedelta(minutes=5),
        open_=5050.0,
        close=5055.0,
        high=5060.0,
        low=5045.0,
        tick_volume=100,
        in_session=True,
    )
    candidate.on_bar(bar_5)
    # Ahora la dirección debe estar fijada a LONG según el retorno de la ventana (5050 / 5000 > 1)
    assert candidate._reference_direction is Direction.LONG
