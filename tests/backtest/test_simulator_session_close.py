"""Golden de cierre forzado de sesión + guard defensivo (R23, R24, R53, R28)."""

from datetime import datetime, timedelta

import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.errors import SessionBoundaryError
from genesis.backtest.ledger import BreachEvent, BreachKind, FillRecord
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile
from genesis.backtest.simulator import OpenPosition, Simulator
from genesis.data.profile import FirmProfile
from genesis.data.sessions import session_window
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import Direction
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.5, min_lot=0.01, max_lot=10.0)
_TRADING_DAY_MONDAY = datetime(2024, 1, 2).date()
_TRADING_DAY_FRIDAY = datetime(2024, 1, 5).date()


def _build_simulator(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
    *,
    risk_profile: RiskProfile | None = None,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(),
        symbol="US500",
        firm_profile=firm_profile_fixture,
        risk_profile=risk_profile if risk_profile is not None else risk_profile_fixture,
        figure=symbol_figure_fixture,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config_fixture,
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
    )


def _open_position(
    entry_time: datetime,
    *,
    position_id: str = "pos-1",
    stop_loss: float,
    take_profit: float | None = 110.0,
) -> OpenPosition:
    return OpenPosition(
        position_id=position_id,
        candidate_id="B",
        symbol="US500",
        direction=Direction.LONG,
        entry_time=entry_time,
        entry_price=100.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
        sizing_hint=0.1,
    )


def test_cierre_forzado_proactivo_al_cierre_de_sesion(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R23/R53: posición viva al cierre de sesión se cierra proactivamente al precio de la vela."""
    simulator = _build_simulator(
        firm_profile_fixture, risk_profile_fixture, symbol_figure_fixture, costs_config_fixture
    )
    _open_utc, close_utc = session_window("US500", _TRADING_DAY_MONDAY)
    position = _open_position(
        close_utc.replace(hour=close_utc.hour - 1), stop_loss=50.0, take_profit=200.0
    )
    simulator.account.open_positions.append(position)

    bar_at_close = make_annotated_bar(
        close_utc,
        open_=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        trading_day=_TRADING_DAY_MONDAY,
        # El borde de sesión ahora viaja en la barra (Change #46, R10): la premisa del
        # test se declara aquí en vez de resolverse dentro del simulador.
        session_close_utc=close_utc,
    )

    simulator._enforce_session_close_and_guard(bar_at_close, [], False)

    assert simulator.account.open_positions == []
    exit_fills = [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, FillRecord) and entry.payload.is_exit
    ]
    assert len(exit_fills) == 1
    assert exit_fills[0].price == pytest.approx(100.5)


def test_guard_lanza_session_boundary_error_si_posicion_viva_pese_al_cierre(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R24: si el cierre proactivo ya se intentó y aun así queda una posición viva → aborta."""
    simulator = _build_simulator(
        firm_profile_fixture, risk_profile_fixture, symbol_figure_fixture, costs_config_fixture
    )
    _open_utc, close_utc = session_window("US500", _TRADING_DAY_MONDAY)
    bar_at_close = make_annotated_bar(
        close_utc,
        open_=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        trading_day=_TRADING_DAY_MONDAY,
        # El borde de sesión ahora viaja en la barra (Change #46, R10): la premisa del
        # test se declara aquí en vez de resolverse dentro del simulador.
        session_close_utc=close_utc,
    )
    simulator._enforce_session_close_and_guard(bar_at_close, [], False)

    # RI-G6: simula que, pese al cierre proactivo ya intentado, una posición sigue viva.
    simulator.account.open_positions.append(
        _open_position(close_utc, stop_loss=50.0, take_profit=200.0)
    )
    bar_after_close = make_annotated_bar(
        close_utc + timedelta(minutes=1),
        trading_day=_TRADING_DAY_MONDAY,
        session_close_utc=close_utc,
    )

    with pytest.raises(SessionBoundaryError):
        simulator._enforce_session_close_and_guard(bar_after_close, [], False)


def test_breach_weekend_al_cerrar_sesion_del_viernes_sin_holding_permitido(
    firm_profile_fixture: FirmProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """R28: posición viva al cierre del viernes con `weekend_holding_allowed=False`."""
    risk_profile_no_weekend = RiskProfile(
        max_loss_limit_pct=10.0,
        max_loss_limit_kind=MaxLossLimitKind.STATIC,
        weekend_holding_allowed=False,
    )
    simulator = _build_simulator(
        firm_profile_fixture,
        risk_profile_no_weekend,
        symbol_figure_fixture,
        costs_config_fixture,
        risk_profile=risk_profile_no_weekend,
    )
    _open_utc, close_utc = session_window("US500", _TRADING_DAY_FRIDAY)
    position = _open_position(
        close_utc.replace(hour=close_utc.hour - 1), stop_loss=50.0, take_profit=200.0
    )
    simulator.account.open_positions.append(position)

    bar_at_close = make_annotated_bar(
        close_utc,
        open_=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        trading_day=_TRADING_DAY_FRIDAY,
        session_close_utc=close_utc,
    )
    simulator._enforce_session_close_and_guard(bar_at_close, [], False)

    weekend_events = [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, BreachEvent) and entry.payload.kind is BreachKind.WEEKEND
    ]
    assert len(weekend_events) == 1
    assert simulator.account.open_positions == []
