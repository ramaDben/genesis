"""Subsistema de genomas declarativos y compilador de estrategias de Génesis."""

from __future__ import annotations

from genesis.strategy.genome.candidate import CompiledGenomeCandidate
from genesis.strategy.genome.compiler import GenomeCandidateFactory, compile_genome
from genesis.strategy.genome.errors import (
    CompiledCandidateStateError,
    GenomeValidationError,
    MissingAcademicProvenanceError,
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

__all__ = [
    "CompiledCandidateStateError",
    "CompiledGenomeCandidate",
    "GenomeAlpha",
    "GenomeCandidateFactory",
    "GenomeFidelity",
    "GenomeMetadata",
    "GenomeRiskExit",
    "GenomeUniverse",
    "GenomeValidationError",
    "MissingAcademicProvenanceError",
    "StrategyGenome",
    "compile_genome",
    "parse_genome",
]
