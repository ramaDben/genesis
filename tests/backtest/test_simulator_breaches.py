"""Golden de breaches en línea DAILY/TOTAL — continuación vs terminalidad (R25–R31, R54)."""

from datetime import UTC, datetime

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.backtest.ledger import BreachEvent, BreachKind
from genesis.backtest.simulator import Simulator
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.5, min_lot=0.01, max_lot=10.0)
_STARTING_BALANCE = 100_000.0


def _build_simulator(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> tuple[Simulator, FakeRiskCandidate]:
    candidate = FakeRiskCandidate()
    simulator = Simulator(
        candidate,
        symbol="US500",
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config_fixture,
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
    )
    return simulator, candidate


def test_breach_diario_golden_calculado_a_mano(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R25/R54: base doble (flotante vs `previous_day_close_balance`), calculado a mano.

    `firm_profile_fixture.daily_loss_limit_pct == 5.0`; balance realizado 94 000 sin
    posiciones abiertas → `floating_equity == 94_000.0`. `loss_vs_close = 100_000 -
    94_000 = 6_000`; `loss_vs_peak` igual (el pico intradía arranca en 100 000, sin
    haber subido). `daily_loss = max(6_000, 6_000) = 6_000 >= threshold = 100_000 *
    0.05 = 5_000` → dispara `BreachEvent(DAILY)` con `magnitude=6_000`, `threshold=5_000`.
    """
    simulator, _candidate = _build_simulator(
        firm_profile_fixture, exit_geometry_fixture, symbol_figure_fixture, costs_config_fixture
    )
    simulator.account.balance = 94_000.0
    bar = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC))

    simulator._evaluate_breaches(bar, [], False)

    daily_events = [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, BreachEvent) and entry.payload.kind is BreachKind.DAILY
    ]
    assert len(daily_events) == 1
    assert daily_events[0].magnitude == pytest.approx(6_000.0)
    assert daily_events[0].threshold == pytest.approx(5_000.0)
    assert daily_events[0].account_exhausted is False
    assert simulator.account.account_exhausted is False


def test_breach_total_golden_calculado_a_mano(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R26/R54: `exit_geometry_fixture.max_loss_limit_pct == 10.0` (STATIC), calculado a mano.

    `starting_balance = 100_000`; balance realizado 88 000 sin posiciones abiertas →
    `floating_equity == 88_000.0`. `total_loss = 100_000 - 88_000 = 12_000 >=
    threshold = 100_000 * 0.10 = 10_000` → dispara `BreachEvent(TOTAL,
    account_exhausted=True)` y agota la cuenta.
    """
    simulator, _candidate = _build_simulator(
        firm_profile_fixture, exit_geometry_fixture, symbol_figure_fixture, costs_config_fixture
    )
    simulator.account.balance = 88_000.0
    bar = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC))

    simulator._evaluate_breaches(bar, [], False)

    total_events = [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, BreachEvent) and entry.payload.kind is BreachKind.TOTAL
    ]
    assert len(total_events) == 1
    assert total_events[0].magnitude == pytest.approx(12_000.0)
    assert total_events[0].threshold == pytest.approx(10_000.0)
    assert total_events[0].account_exhausted is True
    assert simulator.account.account_exhausted is True


def test_tras_breach_diario_on_bar_sigue_invocandose(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R29: DAILY es continuable — el run sigue invocando `candidate.on_bar`."""
    simulator, candidate = _build_simulator(
        firm_profile_fixture, exit_geometry_fixture, symbol_figure_fixture, costs_config_fixture
    )
    simulator.account.balance = 94_000.0
    bar = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC))

    simulator._process_bar(bar)

    assert simulator.account.account_exhausted is False
    assert bar in candidate.on_bar_calls


def test_tras_breach_total_on_bar_no_se_invoca_y_no_hay_excepcion(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R30/R31: TOTAL agota la cuenta; el run continúa sin excepción, omitiendo `on_bar`."""
    simulator, candidate = _build_simulator(
        firm_profile_fixture, exit_geometry_fixture, symbol_figure_fixture, costs_config_fixture
    )
    simulator.account.balance = 88_000.0
    bar_1 = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC))
    bar_2 = make_annotated_bar(datetime(2024, 1, 2, 15, 1, tzinfo=UTC))

    simulator._process_bar(bar_1)
    assert simulator.account.account_exhausted is True

    simulator._process_bar(bar_2)

    assert bar_2 not in candidate.on_bar_calls
