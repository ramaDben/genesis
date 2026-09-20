"""Propiedad forward-only a nivel de simulación completa (R52, R82, spec §9).

Ningún resultado de simular hasta un instante `t` (ledger/balance) DEBE depender de
barras (ni ticks, R82) con `timestamp_utc > t`. Se generan con `hypothesis` un
prefijo común de `AnnotatedBar` y dos "colas" futuras distintas y arbitrarias; se
simula bar-a-bar con `Simulator._process_bar` (mismo patrón que
`tests/strategy/test_contract_lookahead_property.py`) y se compara el estado
capturado justo después del prefijo, ANTES de alimentar cualquier cola futura al
`Simulator`. El segundo caso (R82) repite la propiedad con `tick_store` poblado con
chunks de `server_tz != UTC` (`Europe/Athens`, `build_server_local_tick_chunk`,
ADR-21-7): el `Simulator` cachea el día completo de ticks por `trading_day`
(`RI-G1`), por lo que el escenario relevante es que mutar ticks/barras con
`timestamp_utc > t` (ya presentes en el chunk del mismo día servidor) no cambie el
estado capturado hasta `t`.
"""

import tempfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import ExhaustionPolicy, LedgerEntry
from genesis.backtest.simulator import Simulator
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import AnnotatedBar
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate, build_server_local_tick_chunk
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0)
_ATHENS_SERVER_TZ = ZoneInfo("Europe/Athens")


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


def _build_simulator_with_tick_store(
    tick_store: RawParquetStore,
    firm_profile: FirmProfile,
    exhaustion_policy: ExhaustionPolicy = ExhaustionPolicy.HALT_ENTRIES,
) -> Simulator:
    return Simulator(
        FakeRiskCandidate(entry_threshold=101.0, stop_loss=80.0, take_profit=130.0),
        symbol="US500",
        firm_profile=firm_profile,
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure("US500"),
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=tick_store,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash",
        exhaustion_policy=exhaustion_policy,
    )


def _populate_athens_tick_store(store: RawParquetStore, bars: list[AnnotatedBar]) -> None:
    """Escribe un tick por barra (mismo `close`), wall-clock de servidor Athens (R82).

    Todas las barras de este módulo caen en el mismo `trading_day` de servidor (offset
    +3 no cruza medianoche desde `_BASE_TIME`), así que un único chunk de servidor
    basta (`bars[0].trading_day`).
    """
    if not bars:
        return
    rows = [
        (
            bar.timestamp_utc.astimezone(_ATHENS_SERVER_TZ).replace(tzinfo=None),
            bar.close,
            bar.close,
            bar.close,
        )
        for bar in bars
    ]
    build_server_local_tick_chunk(store, "US500", bars[0].trading_day, rows)


def _simulate_prefix_then_capture(
    prefix_closes: list[float],
    suffix_closes: list[float],
    exhaustion_policy: ExhaustionPolicy = ExhaustionPolicy.HALT_ENTRIES,
) -> tuple[list[LedgerEntry], float]:
    """Procesa el prefijo, captura el estado, y SOLO DESPUÉS alimenta la cola futura."""
    simulator = _build_simulator(exhaustion_policy)
    for bar in _bars(prefix_closes):
        simulator._process_bar(bar)

    snapshot_entries = list(simulator.ledger.entries)
    snapshot_balance = simulator.account.balance

    for bar in _bars(suffix_closes, start_index=len(prefix_closes)):
        simulator._process_bar(bar)

    return snapshot_entries, snapshot_balance


def _simulate_prefix_then_capture_with_athens_ticks(
    prefix_closes: list[float],
    suffix_closes: list[float],
    exhaustion_policy: ExhaustionPolicy = ExhaustionPolicy.HALT_ENTRIES,
) -> tuple[list[LedgerEntry], float]:
    """Análogo a `_simulate_prefix_then_capture`, con `tick_store` poblado (R82).

    El chunk de ticks (`server_tz=Europe/Athens`) se escribe ANTES de simular, con un
    tick por cada barra del prefijo Y de la cola futura (`suffix_closes`) — réplica
    del escenario real: los ticks de todo el día del servidor ya están persistidos
    cuando el `Simulator` procesa la primera barra del día (`RI-G1`, una lectura por
    día). La captura sigue ocurriendo INMEDIATAMENTE tras el prefijo, ANTES de
    alimentar la cola futura al `Simulator`.
    """
    prefix_bars = _bars(prefix_closes)
    suffix_bars = _bars(suffix_closes, start_index=len(prefix_closes))
    profile = replace(load_firm_profile(), server_tz="Europe/Athens")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tick_store = RawParquetStore(Path(tmp_dir))
        _populate_athens_tick_store(tick_store, prefix_bars + suffix_bars)
        simulator = _build_simulator_with_tick_store(tick_store, profile, exhaustion_policy)

        for bar in prefix_bars:
            simulator._process_bar(bar)

        snapshot_entries = list(simulator.ledger.entries)
        snapshot_balance = simulator.account.balance

        for bar in suffix_bars:
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
@pytest.mark.parametrize("exhaustion_policy", list(ExhaustionPolicy))
@given(
    prefix_closes=_closes_strategy,
    suffix_closes_a=_future_closes_strategy,
    suffix_closes_b=_future_closes_strategy,
)
@settings(max_examples=1000, deadline=None)
def test_ledger_hasta_t_no_cambia_si_se_mutan_barras_futuras(
    exhaustion_policy: ExhaustionPolicy,
    prefix_closes: list[float],
    suffix_closes_a: list[float],
    suffix_closes_b: list[float],
) -> None:
    """R52: el ledger/balance hasta `t` es idéntico sin importar qué barras futuras se agreguen.

    PROP-4 (Change #109): la propiedad forward-only sobrevive bajo las dos
    `ExhaustionPolicy` — `RECORD_AND_CONTINUE` no reintroduce dependencia del futuro.
    """
    entries_a, balance_a = _simulate_prefix_then_capture(
        prefix_closes, suffix_closes_a, exhaustion_policy
    )
    entries_b, balance_b = _simulate_prefix_then_capture(
        prefix_closes, suffix_closes_b, exhaustion_policy
    )
    assert entries_a == entries_b
    assert balance_a == pytest.approx(balance_b)


@pytest.mark.timeout(180)
@pytest.mark.parametrize("exhaustion_policy", list(ExhaustionPolicy))
@given(
    prefix_closes=_closes_strategy,
    suffix_closes_a=_future_closes_strategy,
    suffix_closes_b=_future_closes_strategy,
)
@settings(max_examples=1000, deadline=None)
def test_ledger_hasta_t_no_cambia_con_tick_store_poblado_server_tz_no_utc(
    exhaustion_policy: ExhaustionPolicy,
    prefix_closes: list[float],
    suffix_closes_a: list[float],
    suffix_closes_b: list[float],
) -> None:
    """R82: con `tick_store` poblado (`server_tz=Europe/Athens`), el ledger/balance
    capturado inmediatamente tras un prefijo arbitrario de `AnnotatedBar` procesado
    hasta `t` es idéntico entre dos ejecuciones, aunque después se alimenten dos colas
    futuras `suffix_closes_a`/`suffix_closes_b` distintas — barras Y ticks (derivados
    de `bar.close`) con `timestamp_utc > t` — al `Simulator`. PROP-4: bajo las dos
    `ExhaustionPolicy`.
    """
    entries_a, balance_a = _simulate_prefix_then_capture_with_athens_ticks(
        prefix_closes, suffix_closes_a, exhaustion_policy
    )
    entries_b, balance_b = _simulate_prefix_then_capture_with_athens_ticks(
        prefix_closes, suffix_closes_b, exhaustion_policy
    )
    assert entries_a == entries_b
    assert balance_a == pytest.approx(balance_b)
