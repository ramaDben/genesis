"""Tests de la jerarquía de excepciones propia del Candidato A (T2.1)."""

import pytest

from genesis.strategy.candidate_a.errors import CandidateAConfigError, SmcEngineStateError
from genesis.strategy.errors import GenesisStrategyError

pytestmark = pytest.mark.unit


def test_candidate_a_config_error_hereda_de_genesis_strategy_error() -> None:
    assert issubclass(CandidateAConfigError, GenesisStrategyError)


def test_smc_engine_state_error_hereda_de_genesis_strategy_error() -> None:
    assert issubclass(SmcEngineStateError, GenesisStrategyError)
