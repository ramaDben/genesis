"""API pública re-exportada de `candidate_a`/`candidate_a.smc` (T3.8)."""

import pytest

import genesis.strategy.candidate_a as candidate_a_pkg
import genesis.strategy.candidate_a.smc as smc_pkg

pytestmark = pytest.mark.unit


def test_smc_import_directo_de_la_superficie_publica() -> None:
    from genesis.strategy.candidate_a.smc import (
        SmcEngineState,
        SweepState,
        Timeframe,
        update_smc_engine,
    )

    assert update_smc_engine is not None
    assert SmcEngineState is not None
    assert SweepState is not None
    assert Timeframe is not None


def test_smc_all_es_importable() -> None:
    for name in smc_pkg.__all__:
        assert hasattr(smc_pkg, name)


def test_candidate_a_all_es_importable() -> None:
    for name in candidate_a_pkg.__all__:
        assert hasattr(candidate_a_pkg, name)
