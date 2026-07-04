"""Smoke test de `FakeStrategyCandidate` (T9, R38): satisface `StrategyCandidate`."""

from datetime import UTC, datetime

import pytest

from genesis.data.store import AnnotatedBar
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent, StrategyCandidate
from tests.strategy.fakes import FakeStrategyCandidate, make_annotated_bar

pytestmark = pytest.mark.unit


def test_fake_strategy_candidate_satisface_protocolo_runtime_checkable() -> None:
    fake = FakeStrategyCandidate(candidate_id="Z")
    assert isinstance(fake, StrategyCandidate)


def test_fake_strategy_candidate_on_bar_fn_inyectable() -> None:
    def _emit_one(bar: AnnotatedBar) -> list[EntryIntent]:
        return [
            EntryIntent(
                direction=Direction.LONG,
                sizing_hint=0.1,
                candidate_id="Z",
                config_version=CONFIG_VERSION,
            )
        ]

    fake = FakeStrategyCandidate(candidate_id="Z", on_bar_fn=_emit_one)
    bar = make_annotated_bar(datetime(2024, 1, 1, tzinfo=UTC))
    intents = fake.on_bar(bar)
    assert len(intents) == 1
    assert fake.on_bar_calls == [bar]


def test_fake_strategy_candidate_default_on_bar_no_emite_nada() -> None:
    fake = FakeStrategyCandidate()
    bar = make_annotated_bar(datetime(2024, 1, 1, tzinfo=UTC))
    assert fake.on_bar(bar) == []
