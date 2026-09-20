"""Tests unitarios para el esquema del genoma declarativo y excepciones de dominio."""

from __future__ import annotations

import pytest

from genesis.strategy.genome.errors import (
    GenomeValidationError,
    MissingAcademicProvenanceError,
    UnknownRiskExitParamError,
)
from genesis.strategy.genome.schema import (
    GenomeAlpha,
    GenomeFidelity,
    GenomeMetadata,
    GenomeRiskExit,
    GenomeUniverse,
    StrategyGenome,
    parse_genome,
)

_VALID_GENOME_YAML = """
metadata:
  id: "CANDIDATE-C1-TEST"
  author: "Gao et al."
  paper_ref: "SSRN:12345"
  economic_rationale: "Desbalance institucional de apertura."
  fidelity: "canonical"
universe:
  symbol: "US500"
  timeframe: "M15"
  session: "US_EQUITY_OPEN"
alpha:
  entry_trigger:
    kind: "opening_range_breakout"
    range_minutes: 30
risk_exit:
  kind: "chandelier_trailing"
  params:
    lookback_bars: 22
    atr_multiplier: 3.0
"""


def test_genome_fidelity_enum_values():
    assert GenomeFidelity.CANONICAL == "canonical"
    assert GenomeFidelity.INTERPRETED == "interpreted"
    assert GenomeFidelity.OPTIMIZED == "optimized"
    assert GenomeFidelity.COMBINED == "combined"


def test_strategy_genome_immutability():
    metadata = GenomeMetadata(
        id="CANDIDATE-B1",
        author="Gao et al.",
        paper_ref="SSRN:12345",
        economic_rationale="Desbalance institucional de apertura.",
        fidelity=GenomeFidelity.CANONICAL,
    )
    universe = GenomeUniverse(
        symbol="US500",
        timeframe="M15",
        session="US_EQUITY_OPEN",
    )
    alpha = GenomeAlpha(
        regime_filter={"kind": "rvol", "threshold": 1.0},
        entry_trigger={"kind": "opening_range_breakout", "range_minutes": 30},
    )
    risk_exit = GenomeRiskExit(
        kind="chandelier_trailing",
        params={"lookback_bars": 22, "atr_multiplier": 3.0},
    )
    genome = StrategyGenome(
        metadata=metadata,
        universe=universe,
        alpha=alpha,
        risk_exit=risk_exit,
        raw_config={"foo": "bar"},
    )

    assert genome.metadata.id == "CANDIDATE-B1"
    assert genome.universe.symbol == "US500"
    assert genome.metadata.fidelity == GenomeFidelity.CANONICAL

    # Inmutabilidad (frozen=True)
    with pytest.raises(AttributeError):
        setattr(genome.metadata, "id", "MUTATED")  # noqa: B010

    with pytest.raises(AttributeError):
        setattr(genome.universe, "symbol", "US100")  # noqa: B010


def test_domain_exceptions_hierarchy():
    assert issubclass(GenomeValidationError, Exception)
    assert issubclass(MissingAcademicProvenanceError, GenomeValidationError)
    assert issubclass(UnknownRiskExitParamError, GenomeValidationError)

    err = MissingAcademicProvenanceError("Falta paper_ref obligatorio")
    assert isinstance(err, GenomeValidationError)
    assert "Falta paper_ref" in str(err)


def test_unknown_risk_exit_param_rejected() -> None:
    """Eval U7 (AC7, C1): clave desconocida en `risk_exit.params` -> `UnknownRiskExitParamError`."""
    yaml_content = _VALID_GENOME_YAML.replace(
        "    atr_multiplier: 3.0", "    atr_multiplier: 3.0\n    foo_bar: 1.0"
    )
    with pytest.raises(UnknownRiskExitParamError) as excinfo:
        parse_genome(yaml_content)
    assert "foo_bar" in str(excinfo.value)


def test_chandelier_sin_atr_multiplier_falla() -> None:
    """Eval U8 (AC7, R7): `chandelier_trailing` sin `atr_multiplier` -> falla nombrando la clave."""
    yaml_content = _VALID_GENOME_YAML.replace("    atr_multiplier: 3.0\n", "")
    with pytest.raises(GenomeValidationError, match="atr_multiplier"):
        parse_genome(yaml_content)


def test_chandelier_sin_lookback_bars_falla() -> None:
    yaml_content = _VALID_GENOME_YAML.replace("    lookback_bars: 22\n", "")
    with pytest.raises(GenomeValidationError, match="lookback_bars"):
        parse_genome(yaml_content)
