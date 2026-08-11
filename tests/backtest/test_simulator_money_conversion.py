"""Modelo monetario del `Simulator`: la conversión punto→dinero usa `value_per_point`
(`tick_value / tick_size`), no `tick_value` crudo (Change #55, R5/R6, H2)."""

from datetime import UTC, datetime

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.ledger import FillRecord
from genesis.backtest.risk_profile import RiskProfile
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
    risk_profile_fixture: RiskProfile,
    costs_config_fixture: CostsConfig,
    figure: SymbolFigure,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(),
        symbol="US500",
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile_fixture,
        figure=figure,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config_fixture,
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
    )


def _position(*, sizing_hint: float = 0.1) -> OpenPosition:
    return OpenPosition(
        candidate_id="B",
        symbol="US500",
        direction=Direction.LONG,
        entry_time=_ENTRY_TIME,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        sizing_hint=sizing_hint,
    )


def test_floating_pnl_usa_value_per_point(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    costs_config_fixture: CostsConfig,
) -> None:
    """A6: con `(1.0, 1.0)` el flotante es `points * sizing_hint * 1.0`; con `(1.0, 0.01)`
    es exactamente 100x el anterior (discriminación del bug)."""
    baseline_sim = _simulator(
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 1.0)
    )
    scaled_sim = _simulator(
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 0.01)
    )
    position = _position(sizing_hint=0.1)
    baseline_pnl = baseline_sim._floating_pnl(position, 110.0)
    scaled_pnl = scaled_sim._floating_pnl(position, 110.0)
    assert baseline_pnl == pytest.approx((110.0 - 100.0) * 0.1 * 1.0)
    assert scaled_pnl == pytest.approx(baseline_pnl * 100.0)


def test_costo_de_entrada_usa_value_per_point(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    costs_config_fixture: CostsConfig,
) -> None:
    """A7: el `cost_applied` de la entrada (`is_exit=False`) difiere entre las dos fichas
    (el componente de spread/slippage escala con `value_per_point`; la comisión no)."""
    bar = make_annotated_bar(_ENTRY_TIME, open_=100.0, high=101.0, low=99.0, close=100.5)
    intent = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="B",
        config_version=CONFIG_VERSION,
    )

    baseline_sim = _simulator(
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 1.0)
    )
    baseline_sim._open_position(intent, bar, [], False, 90.0, 120.0)
    baseline_entry = next(
        e.payload
        for e in baseline_sim.ledger.entries
        if isinstance(e.payload, FillRecord) and not e.payload.is_exit
    )

    scaled_sim = _simulator(
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 0.01)
    )
    scaled_sim._open_position(intent, bar, [], False, 90.0, 120.0)
    scaled_entry = next(
        e.payload
        for e in scaled_sim.ledger.entries
        if isinstance(e.payload, FillRecord) and not e.payload.is_exit
    )

    assert scaled_entry.cost_applied != pytest.approx(baseline_entry.cost_applied)


def test_pnl_realizado_usa_la_misma_conversion_que_el_flotante(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    costs_config_fixture: CostsConfig,
) -> None:
    """H2/D4: `_close_position` no reimplementa la fórmula; el `pnl_gross` realizado
    (deducido del balance final) escala igual que el flotante al cambiar `tick_size`."""
    fill = ResolvedFill(price=115.0, timestamp_utc=_ENTRY_TIME)

    baseline_sim = _simulator(
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 1.0)
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
        firm_profile_fixture, risk_profile_fixture, costs_config_fixture, _figure_with(1.0, 0.01)
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
