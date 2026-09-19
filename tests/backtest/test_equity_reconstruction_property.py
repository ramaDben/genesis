"""Propiedad central del spec §9: equity reconstruida del ledger == equity en vivo (R47).

`reconstruct_equity_series(ledger.entries)` (T6) DEBE reproducir exactamente la serie
de equity que se registró en vivo en el momento de cada `Ledger.append` durante la
ejecución del `Simulator` — sin depender de ningún estado adicional del `Simulator`.
Se instrumenta `Ledger.append` con un observador que captura `(timestamp_utc,
equity_after)` de cada `FillRecord` EN EL MOMENTO en que se persiste, y se compara
contra la reconstrucción pura post-hoc.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import Decision, ExhaustionPolicy, FillRecord, reconstruct_equity_series
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


def _bars(closes: list[float]) -> list[AnnotatedBar]:
    return [
        make_annotated_bar(
            _BASE_TIME + timedelta(minutes=i),
            close=close,
            open_=close - 0.1,
            high=close + 0.5,
            low=close - 0.5,
        )
        for i, close in enumerate(closes)
    ]


def _build_simulator(
    exhaustion_policy: ExhaustionPolicy = ExhaustionPolicy.HALT_ENTRIES,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(entry_threshold=101.0, stop_loss=80.0, take_profit=130.0),
        symbol="US500",
        firm_profile=load_firm_profile(),
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure("US500"),
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
        exhaustion_policy=exhaustion_policy,
    )


def _install_live_recorder(simulator: Simulator) -> dict[date, list[tuple[datetime, float]]]:
    """Instrumenta `simulator.ledger.append` para capturar la equity EN VIVO al persistir."""
    live_series: dict[date, list[tuple[datetime, float]]] = {}
    original_append: Callable[[Decision], None] = simulator.ledger.append

    def recording_append(payload: Decision) -> None:
        original_append(payload)
        if isinstance(payload, FillRecord):
            day = payload.timestamp_utc.date()
            live_series.setdefault(day, []).append((payload.timestamp_utc, payload.equity_after))

    simulator.ledger.append = recording_append  # ty: ignore[invalid-assignment]
    return live_series


_closes_strategy = st.lists(
    st.floats(min_value=95.0, max_value=115.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=8,
)


@pytest.mark.parametrize("exhaustion_policy", list(ExhaustionPolicy))
@given(closes=_closes_strategy)
@settings(max_examples=1000, deadline=None)
def test_reconstruct_equity_series_iguala_la_serie_registrada_en_vivo(
    exhaustion_policy: ExhaustionPolicy,
    closes: list[float],
) -> None:
    """R47: la reconstrucción pura del ledger reproduce exactamente la serie en vivo.

    PROP-4 (Change #109): también bajo `RECORD_AND_CONTINUE`.
    """
    simulator = _build_simulator(exhaustion_policy)
    live_series = _install_live_recorder(simulator)

    for bar in _bars(closes):
        simulator._process_bar(bar)

    reconstructed = reconstruct_equity_series(simulator.ledger.entries)
    assert reconstructed == live_series
