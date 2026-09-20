"""Compilador de genomas declarativos a CandidateFactory institucional."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import StrategyCandidate
from genesis.strategy.exit_geometry import ExitGeometry, ExitGeometrySource
from genesis.strategy.genome.candidate import CompiledGenomeCandidate
from genesis.strategy.genome.schema import StrategyGenome, parse_genome


@dataclass(frozen=True, slots=True)
class GenomeCandidateFactory:
    """Fábrica de candidatos compilados compatible con CandidateFactory (R3, R4, ADR-E1).

    Implementa `ExitGeometryProvider` (C2, Change #109, `design.md` §1.4): expone la
    geometría de salida declarada en `risk_exit.params` del genoma, con
    `source=GENOME`, para que `run_wfa` la priorice sobre cualquier config global.
    """

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

    @property
    def exit_geometry(self) -> ExitGeometry:
        """Geometría de salida declarada por el genoma (C2): mapea `risk_exit.params`.

        `lookback_bars -> trailing_lookback`, `atr_multiplier -> trailing_atr_mult`,
        sin cotas (R9, C3): el valor declarado en el YAML es el que se usa, tal cual.
        C1 (`schema.parse_genome`) ya garantiza ambas claves para
        `kind == "chandelier_trailing"`; para cualquier otro `kind`, sin allowlist
        propia todavía, se exige lo mismo acá para no construir una geometría a medias.
        """
        params = self.genome.risk_exit.params
        try:
            return ExitGeometry(
                trailing_lookback=int(params["lookback_bars"]),
                trailing_atr_mult=float(params["atr_multiplier"]),
                source=ExitGeometrySource.GENOME,
            )
        except KeyError as exc:
            message = (
                f"El genoma {self.candidate_id!r} no declara {exc.args[0]!r} en "
                "risk_exit.params; requisito para resolver ExitGeometry (C2, Change #109)."
            )
            raise KeyError(message) from exc


def compile_genome(source: Path | str | Mapping[str, Any]) -> GenomeCandidateFactory:
    """Función pura: compila una especificación declarativa a una fábrica CandidateFactory (R3)."""
    genome = parse_genome(source)
    return GenomeCandidateFactory(
        genome=genome,
        raw_config=genome.raw_config,
        candidate_id=genome.metadata.id,
    )
