"""Tests de contratos de simulación: position_id, TP opcional y preservación de lista (Change #97).

Criterios de aceptación verificados:
- A16: La lista de posiciones no se corrompe ante cierres concurrentes (slice assignment).
- A17: Autorización en el embudo y apertura en simulador sin take profit (take_profit=None).
- A21: Vaciado completo de AccountState.open_positions tras cierre forzado de sesión.
- A22: Unicidad de position_id entre simulaciones / ventanas distintas (prefijo dataset_hash).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.backtest.simulator import (
    OpenPosition,
    RiskLevelsProvider,
    Simulator,
    _compute_rr,
)
from genesis.data.profile import FirmProfile
from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent, StrategyCandidate
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.strategy.fakes import make_annotated_bar

_ENTRY_TIME = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
_BAR_TIME = datetime(2024, 1, 2, 14, 31, tzinfo=UTC)
_TRADING_DAY = date(2024, 1, 2)


class _DummyCandidate(StrategyCandidate, RiskLevelsProvider):
    def __init__(self, intents: list[EntryIntent] | None = None, tp: float | None = None) -> None:
        self.candidate_id = "CAND_TEST"
        self._intents = intents or []
        self._tp = tp

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        res = list(self._intents)
        self._intents.clear()
        return res

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float | None]:
        return (90.0, self._tp)


def _build_test_simulator(
    candidate: StrategyCandidate,
    *,
    dataset_hash: str = "dataset-test-1",
    firm_profile: FirmProfile,
    exit_geometry: ExitGeometry,
    figure: SymbolFigure,
    costs_config: CostsConfig,
) -> Simulator:
    return Simulator(
        candidate=candidate,
        symbol="US500",
        firm_profile=firm_profile,
        exit_geometry=exit_geometry,
        figure=figure,
        funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
        costs_config=costs_config,
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash=dataset_hash,
    )


def test_open_position_invariante_position_id_primero_sin_default() -> None:
    """Verifica que position_id es el primer campo sin valor por defecto (R21)."""
    pos = OpenPosition(
        "p-1",
        "B",
        "US500",
        Direction.LONG,
        _ENTRY_TIME,
        100.0,
        90.0,
        None,
        0.1,
    )
    assert pos.position_id == "p-1"
    assert pos.take_profit is None


def test_compute_rr_take_profit_none_retorna_none() -> None:
    """Verifica que _compute_rr retorna None si take_profit es None."""
    rr = _compute_rr(Direction.LONG, reference_price=100.0, stop_loss=90.0, take_profit=None)
    assert rr is None


def test_criterio_a16_supervivencia_posiciones_no_corrupcion(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A16: Con 3 posiciones abiertas y la primera cerrando por fill,
    las otras dos conservan su identidad y la lista no sufre IndexError ni ValueError.
    """
    sim = _build_test_simulator(
        _DummyCandidate(),
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        costs_config=costs_config_fixture,
    )

    pos1 = OpenPosition("pos-1", "B", "US500", Direction.LONG, _ENTRY_TIME, 100.0, 95.0, 110.0, 0.1)
    pos2 = OpenPosition("pos-2", "B", "US500", Direction.LONG, _ENTRY_TIME, 100.0, 80.0, 120.0, 0.1)
    pos3 = OpenPosition("pos-3", "B", "US500", Direction.LONG, _ENTRY_TIME, 100.0, 70.0, 130.0, 0.1)

    sim.account.open_positions.extend([pos1, pos2, pos3])

    # Barra donde el precio cae a 94.0: dispara el SL de pos1 (95.0), no pos2/pos3
    bar = make_annotated_bar(
        _BAR_TIME,
        open_=98.0,
        high=99.0,
        low=94.0,
        close=96.0,
        tick_volume=100,
        trading_day=_TRADING_DAY,
    )

    sim._manage_open_positions(bar, [], coverage=False)

    assert len(sim.account.open_positions) == 2
    assert sim.account.open_positions[0].position_id == "pos-2"
    assert sim.account.open_positions[1].position_id == "pos-3"


def test_criterio_a17_embudo_y_simulador_autorizan_sin_take_profit(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A17 / R22: Intención con take_profit=None se autoriza y se abre en Simulator."""
    intent = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="CAND_TEST",
        config_version=CONFIG_VERSION,
    )
    candidate = _DummyCandidate(intents=[intent], tp=None)
    sim = _build_test_simulator(
        candidate,
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        costs_config=costs_config_fixture,
    )

    bar = make_annotated_bar(
        _BAR_TIME,
        open_=100.0,
        high=102.0,
        low=98.0,
        close=101.0,
        tick_volume=100,
        trading_day=_TRADING_DAY,
    )

    sim._process_new_entries(bar, [], coverage=False)

    assert len(sim.account.open_positions) == 1
    opened = sim.account.open_positions[0]
    assert opened.take_profit is None
    assert opened.stop_loss == 90.0
    assert opened.position_id.startswith("dataset-")


def test_criterio_a21_vaciado_tras_sesion_multiple(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A21: Al cierre forzado de sesión, AccountState.open_positions queda vacía."""
    sim = _build_test_simulator(
        _DummyCandidate(),
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        costs_config=costs_config_fixture,
    )

    pos1 = OpenPosition("pos-1", "B", "US500", Direction.LONG, _ENTRY_TIME, 100.0, 80.0, None, 0.1)
    pos2 = OpenPosition("pos-2", "B", "US500", Direction.LONG, _ENTRY_TIME, 100.0, 80.0, None, 0.1)
    sim.account.open_positions.extend([pos1, pos2])

    bar = make_annotated_bar(
        _BAR_TIME,
        open_=100.0,
        high=102.0,
        low=98.0,
        close=101.0,
        tick_volume=100,
        trading_day=_TRADING_DAY,
    )

    sim._force_close_all_positions(bar, [], coverage=False)
    assert sim.account.open_positions == []


def test_criterio_a22_unicidad_position_id_entre_ventanas(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A22 / R14: position_id no colisiona entre instancias/ventanas distintas."""
    intent1 = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="CAND_TEST",
        config_version=CONFIG_VERSION,
    )
    intent2 = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="CAND_TEST",
        config_version=CONFIG_VERSION,
    )

    cand1 = _DummyCandidate(intents=[intent1], tp=None)
    cand2 = _DummyCandidate(intents=[intent2], tp=None)

    sim_win1 = _build_test_simulator(
        cand1,
        dataset_hash="11111111_window_1_abc",
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        costs_config=costs_config_fixture,
    )
    sim_win2 = _build_test_simulator(
        cand2,
        dataset_hash="22222222_window_2_xyz",
        firm_profile=firm_profile_fixture,
        exit_geometry=exit_geometry_fixture,
        figure=symbol_figure_fixture,
        costs_config=costs_config_fixture,
    )

    bar = make_annotated_bar(
        _BAR_TIME,
        open_=100.0,
        high=102.0,
        low=98.0,
        close=101.0,
        tick_volume=100,
        trading_day=_TRADING_DAY,
    )

    sim_win1._process_new_entries(bar, [], coverage=False)
    sim_win2._process_new_entries(bar, [], coverage=False)

    p1 = sim_win1.account.open_positions[0].position_id
    p2 = sim_win2.account.open_positions[0].position_id

    assert p1 != p2
    assert p1 == "11111111-1"
    assert p2 == "22222222-1"
