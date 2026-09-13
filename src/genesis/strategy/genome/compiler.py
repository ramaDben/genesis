"""Compilador de genomas declarativos a CandidateFactory institucional."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import StrategyCandidate
from genesis.strategy.genome.candidate import CompiledGenomeCandidate
from genesis.strategy.genome.schema import StrategyGenome, parse_genome


@dataclass(frozen=True, slots=True)
class GenomeCandidateFactory:
    """Fábrica de candidatos compilados compatible con CandidateFactory (R3, R4, ADR-E1)."""

    genome: StrategyGenome
    raw_config: Mapping[str, Any]
    candidate_id: str

    def __call__(
        self,
        *,
        figure: SymbolFigure,
        reference_balance: float,
        params: Mapping[str, float] | None = None,
    ) -> StrategyCandidate:
        """Instancia la estrategia ejecutable inyectando los parámetros dados."""
        return CompiledGenomeCandidate(
            self.genome,
            figure=figure,
            reference_balance=reference_balance,
            params=params,
        )


def compile_genome(source: Path | str | Mapping[str, Any]) -> GenomeCandidateFactory:
    """Función pura: compila una especificación declarativa a una fábrica CandidateFactory (R3)."""
    genome = parse_genome(source)
    return GenomeCandidateFactory(
        genome=genome,
        raw_config=genome.raw_config,
        candidate_id=genome.metadata.id,
    )
