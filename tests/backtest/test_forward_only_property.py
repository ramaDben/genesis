"""Propiedad forward-only a nivel de simulación completa (R52, spec §9).

Ningún resultado de simular hasta un instante `t` (ledger/balance) DEBE depender de
barras con `timestamp_utc > t`. Se generan con `hypothesis` un prefijo común de
`AnnotatedBar` y dos "colas" futuras distintas y arbitrarias; se simula bar-a-bar con
`Simulator._process_bar` (mismo patrón que `tests/strategy/test_contract_lookahead_
property.py`) y se compara el estado capturado justo después del prefijo, ANTES de
alimentar cualquier cola futura al `Simulator`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import load_costs_config
from genesis.backtest.ledger import LedgerEntry
from genesis.backtest.risk_profile import load_risk_profile
from genesis.backtest.simulator import Simulator
from genesis.data.profile import load_firm_profile
from genesis.data.store import AnnotatedBar
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0)


def _bars(closes: list[float], *, start_index: int = 0) -> list[AnnotatedBar]:
    return [
        make_annotated_bar(
            _BASE_TIME + timedelta(minutes=start_index + i),
            close=close,
            open_=close - 0.1,
            high=close + 0.5,
            low=close - 0.5,
        )
        for i, close in enumerate(closes)
    ]


def _build_simulator() -> Simulator:
    return Simulator(
        FakeRiskCandidate(entry_threshold=101.0, stop_loss=80.0, take_profit=130.0),
        symbol="US500",
        firm_profile=load_firm_profile(),
        risk_profile=load_risk_profile(),
        figure=_default_symbol_figure("US500"),
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
    )


def _simulate_prefix_then_capture(
    prefix_closes: list[float], suffix_closes: list[float]
) -> tuple[list[LedgerEntry], float]:
    """Procesa el prefijo, captura el estado, y SOLO DESPUÉS alimenta la cola futura."""
    simulator = _build_simulator()
    for bar in _bars(prefix_closes):
        simulator._process_bar(bar)

    snapshot_entries = list(simulator.ledger.entries)
    snapshot_balance = simulator.account.balance

    for bar in _bars(suffix_closes, start_index=len(prefix_closes)):
        simulator._process_bar(bar)

    return snapshot_entries, snapshot_balance


_closes_strategy = st.lists(
    st.floats(min_value=95.0, max_value=115.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=5,
)
_future_closes_strategy = st.lists(
    st.floats(min_value=95.0, max_value=115.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=5,
)


@pytest.mark.timeout(180)
@given(
    prefix_closes=_closes_strategy,
    suffix_closes_a=_future_closes_strategy,
    suffix_closes_b=_future_closes_strategy,
)
@settings(max_examples=1000, deadline=None)
def test_ledger_hasta_t_no_cambia_si_se_mutan_barras_futuras(
    prefix_closes: list[float],
    suffix_closes_a: list[float],
    suffix_closes_b: list[float],
) -> None:
    """R52: el ledger/balance hasta `t` es idéntico sin importar qué barras futuras se agreguen."""
    entries_a, balance_a = _simulate_prefix_then_capture(prefix_closes, suffix_closes_a)
    entries_b, balance_b = _simulate_prefix_then_capture(prefix_closes, suffix_closes_b)
    assert entries_a == entries_b
    assert balance_a == pytest.approx(balance_b)
