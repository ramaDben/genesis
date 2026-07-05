"""3 golden de sesión sintética de `CandidateB` (R84): ruptura, falsa ruptura, doji."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_N_MINUTES = 15
_RANGE_HIGH = 4505.0
_RANGE_LOW = 4498.0


def _new_candidate(us500_figure: SymbolFigure) -> CandidateB:  # ty: ignore[invalid-type-form]
    return CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
        atr_stop_frac=None,
        tp_rr_multiple=3.0,
    )


def _run_formation(
    candidate: CandidateB,  # ty: ignore[invalid-type-form]
    *,
    first_close: float,
) -> None:
    """15 barras de formación; la 1.ª fija la dirección (`first_close` vs `open=4500.0`)."""
    first = (4500.0, 4500.1, 4499.9, first_close)
    rest = [(4500.0, 4500.1, 4499.9, 4500.0)] * (_N_MINUTES - 1)
    for i, (open_, high, low, close) in enumerate([first, *rest]):
        candidate.on_bar(
            make_annotated_bar(
                BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
            )
        )
    candidate._range_high = _RANGE_HIGH
    candidate._range_low = _RANGE_LOW


def test_golden_a_ruptura_confirmada_por_cierre(us500_figure: SymbolFigure) -> None:
    """(a) ruptura por cierre → exactamente 1 EntryIntent; risk_levels == (4498.0, 4530.8)."""
    candidate = _new_candidate(us500_figure)
    _run_formation(candidate, first_close=4501.0)  # LONG

    breakout = make_annotated_bar(
        BASE_TIME + timedelta(minutes=_N_MINUTES),
        open_=4505.5,
        high=4506.5,
        low=4505.4,
        close=4506.2,
    )
    intents = candidate.on_bar(breakout)

    assert len(intents) == 1
    stop, take_profit = candidate.risk_levels(intents[0])
    # Comparación con tolerancia de punto flotante (IEEE 754): `4506.2 - 4498.0` no es
    # exactamente `8.2` en binario, por lo que `4530.8` decimal exacto es inalcanzable
    # bit a bit; `pytest.approx` valida la igualdad hasta la precisión de la fórmula
    # (mismo criterio que `test_sizing.py::test_regla_primaria_stop_tp_y_sizing_long`).
    assert stop == pytest.approx(4498.0)
    assert take_profit == pytest.approx(4530.8)


def test_golden_b_falsa_ruptura_intrabar_no_dispara(us500_figure: SymbolFigure) -> None:
    """(b) high>range_high pero close dentro del rango → [] (ruptura por cierre, no intrabar)."""
    candidate = _new_candidate(us500_figure)
    _run_formation(candidate, first_close=4501.0)  # LONG

    false_breakout = make_annotated_bar(
        BASE_TIME + timedelta(minutes=_N_MINUTES),
        open_=4503.0,
        high=4505.5,  # > _RANGE_HIGH intrabar
        low=4502.8,
        close=4503.0,  # cierre dentro del rango: no dispara
    )
    intents = candidate.on_bar(false_breakout)

    assert intents == []


def test_golden_c_doji_en_primera_barra_no_emite_senal_en_toda_la_sesion(
    us500_figure: SymbolFigure,
) -> None:
    """(c) doji exacto en la 1.ª barra → 0 señales en toda la sesión."""
    candidate = _new_candidate(us500_figure)
    _run_formation(candidate, first_close=4500.0005)  # doji: abs(diff)=0.0005 <= epsilon=0.005

    breakout = make_annotated_bar(
        BASE_TIME + timedelta(minutes=_N_MINUTES),
        open_=4505.5,
        high=4600.0,
        low=4400.0,
        close=4600.0,
    )
    intents = candidate.on_bar(breakout)

    assert intents == []
