"""Tests unitarios de la API pública re-exportada por `genesis.strategy.__init__` (R46)."""

import pytest

import genesis.strategy as strategy_pkg

pytestmark = pytest.mark.unit

_EXPECTED_ALL = {
    "StrategyCandidate",
    "EntryIntent",
    "Direction",
    "CONFIG_VERSION",
    "register_candidate",
    "CANDIDATE_REGISTRY",
    "GenesisStrategyError",
    "LookaheadError",
    "BarClock",
    "inspect",
    "InspectorVerdict",
    "RejectionReason",
    "InspectorFunnelConfig",
}


def test_all_contiene_exactamente_la_superficie_curada() -> None:
    assert set(strategy_pkg.__all__) == _EXPECTED_ALL


def test_todos_los_nombres_de_all_son_importables() -> None:
    for name in strategy_pkg.__all__:
        assert hasattr(strategy_pkg, name), f"'{name}' está en __all__ pero no es importable"


def test_common_no_se_re_exporta_en_all() -> None:
    leaked_names = {
        "common",
        "vwap_engine",
        "zones",
        "Zone",
        "classify_zone",
        "VwapAnchorConfig",
        "AnchorMode",
        "VWAPState",
        "VWAPResult",
    }
    assert not (leaked_names & set(strategy_pkg.__all__))
