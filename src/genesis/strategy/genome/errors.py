"""Excepciones de dominio para el subsistema de genomas declarativos."""

from __future__ import annotations


class GenomeValidationError(Exception):
    """Error base de validación sintáctica o de tipos en la definición del genoma."""


class MissingAcademicProvenanceError(GenomeValidationError):
    """Error levantado cuando una hipótesis carece de referencia académica o procedencia D1."""


class CompiledCandidateStateError(GenomeValidationError):
    """Invariante interno de una estrategia compilada violado (geometría o ciclo de vida)."""


class UnknownRiskExitParamError(GenomeValidationError):
    """Clave desconocida en `risk_exit.params` para el `kind` declarado (C1, Change #109).

    Única clase de excepción nueva de ese change (`design.md` §5): un genoma que
    declara una clave que el motor no consume debe fallar, no ignorarla en silencio
    (R8, Invariante 3b — un parámetro muerto es una señal corrupta para un arquitecto
    automatizado). El mensaje cita la clave por nombre y enumera las admitidas para el
    `kind`, disparado por `genesis.strategy.genome.schema.parse_genome` cuando
    `risk_exit.params` incluye una clave fuera de la allowlist de su `kind`.
    """
