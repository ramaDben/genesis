"""Goldens de `HouseRule` en el `Simulator` (B3, Change #109, DT-3 opción (a)).

Archivo **nuevo**, no un renombre de `tests/backtest/test_risk_profile.py` (H-7,
`tasks.md`): ninguno de los 9 tests de ese archivo era un golden del contrato de la
casa. Contiene G-1 (`MaxLossLimitKind` produce veredictos distintos) y G-4 (la
conversión `STATIC × pct` a monto absoluto es sin pérdida, §D3 del diseño).
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from genesis.backtest.costs import load_costs_config
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.ledger import BreachEvent, BreachKind
from genesis.backtest.simulator import Simulator
from genesis.data.house_rule import HouseRule, MaxLossLimit, MaxLossLimitKind
from genesis.data.profile import load_firm_profile
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0)
_STARTING_BALANCE = 100_000.0

_DAY1 = datetime(2024, 1, 2).date()
_DAY2 = datetime(2024, 1, 3).date()


def _house_rule(kind: MaxLossLimitKind, amount: float = 5_000.0) -> HouseRule:
    return HouseRule(
        max_loss_limit=MaxLossLimit(amount=amount, kind=kind),
        threshold_lock_at=None,
        daily_loss_limit=None,
        consistency_rule=None,
        weekend_holding_allowed=True,
        payout_buffer=0.0,
        min_net_profit_between_payouts=0.0,
        funded_starting_balance=0.0,
        account_size=_STARTING_BALANCE,
    )


def _build_simulator(kind: MaxLossLimitKind, amount: float = 5_000.0) -> Simulator:
    firm_profile = dataclasses.replace(load_firm_profile(), house_rule=_house_rule(kind, amount))
    return Simulator(
        FakeRiskCandidate(),
        symbol="US500",
        firm_profile=firm_profile,
        exit_geometry=load_exit_geometry(),
        figure=_default_symbol_figure("US500"),
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=_STARTING_BALANCE,
        dataset_hash="test-dataset-hash",
    )


def _total_breach_outcome(kind: MaxLossLimitKind) -> tuple[bool, object]:
    """`(ocurrió_breach_total, trading_day)` sobre el mismo fixture de equity fijo (G-1)."""
    simulator = _build_simulator(kind)

    # Bar 1: en medio del día, sube a 110_000 (no es barra de cierre de sesión).
    bar1 = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC), trading_day=_DAY1)
    simulator.account.balance = 110_000.0
    simulator._evaluate_breaches(bar1, [], False)
    if simulator.account.account_exhausted:
        return True, bar1.trading_day

    # Bar 2: cierre de sesión del día 1, retrocede a 104_000 (todavía sobre el inicial).
    bar2_close = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)
    bar2 = make_annotated_bar(
        bar2_close, trading_day=_DAY1, session_close_utc=bar2_close
    )
    simulator.account.balance = 104_000.0
    simulator._evaluate_breaches(bar2, [], False)
    if simulator.account.account_exhausted:
        return True, bar2.trading_day

    # Bar 3: cierre de sesión del día 2, cae a 98_500.
    bar3_close = datetime(2024, 1, 3, 21, 0, tzinfo=UTC)
    bar3 = make_annotated_bar(
        bar3_close, trading_day=_DAY2, session_close_utc=bar3_close
    )
    simulator.account.balance = 98_500.0
    simulator._evaluate_breaches(bar3, [], False)
    return simulator.account.account_exhausted, bar3.trading_day


def test_max_loss_limit_kind_produces_distinct_verdicts() -> None:
    """G-1 (AC3): mismo fixture, tres corridas idénticas salvo `kind` -> veredictos distintos.

    Con un pico intradía de 110_000 seguido de retrocesos parciales, `STATIC` (ancla
    fija en 100_000), `TRAILING_INTRADAY` (sigue el pico de 110_000) y `TRAILING_EOD`
    (sigue solo los cierres de sesión, 104_000) dan umbrales distintos y por lo tanto
    veredictos `(ocurre, trading_day)` distintos en al menos un caso.
    """
    static_outcome = _total_breach_outcome(MaxLossLimitKind.STATIC)
    intraday_outcome = _total_breach_outcome(MaxLossLimitKind.TRAILING_INTRADAY)
    eod_outcome = _total_breach_outcome(MaxLossLimitKind.TRAILING_EOD)

    outcomes = {static_outcome, intraday_outcome, eod_outcome}
    assert len(outcomes) >= 2, (
        f"Los tres kind deberían diferir en al menos un caso: {static_outcome=}, "
        f"{intraday_outcome=}, {eod_outcome=}"
    )
    # Evidencia concreta del defecto que el change corrige: TRAILING_INTRADAY sigue el
    # pico intradía (110_000) y rompe con el retroceso a 104_000, mientras STATIC y
    # TRAILING_EOD (que no vieron ese pico como ancla) no rompen en ese mismo punto.
    assert intraday_outcome[0] is True
    assert static_outcome[0] is False


def test_static_pct_convierte_sin_perdida() -> None:
    """G-4 (D3): `10% STATIC` sobre 100_000 y `amount=10_000.0, STATIC` dan el mismo breach.

    Golden de equivalencia: ambos evaluadores producen exactamente el mismo
    `BreachEvent(TOTAL)` (magnitud y umbral) porque, para `STATIC`, la referencia es
    siempre el balance inicial constante — el pct → monto no pierde información.
    """
    simulator = _build_simulator(MaxLossLimitKind.STATIC, amount=10_000.0)
    simulator.account.balance = 88_000.0
    bar = make_annotated_bar(datetime(2024, 1, 2, 15, 0, tzinfo=UTC))

    simulator._evaluate_breaches(bar, [], False)

    total_events = [
        entry.payload
        for entry in simulator.ledger.entries
        if isinstance(entry.payload, BreachEvent) and entry.payload.kind is BreachKind.TOTAL
    ]
    assert len(total_events) == 1
    # Golden histórico de `test_simulator_breaches.py::test_breach_total_golden_calculado_a_mano`
    # bajo `10% STATIC` sobre 100_000: magnitude=12_000.0, threshold=10_000.0.
    assert total_events[0].magnitude == pytest.approx(12_000.0)
    assert total_events[0].threshold == pytest.approx(10_000.0)
    assert total_events[0].account_exhausted is True
