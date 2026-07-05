"""Excepciones de dominio del Candidato B: `CandidateBConfigError`/`CandidateBStateError` (T1).

Extensión aditiva de `genesis.strategy.errors` (R76, R77): ambas heredan de
`GenesisStrategyError` y conservan el contexto explícito del mensaje (fail-fast).
"""

import pytest

from genesis.strategy.errors import (
    CandidateBConfigError,
    CandidateBStateError,
    GenesisStrategyError,
)

pytestmark = pytest.mark.unit


def test_candidate_b_config_error_hereda_de_genesis_strategy_error() -> None:
    assert issubclass(CandidateBConfigError, GenesisStrategyError) is True


def test_candidate_b_state_error_hereda_de_genesis_strategy_error() -> None:
    assert issubclass(CandidateBStateError, GenesisStrategyError) is True


def test_candidate_b_config_error_conserva_el_contexto_del_mensaje() -> None:
    err = CandidateBConfigError("falta el campo 'n_minutes' en candidates.B.*")
    assert "n_minutes" in str(err)


def test_candidate_b_state_error_conserva_el_contexto_del_mensaje() -> None:
    err = CandidateBStateError("distancia_stop<=0 (entry_reference=4506.2, stop_loss=4506.2)")
    assert "4506.2" in str(err)
