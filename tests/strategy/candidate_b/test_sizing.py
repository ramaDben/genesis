"""`risk_levels` + geometría (stop/TP/sizing) + guards, T9 (R64, R66-R71)."""

from datetime import timedelta

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.errors import CandidateBStateError
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_N_MINUTES = 15
_RANGE_HIGH = 4505.0
_RANGE_LOW = 4498.0


def _formed_candidate(
    us500_figure: SymbolFigure,
    *,
    atr_stop_frac: float | None = None,
    tp_rr_multiple: float = 3.0,
    risk_pct: float = 0.00375,
    reference_balance: float = 100_000.0,
    atr_period: int = 14,
    rvol_threshold: float = 0.0,
) -> CandidateB:
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=reference_balance,
        n_minutes=_N_MINUTES,
        risk_pct=risk_pct,
        atr_stop_frac=atr_stop_frac,
        atr_period=atr_period,
        tp_rr_multiple=tp_rr_multiple,
        rvol_threshold=rvol_threshold,
    )
    first = (4500.0, 4500.1, 4499.9, 4501.0)
    rest = [(4500.0, 4500.1, 4499.9, 4501.0)] * (_N_MINUTES - 1)
    for i, (open_, high, low, close) in enumerate([first, *rest]):
        candidate.on_bar(
            make_annotated_bar(
                BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
            )
        )
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


def test_regla_primaria_stop_tp_y_sizing_long(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, atr_stop_frac=None, tp_rr_multiple=3.0)
    intents = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    assert len(intents) == 1
    intent = intents[0]

    stop, take_profit = candidate.risk_levels(intent)
    assert stop == pytest.approx(4498.0)
    assert take_profit == pytest.approx(4530.8)
    expected_sizing = (0.00375 * 100_000.0) / (8.2 * 1.0)
    assert intent.sizing_hint == pytest.approx(expected_sizing)


def test_regla_alternativa_stop_por_atr_long(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(us500_figure, atr_stop_frac=1.0, tp_rr_multiple=3.0)
    # `_update_atr` (paso 2) se ejecuta también sobre la barra de ruptura (R55.2); se
    # fuerza un TR de "estado estacionario" (== atr_value) para que el suavizado
    # Wilder deje `_atr_value` en 11.0 exacto en el instante del gatillo (paso 6).
    candidate._atr_value = 11.0
    candidate._atr_bars_seen = candidate._atr_period
    candidate._atr_last_close = 4508.9
    intents = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    assert len(intents) == 1
    intent = intents[0]

    stop, _ = candidate.risk_levels(intent)
    assert stop == pytest.approx(4487.0)


def test_fallback_r64_usa_regla_primaria_si_atr_no_calentado(us500_figure: SymbolFigure) -> None:
    candidate = _formed_candidate(
        us500_figure, atr_stop_frac=1.0, tp_rr_multiple=3.0, atr_period=20
    )
    assert candidate._atr_value is None
    intents = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    assert len(intents) == 1
    intent = intents[0]

    stop, _ = candidate.risk_levels(intent)
    assert stop == pytest.approx(4498.0)  # regla primaria, sin excepción


def test_risk_levels_sin_pendiente_lanza_candidate_b_state_error(
    us500_figure: SymbolFigure,
) -> None:
    candidate = _formed_candidate(us500_figure)
    intents = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))
    intent = intents[0]

    candidate.risk_levels(intent)  # primera lectura, válida (pop-on-read)
    with pytest.raises(CandidateBStateError):
        candidate.risk_levels(intent)  # segunda lectura sin nueva señal


def test_distancia_stop_no_positiva_lanza_candidate_b_state_error(
    us500_figure: SymbolFigure,
) -> None:
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
        atr_stop_frac=None,
        rvol_threshold=0.0,
    )
    first = (4500.0, 4500.1, 4499.9, 4501.0)
    rest = [(4500.0, 4500.1, 4499.9, 4501.0)] * (_N_MINUTES - 1)
    for i, (open_, high, low, close) in enumerate([first, *rest]):
        candidate.on_bar(
            make_annotated_bar(
                BASE_TIME + timedelta(minutes=i), open_=open_, high=high, low=low, close=close
            )
        )
    # Fuerza distancia_stop == 0: dispara (close > range_high) pero stop (=range_low,
    # regla primaria LONG) coincide exactamente con entry_reference.
    candidate._range_high = 4506.1
    candidate._range_low = 4506.2

    with pytest.raises(CandidateBStateError):
        candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))


def _figure_with(tick_value: float, tick_size: float) -> SymbolFigure:
    return SymbolFigure(
        symbol="US500",
        tick_value=tick_value,
        tick_size=tick_size,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-1.0,
        swap_short=-1.0,
        swap_rollover_day=3,
    )


def test_sizing_depende_del_cociente_no_del_tick_value_crudo() -> None:
    """A4: mismo `value_per_point` (cociente) -> mismo `sizing_hint`, aunque el `tick_value`
    crudo difiera 100x entre las dos fichas."""
    figure_a = _figure_with(tick_value=0.01, tick_size=0.01)
    figure_b = _figure_with(tick_value=1.0, tick_size=1.0)
    candidate_a = _formed_candidate(figure_a)
    candidate_b = _formed_candidate(figure_b)
    intent_a = candidate_a.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))[0]
    intent_b = candidate_b.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))[0]
    assert intent_a.sizing_hint == pytest.approx(intent_b.sizing_hint)


def test_sizing_con_ger40_usa_el_cociente_115435() -> None:
    """A5: discrimina el bug (usar `tick_value` crudo) del fix (usar `value_per_point`)."""
    figure = _figure_with(tick_value=0.0115435, tick_size=0.01)
    candidate = _formed_candidate(figure, risk_pct=0.00375, reference_balance=100_000.0)
    intent = candidate.on_bar(_breakout_bar(_N_MINUTES, close=4506.2))[0]
    assert intent.sizing_hint == pytest.approx(375.0 / (8.2 * 1.15435))
    assert intent.sizing_hint != pytest.approx(375.0 / (8.2 * 0.0115435))
