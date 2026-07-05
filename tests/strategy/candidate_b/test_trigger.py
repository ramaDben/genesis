"""Gatillo de ruptura por cierre + máximo una señal por día, T8 (R55.6, R58, R59, R60)."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import Direction
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_N_MINUTES = 15
_RANGE_HIGH = 4505.0
_RANGE_LOW = 4498.0


def _formed_candidate(
    us500_figure: SymbolFigure, *, direction: Direction | None = Direction.LONG
) -> CandidateB:  # ty: ignore[invalid-type-form]
    """Candidato con rango ya congelado (`_range_high=4505.0`, `_range_low=4498.0`)."""
    candidate = CandidateB(
        figure=us500_figure, reference_balance=100_000.0, n_minutes=_N_MINUTES, risk_pct=0.00375
    )
    # 1.ª barra fija la dirección (o doji si direction is None) y ya contribuye al rango.
    if direction is Direction.LONG:
        first = (4500.0, 4500.1, 4499.9, 4501.0)
    elif direction is Direction.SHORT:
        first = (4500.0, 4500.1, 4499.9, 4499.0)
    else:
        first = (4500.0, 4500.1, 4499.9, 4500.0005)
    rest = [(4500.0, 4500.1, 4499.9, 4500.0)] * (_N_MINUTES - 1)
    bars = [first, *rest]
    for i, (open_, high, low, close) in enumerate(bars):
        candidate.on_bar(
            make_annotated_bar(
                BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
            )
        )
    # Forzamos el rango exacto del ejemplo numérico del spec, sin reabrir la formación.
    candidate._range_high = _RANGE_HIGH
    candidate._range_low = _RANGE_LOW
    return candidate


def _breakout_bar(minute_index: int, close: float):
    return make_annotated_bar(
        BASE_TIME + timedelta(minutes=minute_index),
        open_=close,
        high=max(close, _RANGE_HIGH) + 0.1,
        low=min(close, _RANGE_LOW) - 0.1,
        close=close,
    )


def test_ruptura_long_por_cierre_dispara_una_entry_intent(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.LONG)
    result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    assert len(result) == 1
    assert result[0].direction is Direction.LONG


def test_cierre_en_igualdad_exacta_al_extremo_no_dispara(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.LONG)
    result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4505.0))
    assert result == []


def test_cierre_dentro_del_rango_no_dispara(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.LONG)
    result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4503.0))
    assert result == []


def test_ruptura_short_por_cierre_dispara_simetrica(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.SHORT)
    result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4497.0))
    assert len(result) == 1
    assert result[0].direction is Direction.SHORT


def test_igualdad_exacta_short_no_dispara(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.SHORT)
    result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4498.0))
    assert result == []


def test_segunda_ruptura_el_mismo_dia_tras_senal_emitida_no_dispara(
    us500_figure: SymbolFigure,
) -> None:
    candidate = _formed_candidate(us500_figure, direction=Direction.LONG)
    first_result = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    assert len(first_result) == 1

    second_result = candidate.on_bar(_breakout_bar(_N_MINUTES + 1, close=4510.0))
    assert second_result == []
