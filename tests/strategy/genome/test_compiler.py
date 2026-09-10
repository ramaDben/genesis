"""Tests para el compilador de genomas declarativos (T4, R3, R4, A3, A4)."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import StrategyCandidate
from genesis.strategy.factories import CandidateFactory
from genesis.strategy.genome.compiler import compile_genome
from genesis.strategy.genome.errors import MissingAcademicProvenanceError
from genesis.validation.trial_ledger import compute_trial_id

GENOME_YAML_1 = """
metadata:
  id: "CANDIDATE-B1-ORB"
  author: "Gao et al."
  paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"
  economic_rationale: "Desbalance de inventario institucional."
  fidelity: "canonical"

universe:
  symbol: "US500"
  timeframe: "M1"
  session: "US_EQUITY_OPEN"

alpha:
  regime_filter:
    kind: "rvol"
    threshold: 1.0
    lookback_days: 10
  entry_trigger:
    kind: "opening_range_breakout"
    range_minutes: 30

risk_exit:
  kind: "chandelier_trailing"
  params:
    lookback_bars: 22
    atr_multiplier: 3.0
"""

# Mismo contenido con claves invertidas
GENOME_YAML_KEY_ORDER = """
risk_exit:
  params:
    atr_multiplier: 3.0
    lookback_bars: 22
  kind: "chandelier_trailing"

alpha:
  entry_trigger:
    range_minutes: 30
    kind: "opening_range_breakout"
  regime_filter:
    lookback_days: 10
    threshold: 1.0
    kind: "rvol"

universe:
  session: "US_EQUITY_OPEN"
  timeframe: "M1"
  symbol: "US500"

metadata:
  fidelity: "canonical"
  economic_rationale: "Desbalance de inventario institucional."
  paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"
  author: "Gao et al."
  id: "CANDIDATE-B1-ORB"
"""


@pytest.fixture
def us500_figure() -> SymbolFigure:
    return SymbolFigure(
        symbol="US500",
        tick_value=1.0,
        tick_size=0.01,
        volume_step=0.01,
        stops_level=0,
        freeze_level=0,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.5,
        swap_rollover_day=3,
    )


def test_compile_genome_returns_candidate_factory(us500_figure: SymbolFigure):
    factory = compile_genome(GENOME_YAML_1)

    # Criterio A3: Cumple el protocolo CandidateFactory
    assert isinstance(factory, CandidateFactory)
    assert hasattr(factory, "raw_config")
    assert isinstance(factory.raw_config, Mapping)

    candidate = factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params={"risk_pct": 0.01, "atr_stop_frac": 0.5},
    )

    assert isinstance(candidate, StrategyCandidate)
    assert candidate.candidate_id == "CANDIDATE-B1-ORB"
    assert hasattr(candidate, "risk_levels")


def test_compile_genome_trial_id_invariance():
    """Criterio A4: Dos compilaciones con orden de claves distinto producen idéntico trial_id."""
    factory1 = compile_genome(GENOME_YAML_1)
    factory2 = compile_genome(GENOME_YAML_KEY_ORDER)

    dummy_dataset_hash = {"US500": "abcdef123456"}
    firm_hash = "firm_hash_1"
    risk_hash = "risk_hash_1"

    trial_id_1 = compute_trial_id(
        factory1.raw_config,
        dummy_dataset_hash,
        firm_hash,
        risk_hash,
    )
    trial_id_2 = compute_trial_id(
        factory2.raw_config,
        dummy_dataset_hash,
        firm_hash,
        risk_hash,
    )

    assert trial_id_1 == trial_id_2
    assert len(trial_id_1) == 64


def test_compile_genome_rejects_missing_provenance():
    target = 'paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"'
    bad_yaml = GENOME_YAML_1.replace(target, 'paper_ref: ""')
    with pytest.raises(MissingAcademicProvenanceError):
        compile_genome(bad_yaml)

