"""ATR-Wilder-14 incremental, T7 (R55.2, R61, R62, R63, R65)."""

from datetime import date, timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit


def _bar_with_tr(minute_offset: int, *, close: float, true_range: float, in_session: bool = True):
    """Construye una barra cuyo TR respecto al `close` previo es exactamente `true_range`.

    Con `high = close + true_range/2` y `low = close - true_range/2`, y sin gaps
    respecto al `close` anterior, `TR = high - low = true_range` (R62).
    """
    return make_annotated_bar(
        BASE_TIME + timedelta(minutes=minute_offset),
        open_=close,
        close=close,
        high=close + true_range / 2,
        low=close - true_range / 2,
        in_session=in_session,
    )


def test_golden_wilder_calentamiento_y_suavizado(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=100,  # ventana grande para no disparar el gatillo en este test
        risk_pct=0.00375,
        atr_period=14,
    )
    close = 4500.0
    for i in range(14):
        candidate.on_bar(_bar_with_tr(i, close=close, true_range=10.0))
    assert candidate._atr_value == pytest.approx(10.0)

    candidate.on_bar(_bar_with_tr(14, close=close, true_range=24.0))
    assert candidate._atr_value == pytest.approx(((10.0 * 13) + 24.0) / 14)


def test_atr_no_se_resetea_al_cambiar_trading_day(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure, reference_balance=100_000.0, n_minutes=100, risk_pct=0.00375
    )
    close = 4500.0
    for i in range(14):
        candidate.on_bar(_bar_with_tr(i, close=close, true_range=10.0))
    atr_before = candidate._atr_value

    next_day = date(2024, 1, 3)
    next_day_bar = make_annotated_bar(
        BASE_TIME + timedelta(days=1),
        open_=close,
        close=close,
        high=close + 1.0,
        low=close - 1.0,
        trading_day=next_day,
        in_session=True,
    )
    candidate.on_bar(next_day_bar)
    assert candidate._atr_value is not None
    # El estado siguió evolucionando (suavizado Wilder), no se reinició a `None`.
    assert candidate._atr_value != atr_before


def test_barras_fuera_de_sesion_no_contribuyen_al_atr(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure, reference_balance=100_000.0, n_minutes=100, risk_pct=0.00375
    )
    out_of_session_bar = _bar_with_tr(0, close=4500.0, true_range=999.0, in_session=False)
    candidate.on_bar(out_of_session_bar)
    assert candidate._atr_bars_seen == 0
    assert candidate._atr_value is None
