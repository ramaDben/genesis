"""Formación y congelamiento del rango de apertura, T6 (R55.5, R57)."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_N_MINUTES = 15


def _range_bars() -> list[tuple[float, float, float, float]]:
    """15 barras deterministas (open, high, low, close) con extremos conocidos."""
    bars = []
    for i in range(_N_MINUTES):
        base = 4500.0 + i * 0.1
        # el máximo absoluto lo fija la barra 7; el mínimo absoluto la barra 3.
        high = base + (5.0 if i == 7 else 0.3)
        low = base - (5.0 if i == 3 else 0.3)
        bars.append((base, high, low, base))
    return bars


def test_rango_es_max_min_de_exactamente_n_minutes_barras(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure, reference_balance=100_000.0, n_minutes=_N_MINUTES, risk_pct=0.00375
    )
    bars = _range_bars()
    expected_high = max(b[1] for b in bars)
    expected_low = min(b[2] for b in bars)

    for i, (open_, high, low, close) in enumerate(bars):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
        )
        result = candidate.on_bar(bar)
        assert result == []

    assert candidate._range_high == expected_high
    assert candidate._range_low == expected_low


def test_barras_posteriores_a_la_ventana_no_modifican_el_rango(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure, reference_balance=100_000.0, n_minutes=_N_MINUTES, risk_pct=0.00375
    )
    bars = _range_bars()
    for i, (open_, high, low, close) in enumerate(bars):
        bar = make_annotated_bar(
            BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
        )
        candidate.on_bar(bar)
    frozen_high = candidate._range_high
    frozen_low = candidate._range_low

    # Barra posterior con extremos exagerados: no debe alterar el rango congelado.
    extreme_bar = make_annotated_bar(
        BASE_TIME + timedelta(minutes=_N_MINUTES),
        open_=4500.0,
        high=999999.0,
        low=-999999.0,
        close=4500.0,
    )
    candidate.on_bar(extreme_bar)

    assert candidate._range_high == frozen_high
    assert candidate._range_low == frozen_low
