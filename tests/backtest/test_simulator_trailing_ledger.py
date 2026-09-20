"""Tests de registro de TrailingStopMoved en Ledger (Change #97).

Criterios de aceptación verificados:
- A7: Golden test de fill con stop movido (el fill se resuelve al stop movido y no al inicial).
- A8: El registro explica el fill (secuencia TrailingStopMoved coincide con fill).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import FillRecord, TrailingStopMoved
from genesis.backtest.simulator import (
    OpenPosition,
    RiskLevelsProvider,
    Simulator,
)
from genesis.data.profile import load_firm_profile
from genesis.strategy.contract import Direction, EntryIntent, StrategyCandidate
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_SYMBOL = "US500"


class _PassiveCandidate(StrategyCandidate, RiskLevelsProvider):
    def __init__(self) -> None:
        self.candidate_id = "PASSIVE"

    def on_bar(self, bar) -> list[EntryIntent]:
        return []

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float | None]:
        return (90.0, None)


def test_criterio_a7_y_a8_golden_test_trailing_stop_fill_y_ledger() -> None:
    sim = Simulator(
        candidate=_PassiveCandidate(),
        symbol=_SYMBOL,
        firm_profile=load_firm_profile(),
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure(_SYMBOL),
        funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="dataset-trailing-ledger",
    )

    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    t = start
    for _ in range(15 * 60):
        bar = make_annotated_bar(
            t,
            open_=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            trading_day=t.date(),
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    assert sim._atr.is_warmed()

    pos_id = "pos-golden-1"
    pos = OpenPosition(
        position_id=pos_id,
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.LONG,
        entry_time=t,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    for _ in range(60):
        bar = make_annotated_bar(
            t,
            open_=100.0,
            high=120.0,
            low=99.0,
            close=118.0,
            trading_day=t.date(),
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    # Note: the H1 bar of 15:00 closed, which updated ATR to ~5.21 (due to TR=21.0)
    expected_new_stop = 120.0 - 3.0 * sim._atr.value()
    assert expected_new_stop > 90.0

    bar_16_00 = make_annotated_bar(
        t,
        open_=118.0,
        high=119.0,
        low=115.0,
        close=117.0,
        trading_day=t.date(),
    )
    sim._process_bar(bar_16_00)
    t += timedelta(minutes=1)

    move_events = [
        e.payload
        for e in sim.ledger.entries
        if isinstance(e.payload, TrailingStopMoved) and e.payload.position_id == pos_id
    ]
    assert len(move_events) == 1
    assert move_events[0].stop_previo == 90.0
    assert move_events[0].stop_nuevo == pytest.approx(expected_new_stop)
    assert move_events[0].symbol == _SYMBOL
    assert move_events[0].position_id == pos_id

    # 5. Minute 16:01: price drops and touches the moved stop (low=100.0 <= expected_new_stop)
    bar_drop = make_annotated_bar(
        t,
        open_=116.0,
        high=117.0,
        low=100.0,
        close=101.0,
        trading_day=t.date(),
    )
    sim._process_bar(bar_drop)

    assert len(sim.account.open_positions) == 0

    exit_fills = [
        e.payload
        for e in sim.ledger.entries
        if isinstance(e.payload, FillRecord) and e.payload.is_exit
    ]
    assert len(exit_fills) == 1
    exit_fill = exit_fills[0]
    assert exit_fill.price == pytest.approx(expected_new_stop)
    assert exit_fill.price != 90.0

    assert exit_fill.price == move_events[-1].stop_nuevo


def test_criterio_a7_y_a8_short_position_trailing_stop_fill_y_ledger() -> None:
    sim = Simulator(
        candidate=_PassiveCandidate(),
        symbol=_SYMBOL,
        firm_profile=load_firm_profile(),
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure(_SYMBOL),
        funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="dataset-trailing-ledger-short",
    )

    # 1. Warm up ATR for 15 hours
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    t = start
    for _ in range(15 * 60):
        bar = make_annotated_bar(
            t,
            open_=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            trading_day=t.date(),
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    # 2. Open SHORT position at 15:00
    pos_id = "pos-golden-short"
    pos = OpenPosition(
        position_id=pos_id,
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.SHORT,
        entry_time=t,
        entry_price=100.0,
        stop_loss=110.0,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    # 3. Hour 15:00 to 15:59: price drops with low=80.0
    for _ in range(60):
        bar = make_annotated_bar(
            t,
            open_=100.0,
            high=101.0,
            low=80.0,
            close=82.0,
            trading_day=t.date(),
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    # 4. Hour 16:00: stop moves down
    expected_new_stop = 80.0 + 3.0 * sim._atr.value()
    assert expected_new_stop < 110.0

    bar_16_00 = make_annotated_bar(
        t,
        open_=82.0,
        high=85.0,
        low=81.0,
        close=83.0,
        trading_day=t.date(),
    )
    sim._process_bar(bar_16_00)
    t += timedelta(minutes=1)

    move_events = [
        e.payload
        for e in sim.ledger.entries
        if isinstance(e.payload, TrailingStopMoved) and e.payload.position_id == pos_id
    ]
    assert len(move_events) == 1
    assert move_events[0].stop_previo == 110.0
    assert move_events[0].stop_nuevo == pytest.approx(expected_new_stop)

    # 5. Minute 16:01: price rallies and touches the moved stop (high=100.0 >= expected_new_stop)
    bar_rally = make_annotated_bar(
        t,
        open_=83.0,
        high=100.0,
        low=82.0,
        close=99.0,
        trading_day=t.date(),
    )
    sim._process_bar(bar_rally)

    assert len(sim.account.open_positions) == 0

    exit_fills = [
        e.payload
        for e in sim.ledger.entries
        if isinstance(e.payload, FillRecord) and e.payload.is_exit
    ]
    assert len(exit_fills) == 1
    exit_fill = exit_fills[0]
    assert exit_fill.price == pytest.approx(expected_new_stop)
    assert exit_fill.price != 110.0
    assert exit_fill.price == move_events[-1].stop_nuevo


def test_criterio_a10_determinismo() -> None:
    """Criterio A10: Dos corridas idénticas producen secuencias de movimientos iguales."""

    def run_simulation() -> list[TrailingStopMoved]:
        sim = Simulator(
            candidate=_PassiveCandidate(),
            symbol=_SYMBOL,
            firm_profile=load_firm_profile(),
            exit_geometry=load_exit_geometry(),
            figure=_default_symbol_figure(_SYMBOL),
            funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
            costs_config=load_costs_config(),
            news_events=[],
            tick_store=None,
            starting_balance=100_000.0,
            dataset_hash="dataset-determinism",
        )
        t = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        for _ in range(15 * 60):
            bar = make_annotated_bar(
                t, open_=100.0, high=102.0, low=98.0, close=100.0, trading_day=t.date()
            )
            sim._process_bar(bar)
            t += timedelta(minutes=1)

        pos = OpenPosition(
            position_id="pos-det",
            candidate_id="PASSIVE",
            symbol=_SYMBOL,
            direction=Direction.LONG,
            entry_time=t,
            entry_price=100.0,
            stop_loss=90.0,
            take_profit=None,
            sizing_hint=0.1,
        )
        sim.account.open_positions.append(pos)

        for _ in range(120):
            bar = make_annotated_bar(
                t, open_=100.0, high=125.0, low=99.0, close=120.0, trading_day=t.date()
            )
            sim._process_bar(bar)
            t += timedelta(minutes=1)

        return [e.payload for e in sim.ledger.entries if isinstance(e.payload, TrailingStopMoved)]

    run1 = run_simulation()
    run2 = run_simulation()
    assert len(run1) > 0
    assert run1 == run2


def test_criterio_a11_ningun_consumidor_ve_stop_viejo() -> None:
    """Criterio A11: Después de la actualización de una barra, toda lectura del estado
    de la cuenta devuelve la posición con el stop nuevo.
    """
    sim = Simulator(
        candidate=_PassiveCandidate(),
        symbol=_SYMBOL,
        firm_profile=load_firm_profile(),
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure(_SYMBOL),
        funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="dataset-a11",
    )
    t = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    for _ in range(15 * 60):
        bar = make_annotated_bar(
            t, open_=100.0, high=102.0, low=98.0, close=100.0, trading_day=t.date()
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    initial_stop = 90.0
    pos = OpenPosition(
        position_id="pos-a11",
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.LONG,
        entry_time=t,
        entry_price=100.0,
        stop_loss=initial_stop,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    # Corremos 60 minutos con un high alto
    for _ in range(60):
        bar = make_annotated_bar(
            t, open_=100.0, high=130.0, low=99.0, close=125.0, trading_day=t.date()
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    # Procesamos la barra de las 16:00
    bar_t = make_annotated_bar(
        t, open_=125.0, high=126.0, low=122.0, close=124.0, trading_day=t.date()
    )
    sim._process_bar(bar_t)

    # Inmediatamente después del procesamiento de bar_t:
    # La cuenta DEBE tener exactamente la posición con el stop nuevo
    assert len(sim.account.open_positions) == 1
    pos_in_account = sim.account.open_positions[0]
    trailing_state = sim._trailing_states["pos-a11"]

    assert pos_in_account.stop_loss == trailing_state.current_stop
    assert pos_in_account.stop_loss > initial_stop
