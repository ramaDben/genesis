"""PRIMER test del Change: `CandidateB` satisface `RiskLevelsProvider` (R50-R52, R81)."""

import pytest

from genesis.backtest.simulator import RiskLevelsProvider
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import CANDIDATE_REGISTRY

pytestmark = pytest.mark.unit


def test_candidate_b_satisface_risk_levels_provider_por_duck_typing(
    us500_figure: SymbolFigure,
) -> None:
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=15,
        risk_pct=0.00375,
    )
    assert isinstance(candidate, RiskLevelsProvider) is True


def test_candidate_id_es_b_y_esta_registrado(us500_figure: SymbolFigure) -> None:
    candidate = CandidateB(
        figure=us500_figure,
        reference_balance=100_000.0,
        n_minutes=15,
        risk_pct=0.00375,
    )
    assert candidate.candidate_id == "B"
    assert "B" in CANDIDATE_REGISTRY
    assert CANDIDATE_REGISTRY["B"] is CandidateB
