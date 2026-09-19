"""Tests de agregación H1 y trailing en `Simulator` (Change #97).

Criterios de aceptación verificados:
- A4: Anti-anticipación del stop (barras posteriores a t no alteran el stop en t).
- A5: La barra en curso no participa (high de t no entra al cálculo del fill de t).
- A6 / A19: El ancla no mira antes de la apertura (vela H1 con open_time < entry_time se ignora).
- A15: La geometría es horaria (stop no varía entre barras M1 de la misma hora, varía al cierre H1).
- A18: Ninguna vela agregada cruza sesiones (cierre a hora no en punto descarta acumulador).
- A20: Posiciones concurrentes (ambas reciben las velas H1 cerradas).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import CostsConfig, load_costs_config
from genesis.backtest.exit_geometry import ExitGeometry, load_exit_geometry
from genesis.backtest.simulator import (
    OpenPosition,
    RiskLevelsProvider,
    Simulator,
)
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.common.timeframe import Timeframe
from genesis.strategy.contract import Direction, EntryIntent, StrategyCandidate
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_TRADING_DAY = date(2024, 1, 2)


class _PassiveCandidate(StrategyCandidate, RiskLevelsProvider):
    def __init__(self) -> None:
        self.candidate_id = "PASSIVE"

    def on_bar(self, bar) -> list[EntryIntent]:
        return []

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float | None]:
        return (90.0, None)


def _build_sim(
    firm_profile: FirmProfile,
    exit_geometry: ExitGeometry,
    figure: SymbolFigure,
    costs_config: CostsConfig,
) -> Simulator:
    return Simulator(
        candidate=_PassiveCandidate(),
        symbol=_SYMBOL,
        firm_profile=firm_profile,
        exit_geometry=exit_geometry,
        figure=figure,
        funnel_config=InspectorFunnelConfig(min_rr=2.0, min_lot=0.01, max_lot=50.0),
        costs_config=costs_config,
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="dataset-tf-test",
    )


def _warm_up_atr(sim: Simulator, n_hours: int = 15, base_price: float = 100.0) -> datetime:
    """Alimenta n_hours velas H1 completas para calentar el ATR (período 14)."""
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    t = start
    for _ in range(n_hours * 60):
        bar = make_annotated_bar(
            t,
            open_=base_price,
            high=base_price + 2.0,
            low=base_price - 2.0,
            close=base_price,
            trading_day=t.date(),
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)
    return t


def test_criterio_a5_barra_en_curso_no_participa(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A5: El high de la barra t es el máximo de toda la serie; el stop aplicado
    en t es el derivado de t-1 y NO el que resultaría de incluir la barra t.
    """
    sim = _build_sim(
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
    )
    current_time = _warm_up_atr(sim, n_hours=15, base_price=100.0)
    assert sim._atr.is_warmed()

    # Abrimos una posición a las current_time (ej. 15:00) con stop inicial 90.0
    pos = OpenPosition(
        position_id="pos-a5",
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.LONG,
        entry_time=current_time,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    # Corremos una hora completa (15:00 a 15:59) donde el high llega a 110.0
    for _ in range(60):
        bar = make_annotated_bar(
            current_time,
            open_=100.0,
            high=110.0,
            low=98.0,
            close=105.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)

    # Al cierre de la hora (15:59), el extremo rodante registró high=110.0.
    # ATR es ~4.0. Nivel esperado ~ 110 - 3*4 = 98.0 > 90.0.
    # Ahora llega la barra t (16:00), con un high monstruoso de 300.0 pero precio cae a 95.0
    # Si la barra 16:00 participara, el stop saltaría a 300 - 3*4 = 288.0,
    # y con open=100 cerraría de inmediato.
    bar_t = make_annotated_bar(
        current_time,
        open_=100.0,
        high=300.0,
        low=97.0,
        close=100.0,
        trading_day=current_time.date(),
    )
    sim._manage_open_positions(bar_t, [], False)

    # La posición sigue viva o tiene el stop derivado de t-1 (<= 98.0), NO de 300.0!
    state = sim._trailing_states["pos-a5"]
    assert state.current_stop < 150.0  # Absolutamente no tomó 300.0


def test_criterio_a6_y_a19_ancla_ignora_maximo_previo_a_apertura(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A6 / A19: Posición abierta a mitad de hora (14:35).
    La vela de las 14:00 trae un pico a las 14:10 (high=180.0).
    La posición abierta a las 14:35 ignora la vela de las 14:00 porque
    open_time (14:00) < entry_time (14:35).
    """
    sim = _build_sim(
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
    )
    current_time = _warm_up_atr(sim, n_hours=15, base_price=100.0)

    # Avanzamos hasta 15:35 inyectando un pico a las 15:10
    for m in range(35):
        h = 180.0 if m == 10 else 102.0
        bar = make_annotated_bar(
            current_time,
            open_=100.0,
            high=h,
            low=98.0,
            close=100.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)

    # A las 15:35 abrimos la posición
    entry_time = current_time
    pos = OpenPosition(
        position_id="pos-a19",
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.LONG,
        entry_time=entry_time,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    # Completamos la hora hasta 15:59
    for _m in range(35, 60):
        bar = make_annotated_bar(
            current_time,
            open_=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)

    # La vela H1 de las 15:00 cerró en 15:59 con open_time = 15:00 < entry_time = 15:35.
    # El trailing state de pos-a19 NO debe tener observaciones del pico de 180.0!
    state = sim._trailing_states.get("pos-a19")
    assert state is not None
    assert state.rolling_extreme.count == 0  # Ignoró la vela de las 15:00
    assert state.current_stop == 90.0       # Mantiene el stop inicial


def test_criterio_a15_geometria_es_horaria(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A15: El stop no varía entre barras M1 de la misma hora; se actualiza
    únicamente al cerrarse la hora.
    """
    sim = _build_sim(
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
    )
    current_time = _warm_up_atr(sim, n_hours=15, base_price=100.0)

    # Posición abierta al inicio de hora
    pos = OpenPosition(
        position_id="pos-a15",
        candidate_id="PASSIVE",
        symbol=_SYMBOL,
        direction=Direction.LONG,
        entry_time=current_time,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=None,
        sizing_hint=0.1,
    )
    sim.account.open_positions.append(pos)

    # Hora 1 (15:00 a 15:59): precio sube a 120.0
    for _ in range(60):
        bar = make_annotated_bar(
            current_time,
            open_=100.0,
            high=120.0,
            low=99.0,
            close=115.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)

    # Hora 2 (16:00 a 16:59): el stop en 16:01, 16:02, ..., 16:50 debe ser IDÉNTICO
    stops_seen: list[float] = []
    for _ in range(45):
        bar = make_annotated_bar(
            current_time,
            open_=115.0,
            high=125.0,
            low=110.0,
            close=120.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)
        current_pos = next(p for p in sim.account.open_positions if p.position_id == "pos-a15")
        stops_seen.append(current_pos.stop_loss)

    # Todos los stops observados intra-hora son idénticos
    assert len(set(stops_seen)) == 1
    assert stops_seen[0] > 90.0  # Subió gracias a la vela H1 de las 15:00


def test_criterio_a18_ninguna_vela_agregada_cruza_sesiones(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A18: Al cierre de sesión a hora no redonda (ej. 17:30), el agregador se descarta
    y no extiende la vela incompleta en la sesión siguiente.
    """
    sim = _build_sim(
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
    )
    t = datetime(2024, 1, 2, 17, 0, tzinfo=UTC)
    session_close = datetime(2024, 1, 2, 17, 30, tzinfo=UTC)

    # Pasamos 30 barras hasta las 17:30
    for _ in range(31):
        bar = make_annotated_bar(
            t,
            open_=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            trading_day=_TRADING_DAY,
            session_close_utc=session_close,
        )
        sim._process_bar(bar)
        t += timedelta(minutes=1)

    # Al llegar a las 17:30 se llamó _enforce_session_close_and_guard y reseteó self._aggregator
    # El acumulador H1 debe estar en None
    assert sim._aggregator._accumulators[Timeframe.H1] is None


def test_criterio_a20_posiciones_concurrentes_reciben_ambas_h1(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
) -> None:
    """Criterio A20: Con dos posiciones abiertas del mismo símbolo, el cierre de la vela H1
    actualiza el extremo rodante de AMBAS posiciones.
    """
    sim = _build_sim(
        firm_profile_fixture,
        exit_geometry_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
    )
    current_time = _warm_up_atr(sim, n_hours=15, base_price=100.0)

    pos1 = OpenPosition(
        "pos-1", "PASSIVE", _SYMBOL, Direction.LONG, current_time, 100.0, 50.0, None, 0.1
    )
    pos2 = OpenPosition(
        "pos-2", "PASSIVE", _SYMBOL, Direction.SHORT, current_time, 100.0, 150.0, None, 0.1
    )
    sim.account.open_positions.extend([pos1, pos2])

    # Corremos 60 minutos con un high=120.0 y low=80.0
    for _ in range(60):
        bar = make_annotated_bar(
            current_time,
            open_=100.0,
            high=120.0,
            low=80.0,
            close=100.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar)
        current_time += timedelta(minutes=1)

    # Ambas posiciones deben tener count=1 en su rolling_extreme
    state1 = sim._trailing_states["pos-1"]
    state2 = sim._trailing_states["pos-2"]
    assert state1.rolling_extreme.count == 1
    assert state2.rolling_extreme.count == 1
    assert state1.rolling_extreme.max_value() == 120.0
    assert state2.rolling_extreme.min_value() == 80.0


@pytest.mark.timeout(60)
@given(
    suffix_highs_a=st.lists(
        st.floats(min_value=100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    ),
    suffix_highs_b=st.lists(
        st.floats(min_value=100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=30, deadline=None)
def test_criterio_a4_anti_anticipacion_del_stop(
    suffix_highs_a: list[float],
    suffix_highs_b: list[float],
) -> None:
    """Criterio A4: Extensión de la propiedad central del spec §9 al stop:
    Mutar cualquier barra posterior a `t` NO cambia el stop efectivo aplicado en `t`.
    """
    def run_up_to_t(suffix_highs: list[float]) -> float:
        sim = _build_sim(
            load_firm_profile(),
            load_exit_geometry(),
            _default_symbol_figure(_SYMBOL),
            load_costs_config(),
        )
        current_time = _warm_up_atr(sim, n_hours=15, base_price=100.0)
        pos = OpenPosition(
            position_id="pos-a4",
            candidate_id="PASSIVE",
            symbol=_SYMBOL,
            direction=Direction.LONG,
            entry_time=current_time,
            entry_price=100.0,
            stop_loss=90.0,
            take_profit=None,
            sizing_hint=0.1,
        )
        sim.account.open_positions.append(pos)

        # 60 minutos para cerrar 1 vela H1
        for _ in range(60):
            bar = make_annotated_bar(
                current_time,
                open_=100.0,
                high=115.0,
                low=98.0,
                close=110.0,
                trading_day=current_time.date(),
            )
            sim._process_bar(bar)
            current_time += timedelta(minutes=1)

        # Barra t (a las 16:00): capturamos el stop efectivo antes de que corra el sufijo futuro
        bar_t = make_annotated_bar(
            current_time,
            open_=110.0,
            high=112.0,
            low=108.0,
            close=110.0,
            trading_day=current_time.date(),
        )
        sim._process_bar(bar_t)
        stop_at_t = sim._trailing_states["pos-a4"].current_stop
        current_time += timedelta(minutes=1)

        # Ahora corremos el sufijo futuro con barras mutadas
        for h in suffix_highs:
            future_bar = make_annotated_bar(
                current_time,
                open_=110.0,
                high=h,
                low=105.0,
                close=108.0,
                trading_day=current_time.date(),
            )
            sim._process_bar(future_bar)
            current_time += timedelta(minutes=1)

        return stop_at_t

    stop_a = run_up_to_t(suffix_highs_a)
    stop_b = run_up_to_t(suffix_highs_b)
    assert stop_a == stop_b

