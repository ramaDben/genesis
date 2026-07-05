"""Tests de `ledger.py` — registro append-only y `reconstruct_equity_series` (R42–R47)."""

import dataclasses
from datetime import UTC, date, datetime

import pytest

from genesis.backtest.ledger import (
    CONFIG_VERSION,
    BreachEvent,
    BreachKind,
    FillRecord,
    Ledger,
    LedgerEntry,
    RejectionRecord,
    RunProvenance,
    reconstruct_equity_series,
)
from genesis.strategy.contract import Direction
from genesis.strategy.inspector import AUTHORIZED, InspectorVerdict, RejectionReason

pytestmark = pytest.mark.unit

_PROVENANCE = RunProvenance(
    candidate_id="B",
    config_version=CONFIG_VERSION,
    dataset_hash="dataset-hash",
    firm_profile_hash="firm-hash",
    risk_profile_hash="risk-hash",
)


def test_config_version_es_el_normativo() -> None:
    assert CONFIG_VERSION == "genesis-backtest/1"


def test_breach_kind_tiene_exactamente_cuatro_miembros() -> None:
    assert {member.value for member in BreachKind} == {"daily", "total", "news", "weekend"}


def test_breach_event_es_frozen() -> None:
    event = BreachEvent(
        kind=BreachKind.DAILY,
        trading_day=date(2024, 1, 2),
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        magnitude=100.0,
        threshold=50.0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.magnitude = 0.0  # type: ignore[misc]


def test_fill_record_es_frozen() -> None:
    fill = FillRecord(
        candidate_id="B",
        symbol="US500",
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        price=100.0,
        direction=Direction.LONG,
        is_exit=False,
        cost_applied=0.5,
        equity_after=100_000.0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        fill.price = 0.0  # type: ignore[misc]


def test_ledger_entry_es_frozen() -> None:
    fill = FillRecord(
        candidate_id="B",
        symbol="US500",
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        price=100.0,
        direction=Direction.LONG,
        is_exit=False,
        cost_applied=0.5,
        equity_after=100_000.0,
    )
    entry = LedgerEntry(provenance=_PROVENANCE, payload=fill)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.payload = fill  # type: ignore[misc]


def test_breach_event_account_exhausted_solo_true_para_total() -> None:
    daily = BreachEvent(
        kind=BreachKind.DAILY,
        trading_day=date(2024, 1, 2),
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        magnitude=100.0,
        threshold=50.0,
    )
    total = BreachEvent(
        kind=BreachKind.TOTAL,
        trading_day=date(2024, 1, 2),
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        magnitude=1000.0,
        threshold=500.0,
        account_exhausted=True,
    )
    assert daily.account_exhausted is False
    assert total.account_exhausted is True


def test_ledger_append_agrega_entrada_al_final() -> None:
    ledger = Ledger(provenance=_PROVENANCE, entries=[])
    rejection = RejectionRecord(
        candidate_id="B",
        symbol="US500",
        intent_time=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        verdict=InspectorVerdict(
            authorized=False, rejection_reason=RejectionReason.INSUFFICIENT_RR
        ),
    )
    ledger.append(rejection)
    assert len(ledger.entries) == 1
    assert ledger.entries[0].payload is rejection
    assert ledger.entries[0].provenance is _PROVENANCE


def test_reconstruct_equity_series_reproduce_serie_conocida() -> None:
    day_1 = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
    day_1_later = datetime(2024, 1, 2, 16, 0, tzinfo=UTC)
    day_2 = datetime(2024, 1, 3, 15, 0, tzinfo=UTC)

    def _fill(timestamp: datetime, equity_after: float) -> FillRecord:
        return FillRecord(
            candidate_id="B",
            symbol="US500",
            timestamp_utc=timestamp,
            price=100.0,
            direction=Direction.LONG,
            is_exit=True,
            cost_applied=0.5,
            equity_after=equity_after,
        )

    entries = [
        LedgerEntry(provenance=_PROVENANCE, payload=_fill(day_1, 100_100.0)),
        LedgerEntry(
            provenance=_PROVENANCE,
            payload=RejectionRecord(
                candidate_id="B",
                symbol="US500",
                intent_time=day_1_later,
                verdict=AUTHORIZED,
            ),
        ),
        LedgerEntry(provenance=_PROVENANCE, payload=_fill(day_1_later, 100_050.0)),
        LedgerEntry(provenance=_PROVENANCE, payload=_fill(day_2, 99_900.0)),
    ]

    series = reconstruct_equity_series(entries)

    assert series == {
        date(2024, 1, 2): [(day_1, 100_100.0), (day_1_later, 100_050.0)],
        date(2024, 1, 3): [(day_2, 99_900.0)],
    }


def test_reconstruct_equity_series_es_pura_no_muta_entradas() -> None:
    fill = FillRecord(
        candidate_id="B",
        symbol="US500",
        timestamp_utc=datetime(2024, 1, 2, 15, 0, tzinfo=UTC),
        price=100.0,
        direction=Direction.LONG,
        is_exit=True,
        cost_applied=0.5,
        equity_after=100_100.0,
    )
    entries = [LedgerEntry(provenance=_PROVENANCE, payload=fill)]
    reconstruct_equity_series(entries)
    assert entries == [LedgerEntry(provenance=_PROVENANCE, payload=fill)]
