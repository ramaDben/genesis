"""Modelo monetario del `Simulator`: la conversión punto→dinero usa `value_per_point`
(`tick_value / tick_size`), no `tick_value` crudo (Change #55, R5/R6, H2)."""

from datetime import UTC, datetime

import pytest

from genesis.backtest.costs import CostsConfig, commission_for
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.backtest.ledger import FillRecord
from genesis.backtest.simulator import OpenPosition, ResolvedFill, Simulator
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=1.0, min_lot=0.01, max_lot=10.0)
_ENTRY_TIME = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
_STARTING_BALANCE = 100_000.0


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


def _simulator(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    costs_config_fixture: CostsConfig,
    figure: SymbolFigure,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(),
        symbol="US500",
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=figure,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config_fixture,
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
    )


def _position(
    *,
    position_id: str = "pos-1",
    sizing_hint: float = 0.1,
    take_profit: float | None = 120.0,
) -> OpenPosition:
    return OpenPosition(
        position_id=position_id,
        candidate_id="B",
        symbol="US500",
        direction=Direction.LONG,
        entry_time=_ENTRY_TIME,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=take_profit,
        sizing_hint=sizing_hint,
    )


def test_floating_pnl_usa_value_per_point(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    costs_config_fixture: CostsConfig,
) -> None:
    """A6: con `(1.0, 1.0)` el flotante es `points * sizing_hint * 1.0`; con `(1.0, 0.01)`
    es exactamente 100x el anterior (discriminación del bug)."""
    baseline_sim = _simulator(
        firm_profile_fixture, exit_geometry_fixture, costs_config_fixture, _figure_with(1.0, 1.0)
    )
    scaled_sim = _simulator(
        firm_profile_fixture, exit_geometry_fixture, costs_config_fixture, _figure_with(1.0, 0.01)
    )
    position = _position(sizing_hint=0.1)
    baseline_pnl = baseline_sim._floating_pnl(position, 110.0)
    scaled_pnl = scaled_sim._floating_pnl(position, 110.0)
    assert baseline_pnl == pytest.approx((110.0 - 100.0) * 0.1 * 1.0)
    assert scaled_pnl == pytest.approx(baseline_pnl * 100.0)


def _entry_cost(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    costs_config_fixture: CostsConfig,
    figure: SymbolFigure,
) -> float:
    bar = make_annotated_bar(_ENTRY_TIME, open_=100.0, high=101.0, low=99.0, close=100.5)
    intent = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="B",
        config_version=CONFIG_VERSION,
    )
    simulator = _simulator(
        firm_profile_fixture, exit_geometry_fixture, costs_config_fixture, figure
    )
    simulator._open_position(intent, bar, [], False, 90.0, 120.0)
    return next(
        e.payload.cost_applied
        for e in simulator.ledger.entries
        if isinstance(e.payload, FillRecord) and not e.payload.is_exit
    )


def test_costo_de_entrada_escala_con_tick_value_no_con_tick_size(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    costs_config_fixture: CostsConfig,
) -> None:
    """A7 reescrito (Change #135, R20): la fricción va en ticks, así que su costo en dinero
    es `ticks * tick_value * q`, independiente de `tick_size`.

    E20.1: fichas `(1.0, 1.0)` y `(1.0, 0.01)` -> mismo `cost_applied` de entrada.
    E20.2: fichas `(1.0, 1.0)` y `(2.0, 1.0)` -> la fricción (costo menos comisión de la pata)
    se duplica. E20.3: si alguien volviera a convertir puntos con `tick_value` crudo en vez de
    `value_per_point`, la ficha `(1.0, 0.01)` daría una fricción 100 veces menor y E20.1
    fallaría.
    """
    args = (firm_profile_fixture, exit_geometry_fixture, costs_config_fixture)
    baseline = _entry_cost(*args, _figure_with(1.0, 1.0))
    small_tick = _entry_cost(*args, _figure_with(1.0, 0.01))
    double_value = _entry_cost(*args, _figure_with(2.0, 1.0))
    commission_leg = commission_for("US500", 0.1, costs_config_fixture)

    assert small_tick == pytest.approx(baseline)
    assert double_value - commission_leg == pytest.approx(2 * (baseline - commission_leg))


def test_pnl_realizado_usa_la_misma_conversion_que_el_flotante(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    costs_config_fixture: CostsConfig,
) -> None:
    """H2/D4: `_close_position` no reimplementa la fórmula; el `pnl_gross` realizado
    (deducido del balance final) escala igual que el flotante al cambiar `tick_size`."""
    fill = ResolvedFill(price=115.0, timestamp_utc=_ENTRY_TIME)

    baseline_sim = _simulator(
        firm_profile_fixture, exit_geometry_fixture, costs_config_fixture, _figure_with(1.0, 1.0)
    )
    baseline_position = _position(sizing_hint=0.1)
    baseline_sim.account.open_positions.append(baseline_position)
    baseline_sim._close_position(baseline_position, fill)
    baseline_exit = next(
        e.payload
        for e in baseline_sim.ledger.entries
        if isinstance(e.payload, FillRecord) and e.payload.is_exit
    )
    baseline_pnl_gross = baseline_exit.equity_after - _STARTING_BALANCE + baseline_exit.cost_applied

    scaled_sim = _simulator(
        firm_profile_fixture, exit_geometry_fixture, costs_config_fixture, _figure_with(1.0, 0.01)
    )
    scaled_position = _position(sizing_hint=0.1)
    scaled_sim.account.open_positions.append(scaled_position)
    scaled_sim._close_position(scaled_position, fill)
    scaled_exit = next(
        e.payload
        for e in scaled_sim.ledger.entries
        if isinstance(e.payload, FillRecord) and e.payload.is_exit
    )
    scaled_pnl_gross = scaled_exit.equity_after - _STARTING_BALANCE + scaled_exit.cost_applied

    assert baseline_pnl_gross == pytest.approx((115.0 - 100.0) * 0.1 * 1.0)
    assert scaled_pnl_gross == pytest.approx(baseline_pnl_gross * 100.0)
