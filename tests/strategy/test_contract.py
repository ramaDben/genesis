"""Tests unitarios del contrato plugin `StrategyCandidate` (`contract.py`, PA-3)."""

import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from genesis.data.store import AnnotatedBar
from genesis.strategy.contract import (
    CANDIDATE_REGISTRY,
    CONFIG_VERSION,
    Direction,
    EntryIntent,
    StrategyCandidate,
    register_candidate,
)
from genesis.strategy.errors import DuplicateCandidateError

pytestmark = pytest.mark.unit


def test_config_version_normativo() -> None:
    assert CONFIG_VERSION == "genesis-strategy/1"


def test_direction_valores_normativos() -> None:
    assert Direction.LONG == "long"
    assert Direction.SHORT == "short"


def test_entry_intent_tiene_exactamente_cuatro_campos() -> None:
    intent = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="A",
        config_version=CONFIG_VERSION,
    )
    assert intent.direction is Direction.LONG
    assert intent.sizing_hint == 0.1
    assert intent.candidate_id == "A"
    assert intent.config_version == CONFIG_VERSION


def test_entry_intent_es_frozen() -> None:
    intent = EntryIntent(
        direction=Direction.LONG,
        sizing_hint=0.1,
        candidate_id="A",
        config_version=CONFIG_VERSION,
    )
    with pytest.raises(FrozenInstanceError):
        setattr(intent, "sizing_hint", 0.2)  # noqa: B010


class _FakeCandidate:
    """Candidato local mínimo que cumple `StrategyCandidate` (inline, sin fakes.py)."""

    candidate_id = "Z"

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        return []


def test_fake_candidate_satisface_protocolo_runtime_checkable() -> None:
    assert isinstance(_FakeCandidate(), StrategyCandidate)


def test_register_candidate_normaliza_letra_a_mayuscula() -> None:
    CANDIDATE_REGISTRY.pop("Q", None)
    try:

        @register_candidate("q")
        class _Candidate:
            candidate_id = "Q"

            def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
                return []

        assert CANDIDATE_REGISTRY["Q"] is _Candidate
    finally:
        CANDIDATE_REGISTRY.pop("Q", None)


def test_register_candidate_colision_lanza_duplicate_candidate_error() -> None:
    CANDIDATE_REGISTRY.pop("W", None)
    try:

        @register_candidate("w")
        class _CandidateOne:
            candidate_id = "W"

            def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
                return []

        with pytest.raises(DuplicateCandidateError, match="W"):

            @register_candidate("w")
            class _CandidateTwo:
                candidate_id = "W"

                def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
                    return []
    finally:
        CANDIDATE_REGISTRY.pop("W", None)


def test_contract_module_no_importa_inspector_ni_common() -> None:
    source = Path("src/genesis/strategy/contract.py").read_text(encoding="utf-8")
    pattern = (
        r"^(from genesis\.strategy\.(inspector|common)"
        r"|import genesis\.strategy\.(inspector|common))"
    )
    assert not re.search(pattern, source, flags=re.MULTILINE)
