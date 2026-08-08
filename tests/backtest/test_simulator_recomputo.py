"""El simulador no recalcula por barra lo que solo depende del día (Change #46).

Estas garantías estaban medidas por `scripts/bench_simulator.py` —que contó las llamadas
reales sobre 232.487 barras— pero una medición no impide una regresión: quien reintroduzca
la llamada por barra vería el bench empeorar y la suite en verde. Estos tests cierran esa
puerta (R28, R43).
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.risk_profile import RiskProfile
from genesis.backtest.simulator import Simulator
from genesis.backtest.ticks import _day_window
from genesis.data.metadata import ArtifactMetadata
from genesis.data.mt5_export import ChunkWindow, Granularity, RawParquetStore
from genesis.data.profile import FirmProfile
from genesis.data.sessions import session_window
from genesis.data.symbols import SymbolFigure
from genesis.strategy.inspector import load_inspector_funnel_config
from tests.backtest.fakes import FakeRiskCandidate

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = load_inspector_funnel_config()
_SYMBOL = "US500"


def _m1_frame(moments: list[datetime]) -> pd.DataFrame:
    """Frame M1 mínimo en hora local del servidor, con OHLC plano."""
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(moments),
            "open": [100.0] * len(moments),
            "high": [100.5] * len(moments),
            "low": [99.5] * len(moments),
            "close": [100.0] * len(moments),
            "tick_volume": [10] * len(moments),
        }
    )


def _two_day_frame() -> pd.DataFrame:
    """Tres barras del 2024-03-01 y dos del 2024-03-04, en sesión de contado."""
    return _m1_frame(
        [
            datetime(2024, 3, 1, 15, 0),
            datetime(2024, 3, 1, 15, 1),
            datetime(2024, 3, 1, 15, 2),
            datetime(2024, 3, 4, 15, 0),
            datetime(2024, 3, 4, 15, 1),
        ]
    )


def _build_simulator(
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    figure: SymbolFigure,
    costs_config: CostsConfig,
    *,
    tick_store: RawParquetStore | None = None,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(),
        symbol=_SYMBOL,
        firm_profile=firm_profile,
        risk_profile=risk_profile,
        figure=figure,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=costs_config,
        news_events=[],
        tick_store=tick_store,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
    )


def test_run_resuelve_la_ventana_de_sesion_una_vez_por_dia(
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R28: sobre el run completo, `session_window` se consulta por día, no por barra."""
    simulator = _build_simulator(
        firm_profile_fixture, risk_profile_fixture, symbol_figure_fixture, costs_config_fixture
    )
    frame = _two_day_frame()

    dias_consultados: list[date] = []
    original = session_window

    def espiar(symbol: str, session_date: date) -> tuple[datetime, datetime]:
        dias_consultados.append(session_date)
        return original(symbol, session_date)

    monkeypatch.setattr("genesis.data.store.session_window", espiar)

    ledger = simulator.run(frame)

    assert ledger is not None
    assert len(dias_consultados) == len(set(dias_consultados)), (
        "un mismo trading_day no debe consultarse dos veces"
    )
    assert len(dias_consultados) == 2, "dos días distintos, dos consultas — no cinco barras"


def test_run_consulta_la_existencia_de_chunks_una_vez_por_dia(
    tmp_path: Path,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R43: la consulta de chunks depende del día, no del número de barras.

    Antes eran 1-3 `Path.exists()` por barra: 232.833 syscalls en una corrida de 173 días,
    para un valor que solo cambia de día en día.

    La prueba no fija un número absoluto —depende de cuántos chunks de servidor sean
    candidatos por día, y de que `iter_ticks` también consulte al leer— sino que corre el
    mismo par de días con cinco barras y con veinticinco: si el conteo no se mueve, el
    coste no escala con las barras, que es lo que exige la regla.
    """

    def consultas_para(moments: list[datetime]) -> int:
        store = RawParquetStore(tmp_path)
        registradas: list[tuple[str, ChunkWindow]] = []
        original_has_chunk = store.has_chunk

        def espiar(symbol: str, granularity: Granularity, window: ChunkWindow) -> bool:
            registradas.append((symbol, window))
            return original_has_chunk(symbol, granularity, window)

        monkeypatch.setattr(store, "has_chunk", espiar)

        simulator = _build_simulator(
            firm_profile_fixture,
            risk_profile_fixture,
            symbol_figure_fixture,
            costs_config_fixture,
            tick_store=store,
        )
        simulator.run(_m1_frame(moments))
        return len(registradas)

    pocas_barras = [datetime(2024, 3, 1, 15, minuto) for minuto in range(3)]
    pocas_barras += [datetime(2024, 3, 4, 15, minuto) for minuto in range(2)]

    muchas_barras = [datetime(2024, 3, 1, 15, minuto) for minuto in range(15)]
    muchas_barras += [datetime(2024, 3, 4, 15, minuto) for minuto in range(10)]

    con_5 = consultas_para(pocas_barras)
    con_25 = consultas_para(muchas_barras)

    assert con_5 == con_25, (
        f"5 barras -> {con_5} consultas, 25 barras -> {con_25}: el coste escala con las barras"
    )


def test_ventana_de_sesion_de_la_barra_coincide_con_session_window(
    firm_profile_fixture: FirmProfile,
) -> None:
    """La memoización no debe cambiar el valor: es el mismo que daría la llamada directa."""
    from genesis.data.store import iter_bars

    frame = _two_day_frame()

    for bar in iter_bars(frame, _SYMBOL, firm_profile_fixture):
        esperado_open, esperado_close = session_window(_SYMBOL, bar.trading_day)
        assert bar.session_open_utc == esperado_open
        assert bar.session_close_utc == esperado_close


def _write_tick_chunk_for(
    store: RawParquetStore, symbol: str, trading_day: date, moment: datetime
) -> None:
    """Persiste un chunk de ticks de un solo tick, para que exista cobertura del día."""
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([moment], utc=True),
            "bid": [100.0],
            "ask": [100.1],
            "last": [100.05],
        }
    )
    window = _day_window(trading_day)
    metadata = ArtifactMetadata(
        config_version="test",
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash="test",
        time_range=(window.start, window.end),
        git_commit="test",
    )
    store.write_chunk(frame, symbol, Granularity.TICK, window, metadata)


def test_los_ticks_de_un_dia_se_leen_una_sola_vez_en_el_run(
    tmp_path: Path,
    firm_profile_fixture: FirmProfile,
    risk_profile_fixture: RiskProfile,
    symbol_figure_fixture: SymbolFigure,
    costs_config_fixture: CostsConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El caché evita releer el mismo día, que era el motivo de compartirlo entre combos."""
    store = RawParquetStore(tmp_path)
    _write_tick_chunk_for(store, _SYMBOL, date(2024, 3, 1), datetime(2024, 3, 1, 15, 0, tzinfo=UTC))

    lecturas: list[tuple[str, ChunkWindow]] = []
    original_read = store.read_chunk

    def espiar(symbol: str, granularity: Granularity, window: ChunkWindow) -> pd.DataFrame:
        lecturas.append((symbol, window))
        return original_read(symbol, granularity, window)

    monkeypatch.setattr(store, "read_chunk", espiar)

    simulator = _build_simulator(
        firm_profile_fixture,
        risk_profile_fixture,
        symbol_figure_fixture,
        costs_config_fixture,
        tick_store=store,
    )
    simulator.run(_two_day_frame())

    assert len(lecturas) == len(set(lecturas)), "ningún chunk debe leerse dos veces en un run"
