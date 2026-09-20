"""Tests de `metrics.py` — métricas clásicas y prop, puras sobre un `Ledger` (R48–R50)."""

import copy
from datetime import UTC, datetime

import pytest

from genesis.backtest.ledger import (
    CONFIG_VERSION,
    BreachEvent,
    BreachKind,
    ExhaustionPolicy,
    FillRecord,
    Ledger,
    LedgerEntry,
    RejectionRecord,
    RunProvenance,
)
from genesis.backtest.metrics import (
    intent_authorization_counts,
    ledger_metrics_summary,
    max_concurrent_exposure,
    max_drawdown,
    min_distance_to_daily_limit,
    profit_factor,
    rejection_rate_by_reason,
    sharpe_pointwise,
    win_rate,
    worst_daily_floating_excursion,
)
from genesis.data.profile import load_firm_profile
from genesis.strategy.contract import Direction
from genesis.strategy.inspector import AUTHORIZED, InspectorVerdict, RejectionReason

pytestmark = pytest.mark.unit

_PROVENANCE = RunProvenance(
    candidate_id="B",
    config_version=CONFIG_VERSION,
    dataset_hash="dataset-hash",
    firm_profile_hash="firm-hash",
    exit_geometry_hash="geometry-hash",
    house_rule_hash="house-rule-hash",
    exhaustion_policy=ExhaustionPolicy.HALT_ENTRIES,
)


def _fill(timestamp: datetime, price: float, *, is_exit: bool, equity_after: float) -> FillRecord:
    return FillRecord(
        candidate_id="B",
        symbol="US500",
        timestamp_utc=timestamp,
        price=price,
        direction=Direction.LONG,
        is_exit=is_exit,
        cost_applied=1.0,
        equity_after=equity_after,
    )


def _build_ledger(fills: list[FillRecord]) -> Ledger:
    return Ledger(
        provenance=_PROVENANCE,
        entries=[LedgerEntry(provenance=_PROVENANCE, payload=fill) for fill in fills],
    )


_T0 = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
_T1 = datetime(2024, 1, 2, 15, 5, tzinfo=UTC)
_T2 = datetime(2024, 1, 2, 15, 10, tzinfo=UTC)
_T3 = datetime(2024, 1, 2, 15, 15, tzinfo=UTC)


def test_profit_factor_calculado_a_mano() -> None:
    """Dos trades: +200 ganador, -100 perdedor → PF = 200/100 = 2.0."""
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 102.0, is_exit=True, equity_after=100_199.0),  # +200
            _fill(_T2, 100.0, is_exit=False, equity_after=100_198.0),
            _fill(_T3, 99.0, is_exit=True, equity_after=100_098.0),  # -100
        ]
    )
    assert profit_factor(ledger) == pytest.approx(2.0)


def test_win_rate_calculado_a_mano() -> None:
    """Un exit ganador de dos → win_rate = 0.5."""
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 102.0, is_exit=True, equity_after=100_199.0),
            _fill(_T2, 100.0, is_exit=False, equity_after=100_198.0),
            _fill(_T3, 99.0, is_exit=True, equity_after=100_098.0),
        ]
    )
    assert win_rate(ledger) == pytest.approx(0.5)


def test_max_drawdown_calculado_a_mano() -> None:
    """Equity 99_999 → 100_199 (pico) → 100_098: drawdown máximo = 100_199 - 100_098 = 101."""
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 102.0, is_exit=True, equity_after=100_199.0),
            _fill(_T2, 100.0, is_exit=False, equity_after=100_198.0),
            _fill(_T3, 99.0, is_exit=True, equity_after=100_098.0),
        ]
    )
    assert max_drawdown(ledger) == pytest.approx(101.0)


def test_sharpe_pointwise_sin_suficientes_datos_retorna_cero() -> None:
    ledger = _build_ledger([_fill(_T0, 100.0, is_exit=False, equity_after=99_999.0)])
    assert sharpe_pointwise(ledger) == 0.0


def test_worst_daily_floating_excursion_calculado_a_mano() -> None:
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=BreachEvent(
                kind=BreachKind.DAILY,
                trading_day=_T0.date(),
                timestamp_utc=_T0,
                magnitude=3_000.0,
                threshold=5_000.0,
            ),
        ),
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=BreachEvent(
                kind=BreachKind.DAILY,
                trading_day=_T1.date(),
                timestamp_utc=_T1,
                magnitude=6_500.0,
                threshold=5_000.0,
            ),
        ),
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)
    assert worst_daily_floating_excursion(ledger) == pytest.approx(6_500.0)


def test_worst_daily_floating_excursion_sin_breaches_es_cero() -> None:
    ledger = Ledger(provenance=_PROVENANCE, entries=[])
    assert worst_daily_floating_excursion(ledger) == 0.0


def test_min_distance_to_daily_limit_calculado_a_mano() -> None:
    firm_profile = load_firm_profile()
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=BreachEvent(
                kind=BreachKind.DAILY,
                trading_day=_T0.date(),
                timestamp_utc=_T0,
                magnitude=6_000.0,
                threshold=5_000.0,
            ),
        ),
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)
    assert min_distance_to_daily_limit(ledger, firm_profile) == pytest.approx(-1_000.0)


def test_min_distance_to_daily_limit_sin_breaches_usa_el_monto_del_dll_de_la_ficha() -> None:
    """`house_rule.daily_loss_limit.amount` reemplaza al `daily_loss_limit_pct` eliminado."""
    firm_profile = load_firm_profile()
    assert firm_profile.house_rule is not None
    assert firm_profile.house_rule.daily_loss_limit is not None
    ledger = Ledger(provenance=_PROVENANCE, entries=[])
    assert min_distance_to_daily_limit(ledger, firm_profile) == pytest.approx(
        firm_profile.house_rule.daily_loss_limit.amount
    )


def test_min_distance_to_daily_limit_sin_dll_en_el_contrato_retorna_none() -> None:
    """Eval DT-2 (B3b): sin `daily_loss_limit` en la ficha, `None` — sin inventar un número."""
    import dataclasses

    firm_profile = load_firm_profile()
    assert firm_profile.house_rule is not None
    firm_profile_sin_dll = dataclasses.replace(
        firm_profile,
        house_rule=dataclasses.replace(firm_profile.house_rule, daily_loss_limit=None),
    )
    ledger = Ledger(provenance=_PROVENANCE, entries=[])
    assert min_distance_to_daily_limit(ledger, firm_profile_sin_dll) is None


def test_max_concurrent_exposure_calculado_a_mano() -> None:
    """Dos entradas abiertas simultáneamente antes de cerrar → exposición máxima = 2."""
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 101.0, is_exit=False, equity_after=99_997.0),
            _fill(_T2, 102.0, is_exit=True, equity_after=100_100.0),
            _fill(_T3, 103.0, is_exit=True, equity_after=100_300.0),
        ]
    )
    assert max_concurrent_exposure(ledger) == 2


def test_rejection_rate_by_reason_agrega_rejection_reason_y_breach_kind() -> None:
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=RejectionRecord(
                candidate_id="B",
                symbol="US500",
                intent_time=_T0,
                verdict=InspectorVerdict(
                    authorized=False, rejection_reason=RejectionReason.INSUFFICIENT_RR
                ),
            ),
        ),
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=RejectionRecord(
                candidate_id="B", symbol="US500", intent_time=_T1, verdict=AUTHORIZED
            ),
        ),
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=BreachEvent(
                kind=BreachKind.NEWS,
                trading_day=_T2.date(),
                timestamp_utc=_T2,
                magnitude=60.0,
                threshold=0.0,
            ),
        ),
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)
    rates = rejection_rate_by_reason(ledger)
    assert rates["insufficient_rr"] == pytest.approx(1 / 3)
    assert rates["news"] == pytest.approx(1 / 3)


def test_rejection_rate_by_reason_sin_entradas_retorna_diccionario_vacio() -> None:
    ledger = Ledger(provenance=_PROVENANCE, entries=[])
    assert rejection_rate_by_reason(ledger) == {}


def test_ninguna_funcion_muta_el_ledger_recibido() -> None:
    firm_profile = load_firm_profile()
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 102.0, is_exit=True, equity_after=100_199.0),
        ]
    )
    snapshot = copy.deepcopy(ledger)

    profit_factor(ledger)
    win_rate(ledger)
    max_drawdown(ledger)
    sharpe_pointwise(ledger)
    worst_daily_floating_excursion(ledger)
    min_distance_to_daily_limit(ledger, firm_profile)
    max_concurrent_exposure(ledger)
    rejection_rate_by_reason(ledger)

    assert ledger == snapshot


def test_ledger_metrics_summary_coincide_bit_a_bit_con_las_metricas_individuales() -> None:
    """Una pasada y cuatro pasadas dan exactamente el mismo valor (R52 del Change #46).

    Igualdad exacta, no `approx`: ambas rutas aplican la misma fórmula sobre la misma
    secuencia en el mismo orden, así que ni el último bit puede moverse. Si esto pasara
    a fallar por redondeo, sería porque alguien reordenó una acumulación de floats.
    """
    ledger = _build_ledger(
        [
            _fill(_T0, 100.0, is_exit=False, equity_after=99_999.0),
            _fill(_T1, 102.0, is_exit=True, equity_after=100_199.0),
            _fill(_T2, 100.0, is_exit=False, equity_after=100_198.0),
            _fill(_T3, 99.0, is_exit=True, equity_after=100_098.0),
        ]
    )

    summary = ledger_metrics_summary(ledger)

    assert summary.profit_factor == profit_factor(ledger)
    assert summary.sharpe_pointwise == sharpe_pointwise(ledger)
    assert summary.max_drawdown == max_drawdown(ledger)
    assert summary.win_rate == win_rate(ledger)


def test_ledger_metrics_summary_sobre_ledger_vacio_no_revienta() -> None:
    """Sin fills, las cuatro métricas caen a sus valores neutros, igual que las públicas."""
    ledger = _build_ledger([])

    summary = ledger_metrics_summary(ledger)

    assert summary.profit_factor == profit_factor(ledger)
    assert summary.sharpe_pointwise == sharpe_pointwise(ledger)
    assert summary.max_drawdown == max_drawdown(ledger)
    assert summary.win_rate == win_rate(ledger)


def _rejection(timestamp: datetime, reason: RejectionReason) -> RejectionRecord:
    return RejectionRecord(
        candidate_id="B",
        symbol="US500",
        intent_time=timestamp,
        verdict=InspectorVerdict(authorized=False, rejection_reason=reason),
    )


def test_intent_authorization_counts_rechazo_total() -> None:
    """A1 (Change #51): 24 rechazos por sizing y 0 fills → todo lo rechazado es sizing."""
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=_rejection(_T0, RejectionReason.LOT_SIZE_OUT_OF_BOUNDS),
        )
        for _ in range(24)
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)

    counts = intent_authorization_counts(ledger)

    assert counts.intents_authorized == 0
    assert counts.intents_total == 24
    assert counts.rejections_by_reason == {"lot_size_out_of_bounds": 24}


def test_intent_authorization_counts_ledger_vacio() -> None:
    ledger = Ledger(provenance=_PROVENANCE, entries=[])

    counts = intent_authorization_counts(ledger)

    assert counts.intents_authorized == 0
    assert counts.intents_total == 0
    assert counts.rejections_by_reason == {}


def test_intent_authorization_counts_breach_y_exit_no_cuentan_como_intents() -> None:
    """`BreachEvent` no es un intent propuesto; `FillRecord(is_exit=True)` no es entrada."""
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=BreachEvent(
                kind=BreachKind.NEWS,
                trading_day=_T0.date(),
                timestamp_utc=_T0,
                magnitude=60.0,
                threshold=0.0,
            ),
        ),
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=_fill(_T1, 100.0, is_exit=True, equity_after=100_000.0),
        ),
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)

    counts = intent_authorization_counts(ledger)

    assert counts.intents_total == 0
    assert counts.intents_authorized == 0
    assert counts.rejections_by_reason == {}


def test_intent_authorization_counts_rejection_reason_none_cuenta_como_unknown() -> None:
    """`rejection_reason=None` (estado imposible por invariante) se cuenta como `unknown`."""
    entries = [
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=RejectionRecord(
                candidate_id="B", symbol="US500", intent_time=_T0, verdict=AUTHORIZED
            ),
        )
    ]
    ledger = Ledger(provenance=_PROVENANCE, entries=entries)

    counts = intent_authorization_counts(ledger)

    assert counts.intents_total == 1
    assert counts.rejections_by_reason == {"unknown": 1}
