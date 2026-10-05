"""Cobro de costos por pata en el `Simulator` y validación de la fila en `__init__` (#135).

R10: comisión a mitad por pata, spread una vez en la entrada, deslizamiento en la entrada y
en toda salida. R11: el símbolo sin fila de costos falla en el constructor, después del
chequeo de sesión. D2: la tabla de test reproduce el modelo anterior bit a bit.
"""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.backtest.costs import CostsConfig, commission_for, costs_hash
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.backtest.ledger import FillRecord
from genesis.backtest.simulator import OpenPosition, ResolvedFill, Simulator
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import (
    FakeRiskCandidate,
    load_test_costs_config,
    make_costs_config,
    make_instrument_costs,
)
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0)
_ENTRY_TIME = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
_STARTING_BALANCE = 100_000.0
# Ficha con la geometría del MNQ (tick de 0,25 puntos que vale $0,50).
_MNQ_LIKE = _default_symbol_figure("US500", tick_value=0.5, tick_size=0.25)


def _realistic_config(*, spread_ticks: float = 1.0, slippage_ticks: float = 1.0) -> CostsConfig:
    return make_costs_config(
        make_instrument_costs(
            "US500", round_trip_usd=1.90, spread_ticks=spread_ticks, slippage_ticks=slippage_ticks
        )
    )


def _simulator(
    firm_profile: FirmProfile,
    exit_geometry: ExitGeometry,
    costs_config: CostsConfig,
    *,
    figure: SymbolFigure = _MNQ_LIKE,
    symbol: str = "US500",
    stress: float = 1.0,
    candidate: FakeRiskCandidate | None = None,
) -> Simulator:
    return Simulator(
        candidate if candidate is not None else FakeRiskCandidate(),
        symbol=symbol,
        firm_profile=firm_profile,
        exit_geometry=exit_geometry,
        figure=figure,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config,
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
        stress=stress,
    )


def _intent(sizing_hint: float = 1.0) -> EntryIntent:
    return EntryIntent(
        direction=Direction.LONG,
        sizing_hint=sizing_hint,
        candidate_id="B",
        config_version=CONFIG_VERSION,
    )


def _fills(simulator: Simulator) -> tuple[FillRecord, FillRecord]:
    fills = [e.payload for e in simulator.ledger.entries if isinstance(e.payload, FillRecord)]
    entry = next(f for f in fills if not f.is_exit)
    exit_ = next(f for f in fills if f.is_exit)
    return entry, exit_


def _round_trip(simulator: Simulator, *, sizing_hint: float = 1.0) -> tuple[float, float]:
    """Abre en `bar.open = 100` y cierra el mismo día a 101; devuelve los dos `cost_applied`."""
    bar = make_annotated_bar(_ENTRY_TIME, open_=100.0, high=100.5, low=99.5, close=100.2)
    simulator._open_position(_intent(sizing_hint), bar, [], False, 90.0, 120.0)
    position = simulator.account.open_positions[0]
    exit_fill = ResolvedFill(price=101.0, timestamp_utc=_ENTRY_TIME + timedelta(minutes=5))
    simulator._close_position(position, exit_fill)
    simulator.account.open_positions.remove(position)
    entry, exit_ = _fills(simulator)
    return entry.cost_applied, exit_.cost_applied


# --- R10: cobro por pata ------------------------------------------------------------------


def test_simulator_cobra_comision_mitad_por_pata_y_deslizamiento_en_ambas(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, _realistic_config())
    entry, exit_ = _round_trip(simulator)
    assert entry == pytest.approx(1.95)
    assert exit_ == pytest.approx(1.45)
    assert entry + exit_ == pytest.approx(3.40)


def test_simulator_sin_friccion_suma_exactamente_el_ida_y_vuelta(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    config = _realistic_config(spread_ticks=0, slippage_ticks=0)
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, config)
    entry, exit_ = _round_trip(simulator)
    assert entry + exit_ == pytest.approx(1.90)


def test_simulator_stress_duplica_cada_pata(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    simulator = _simulator(
        firm_profile_fixture, exit_geometry_fixture, _realistic_config(), stress=2.0
    )
    entry, exit_ = _round_trip(simulator)
    assert entry == pytest.approx(3.90)
    assert exit_ == pytest.approx(2.90)


def _open_position_at_100() -> OpenPosition:
    return OpenPosition(
        position_id="pos-1",
        candidate_id="B",
        symbol="US500",
        direction=Direction.LONG,
        entry_time=_ENTRY_TIME,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=130.0,
        sizing_hint=1.0,
    )


def _exit_cost(simulator: Simulator) -> float:
    exits = [
        e.payload
        for e in simulator.ledger.entries
        if isinstance(e.payload, FillRecord) and e.payload.is_exit
    ]
    assert len(exits) == 1
    return exits[0].cost_applied


def test_deslizamiento_de_salida_se_cobra_en_toda_salida(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    """E10.4: cierre forzado de sesión (sin tocar SL) y salida por stop cobran lo mismo."""
    later = _ENTRY_TIME + timedelta(minutes=10)

    by_session = _simulator(firm_profile_fixture, exit_geometry_fixture, _realistic_config())
    by_session.account.open_positions.append(_open_position_at_100())
    quiet_bar = make_annotated_bar(later, open_=100.0, high=100.5, low=99.5, close=100.2)
    by_session._force_close_all_positions(quiet_bar, [], False)

    by_stop = _simulator(firm_profile_fixture, exit_geometry_fixture, _realistic_config())
    by_stop.account.open_positions.append(_open_position_at_100())
    stop_bar = make_annotated_bar(later, open_=96.0, high=96.5, low=94.0, close=94.5)
    by_stop._manage_open_positions(stop_bar, [], False)

    assert by_stop.account.open_positions == []
    assert _exit_cost(by_session) == pytest.approx(1.45)
    assert _exit_cost(by_stop) == pytest.approx(_exit_cost(by_session))


def test_balance_descuenta_exactamente_cost_applied(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, _realistic_config())
    entry_cost, exit_cost = _round_trip(simulator)
    pnl_gross = (101.0 - 100.0) * 1.0 * _MNQ_LIKE.value_per_point
    expected = _STARTING_BALANCE + pnl_gross - (entry_cost + exit_cost)
    assert simulator.account.balance == pytest.approx(expected)


# --- AE1: ciclo completo con fricción realista (revisión agy, 2026-10-05) -------------------


def _bar(minute: int, *, open_: float, high: float, low: float, close: float, **kwargs: object):
    return make_annotated_bar(
        _ENTRY_TIME + timedelta(minutes=minute),
        open_=open_,
        high=high,
        low=low,
        close=close,
        **kwargs,  # ty: ignore[invalid-argument-type]
    )


def _assert_full_cycle_costs(simulator: Simulator) -> None:
    entry, exit_ = _fills(simulator)
    assert entry.cost_applied == pytest.approx(1.95)
    assert exit_.cost_applied == pytest.approx(1.45)
    pnl_gross = (exit_.price - entry.price) * 1.0 * _MNQ_LIKE.value_per_point
    expected = _STARTING_BALANCE + pnl_gross - (entry.cost_applied + exit_.cost_applied)
    assert simulator.account.balance == pytest.approx(expected)
    assert exit_.equity_after == pytest.approx(expected)


def test_ciclo_completo_con_friccion_realista_salida_por_stop(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    """AE1: `_process_bar` de punta a punta, fila 1,90/1/1, salida por stop."""
    candidate = FakeRiskCandidate(
        entry_threshold=101.0, sizing_hint=1.0, stop_loss=95.0, take_profit=130.0
    )
    simulator = _simulator(
        firm_profile_fixture, exit_geometry_fixture, _realistic_config(), candidate=candidate
    )
    for bar in (
        _bar(0, open_=100.9, high=101.5, low=100.5, close=101.2),
        _bar(1, open_=101.0, high=101.3, low=100.4, close=100.6),
        _bar(2, open_=96.0, high=96.5, low=94.0, close=94.5),
    ):
        simulator._process_bar(bar)
    assert simulator.account.open_positions == []
    _assert_full_cycle_costs(simulator)


def test_ciclo_completo_con_friccion_realista_salida_por_cierre_de_sesion(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    """AE1: `_process_bar` de punta a punta, fila 1,90/1/1, cierre forzado de sesión."""
    candidate = FakeRiskCandidate(
        entry_threshold=101.0, sizing_hint=1.0, stop_loss=95.0, take_profit=130.0
    )
    simulator = _simulator(
        firm_profile_fixture, exit_geometry_fixture, _realistic_config(), candidate=candidate
    )
    close_utc = _ENTRY_TIME + timedelta(minutes=1)
    for bar in (
        _bar(0, open_=100.9, high=101.5, low=100.5, close=101.2, session_close_utc=close_utc),
        _bar(1, open_=101.0, high=101.3, low=100.4, close=100.6, session_close_utc=close_utc),
    ):
        simulator._process_bar(bar)
    assert simulator.account.open_positions == []
    _assert_full_cycle_costs(simulator)
    _entry, exit_ = _fills(simulator)
    assert exit_.price == pytest.approx(100.6)


# --- R11: validación en __init__ ----------------------------------------------------------


def test_simulator_simbolo_sin_fila_falla_en_init(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    config = make_costs_config(make_instrument_costs("MNQ"))
    with pytest.raises(BacktestConfigError) as excinfo:
        _simulator(firm_profile_fixture, exit_geometry_fixture, config)
    message = str(excinfo.value)
    assert "'US500'" in message
    assert "['MNQ']" in message


def test_simbolo_fuera_de_sesiones_y_de_tabla_da_error_de_sesion(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    with pytest.raises(BacktestConfigError) as excinfo:
        _simulator(
            firm_profile_fixture, exit_geometry_fixture, load_test_costs_config(), symbol="NOPE"
        )
    message = str(excinfo.value)
    assert "SESSIONS" in message
    assert "tabla de costos" not in message


def test_simbolo_con_fila_fuera_de_sesiones_da_error_de_sesion(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    with pytest.raises(BacktestConfigError, match="SESSIONS"):
        _simulator(
            firm_profile_fixture, exit_geometry_fixture, load_test_costs_config(), symbol="SYM_A"
        )


def test_simbolo_con_fila_y_sesion_construye(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, load_test_costs_config())
    assert simulator.symbol == "US500"


@pytest.mark.parametrize("function", ["Simulator"])
def test_simbolo_sin_fila_falla_con_contexto(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry, function: str
) -> None:
    """E9.1, caso `Simulator` (choque C1): `US500` sí está en `SESSIONS` y no tiene fila."""
    del function
    config = make_costs_config(make_instrument_costs("MNQ"), make_instrument_costs("MGC"))
    with pytest.raises(BacktestConfigError) as excinfo:
        _simulator(firm_profile_fixture, exit_geometry_fixture, config)
    message = str(excinfo.value)
    assert "'US500'" in message
    assert message.index("MGC") < message.index("MNQ")
    assert "sin valor de respaldo" in message.lower()


# --- R14: procedencia de la corrida ---------------------------------------------------------


def test_simulator_provenance_trae_costs_hash(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    config = load_test_costs_config()
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, config)
    assert simulator.ledger.provenance.costs_hash == costs_hash("US500", config)


def test_provenance_cambia_con_spread_ticks(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    one = _simulator(firm_profile_fixture, exit_geometry_fixture, _realistic_config())
    two = _simulator(
        firm_profile_fixture, exit_geometry_fixture, _realistic_config(spread_ticks=2.0)
    )
    assert one.ledger.provenance.costs_hash != two.ledger.provenance.costs_hash


# --- D2: la tabla de test reproduce el modelo anterior --------------------------------------


@pytest.mark.parametrize("stress", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("q", [0.01, 0.1, 0.37, 1.0, 2.5])
def test_tabla_de_test_reproduce_el_modelo_anterior(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry, q: float, stress: float
) -> None:
    """Entrada `q*7*s + (1,5*s + 0,2*s)*q` y salida `q*7*s`: igualdad exacta (D2, R19)."""
    simulator = _simulator(
        firm_profile_fixture,
        exit_geometry_fixture,
        load_test_costs_config(),
        figure=_default_symbol_figure("US500"),
        stress=stress,
    )
    entry, exit_ = _round_trip(simulator, sizing_hint=q)
    assert entry == q * 7.0 * stress + (1.5 * stress + 0.2 * stress) * q * 1.0
    assert exit_ == q * 7.0 * stress


def test_comision_de_pata_coincide_con_commission_for(
    firm_profile_fixture: FirmProfile, exit_geometry_fixture: ExitGeometry
) -> None:
    config = _realistic_config(spread_ticks=0, slippage_ticks=0)
    simulator = _simulator(firm_profile_fixture, exit_geometry_fixture, config)
    entry, exit_ = _round_trip(simulator)
    assert entry == commission_for("US500", 1.0, config)
    assert exit_ == commission_for("US500", 1.0, config)
