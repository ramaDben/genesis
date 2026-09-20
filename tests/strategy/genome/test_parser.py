"""Tests para el parser YAML de genomas y validación de procedencia académica D1."""

from __future__ import annotations

from pathlib import Path

import pytest

from genesis.strategy.genome.errors import (
    GenomeValidationError,
    MissingAcademicProvenanceError,
)
from genesis.strategy.genome.schema import GenomeFidelity, parse_genome

VALID_GENOME_YAML = """
metadata:
  id: "CANDIDATE-B1-ORB"
  author: "Gao et al."
  paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"
  economic_rationale: "Desbalance de inventario institucional en la apertura."
  fidelity: "canonical"

universe:
  symbol: "US500"
  timeframe: "M15"
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


def test_parse_valid_genome_yaml_string():
    genome = parse_genome(VALID_GENOME_YAML)
    assert genome.metadata.id == "CANDIDATE-B1-ORB"
    assert genome.metadata.author == "Gao et al."
    assert genome.metadata.fidelity == GenomeFidelity.CANONICAL
    assert genome.universe.symbol == "US500"
    assert genome.alpha.regime_filter is not None
    assert genome.alpha.regime_filter["threshold"] == 1.0
    assert genome.risk_exit.kind == "chandelier_trailing"
    assert genome.risk_exit.params["atr_multiplier"] == 3.0


def test_parse_valid_genome_from_file(tmp_path: Path):
    yaml_file = tmp_path / "genome.yaml"
    yaml_file.write_text(VALID_GENOME_YAML, encoding="utf-8")

    genome = parse_genome(yaml_file)
    assert genome.metadata.id == "CANDIDATE-B1-ORB"
    assert genome.universe.symbol == "US500"


def test_parse_missing_paper_ref_raises_provenance_error():
    yaml_content = VALID_GENOME_YAML.replace(
        'paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"',
        'paper_ref: ""',
    )
    with pytest.raises(MissingAcademicProvenanceError, match="paper_ref"):
        parse_genome(yaml_content)


def test_parse_invalid_fidelity_raises_provenance_error():
    yaml_content = VALID_GENOME_YAML.replace(
        'fidelity: "canonical"',
        'fidelity: "inventado"',
    )
    with pytest.raises(MissingAcademicProvenanceError, match="fidelity"):
        parse_genome(yaml_content)


def test_parse_missing_metadata_raises_validation_error():
    yaml_content = """
universe:
  symbol: "US500"
  timeframe: "M15"
  session: "US_EQUITY_OPEN"
alpha:
  entry_trigger:
    kind: "orb"
risk_exit:
  kind: "fixed"
  params: {}
"""
    with pytest.raises(GenomeValidationError, match="metadata"):
        parse_genome(yaml_content)


def test_parse_malformed_yaml_raises_validation_error():
    with pytest.raises(GenomeValidationError):
        parse_genome("::: malformed yaml ::: [")


def test_parse_canonical_candidate_b1_spec():
    p = Path("candidates/specs/candidate_b1_orb.yaml")
    genome = parse_genome(p)
    assert genome.metadata.id == "CANDIDATE-B1-ORB"
    assert genome.metadata.fidelity == GenomeFidelity.CANONICAL
    assert genome.universe.symbol == "US500"
    assert genome.alpha.entry_trigger["range_minutes"] == 30
    assert genome.risk_exit.kind == "chandelier_trailing"
