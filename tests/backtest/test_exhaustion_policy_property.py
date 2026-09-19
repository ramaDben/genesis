"""Propiedades de `ExhaustionPolicy` (B4, D1 del diseño, Change #109).

`HALT_ENTRIES` (default, R30) vs. `RECORD_AND_CONTINUE` (capa 4, para no truncar la
muestra OOS): el segundo modo produce **al menos** los mismos eventos que el primero,
nunca menos, y el breach TOTAL sigue emitiéndose una única vez por corrida en ambos.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import BreachEvent, BreachKind, ExhaustionPolicy, FillRecord
from genesis.backtest.simulator import Simulator
from genesis.data.profile import load_firm_profile
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.0, min_lot=0.01, max_lot=10.0)
_STARTING_BALANCE = 100_000.0
_BASE_TIME = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)


def _always_fires(bar: object) -> list[EntryIntent]:
    del bar
    return [
        EntryIntent(
            direction=Direction.LONG,
            sizing_hint=0.01,
            candidate_id="B",
            config_version=CONFIG_VERSION,
        )
    ]


def _build_simulator(exhaustion_policy: ExhaustionPolicy) -> Simulator:
    candidate = FakeRiskCandidate(stop_loss=1.0, take_profit=None, on_bar_fn=_always_fires)
    return Simulator(
        candidate,
        symbol="US500",
        firm_profile=load_firm_profile(),
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure("US500"),
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
        exhaustion_policy=exhaustion_policy,
    )


def _run(exhaustion_policy: ExhaustionPolicy, post_breach_bars: int) -> Simulator:
    simulator = _build_simulator(exhaustion_policy)

    # Bar 0: sin breach, abre una posición (ambas políticas se comportan igual).
    bar0 = make_annotated_bar(_BASE_TIME)
    simulator._process_bar(bar0)

    # Bar 1: fuerza un breach TOTAL (amount=10_000 sobre 100_000, STATIC por defecto
    # de `the5ers.json`) hundiendo el balance realizado.
    simulator.account.balance = 0.0
    bar1 = make_annotated_bar(_BASE_TIME + timedelta(minutes=1))
    simulator._process_bar(bar1)

    for i in range(post_breach_bars):
        bar = make_annotated_bar(_BASE_TIME + timedelta(minutes=2 + i))
        simulator._process_bar(bar)

    return simulator


def _intent_entries(simulator: Simulator) -> list[object]:
    """Entradas de decisión sobre intents (`FillRecord`/`RejectionRecord`), en orden."""
    return [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, FillRecord) and not entry.payload.is_exit
    ]


def _total_breaches(simulator: Simulator) -> list[BreachEvent]:
    return [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, BreachEvent) and entry.payload.kind is BreachKind.TOTAL
    ]


@given(post_breach_bars=st.integers(min_value=0, max_value=8))
@settings(max_examples=25, deadline=None)
def test_prop3_halt_entries_es_prefijo_de_record_and_continue(post_breach_bars: int) -> None:
    """PROP-3 (AC4, R6): `entries(HALT_ENTRIES)` es prefijo de `entries(RECORD_AND_CONTINUE)`."""
    halted = _run(ExhaustionPolicy.HALT_ENTRIES, post_breach_bars)
    continued = _run(ExhaustionPolicy.RECORD_AND_CONTINUE, post_breach_bars)

    halted_intents = _intent_entries(halted)
    continued_intents = _intent_entries(continued)

    assert len(halted_intents) <= len(continued_intents)
    assert halted_intents == continued_intents[: len(halted_intents)]

    # `breaches(HALT) ⊆ breaches(CONTINUE)`: mismo escenario hasta el breach, así que
    # el conjunto de eventos TOTAL es idéntico en ambos (ninguno emite más de uno).
    assert _total_breaches(halted) == _total_breaches(continued)


@given(post_breach_bars=st.integers(min_value=0, max_value=8))
@settings(max_examples=25, deadline=None)
def test_prop5_un_solo_breach_total_bajo_record_and_continue(post_breach_bars: int) -> None:
    """PROP-5 (§D1 punto 3): a lo sumo un `BreachEvent(TOTAL)` por corrida, sin truncar."""
    simulator = _run(ExhaustionPolicy.RECORD_AND_CONTINUE, post_breach_bars)
    assert len(_total_breaches(simulator)) <= 1


def test_record_and_continue_sigue_produciendo_entradas_tras_el_agotamiento() -> None:
    """No-regresión: con `post_breach_bars > 0`, `RECORD_AND_CONTINUE` abre más posiciones."""
    continued = _run(ExhaustionPolicy.RECORD_AND_CONTINUE, post_breach_bars=3)
    halted = _run(ExhaustionPolicy.HALT_ENTRIES, post_breach_bars=3)
    assert len(_intent_entries(continued)) > len(_intent_entries(halted))
