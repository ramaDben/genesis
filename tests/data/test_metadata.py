"""Tests unitarios de `genesis.data.metadata` (reproducibilidad institucional)."""

from datetime import UTC, datetime

import pytest

from genesis.data.metadata import (
    CONFIG_VERSION,
    ArtifactMetadata,
    current_git_commit,
    sha256_of,
)
from genesis.data.symbols import SymbolFigure

pytestmark = pytest.mark.unit


def test_sha256_of_is_stable_across_calls() -> None:
    payload = b"contenido crudo de un chunk de prueba"
    assert sha256_of(payload) == sha256_of(payload)


def test_sha256_of_differs_for_different_payloads() -> None:
    assert sha256_of(b"x") != sha256_of(b"y")


def test_sha256_of_matches_hashlib_reference() -> None:
    import hashlib

    payload = b"referencia"
    assert sha256_of(payload) == hashlib.sha256(payload).hexdigest()


def test_current_git_commit_returns_non_empty_string() -> None:
    commit = current_git_commit()
    assert isinstance(commit, str)
    assert len(commit) > 0


def _build_metadata() -> ArtifactMetadata:
    return ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=sha256_of(b"chunk"),
        firm_profile_hash=sha256_of(b"profile"),
        time_range=(datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)),
        git_commit="deadbeef",
        symbol_figure=SymbolFigure(
            symbol="US500",
            tick_value=1.0,
            volume_step=0.01,
            stops_level=10,
            freeze_level=5,
            digits=2,
            swap_long=-0.5,
            swap_short=-0.3,
            swap_rollover_day=3,
        ),
    )


def test_artifact_metadata_has_five_reproducibility_fields() -> None:
    metadata = _build_metadata()
    assert metadata.config_version == CONFIG_VERSION
    assert metadata.dataset_hash
    assert metadata.firm_profile_hash
    assert metadata.time_range[0] < metadata.time_range[1]
    assert metadata.git_commit == "deadbeef"


def test_artifact_metadata_json_round_trip() -> None:
    metadata = _build_metadata()
    restored = ArtifactMetadata.from_json(metadata.to_json())
    assert restored == metadata


def test_artifact_metadata_json_contains_reproducibility_fields() -> None:
    raw = _build_metadata().to_json()
    fields = ("config_version", "dataset_hash", "firm_profile_hash", "time_range", "git_commit")
    for field in fields:
        assert field in raw


def test_artifact_metadata_allows_missing_symbol_figure() -> None:
    metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=sha256_of(b"chunk"),
        firm_profile_hash=sha256_of(b"profile"),
        time_range=(datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)),
        git_commit="deadbeef",
    )
    assert metadata.symbol_figure is None
    restored = ArtifactMetadata.from_json(metadata.to_json())
    assert restored == metadata
