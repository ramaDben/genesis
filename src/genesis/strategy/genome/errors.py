"""Excepciones de dominio para el subsistema de genomas declarativos."""

from __future__ import annotations


class GenomeValidationError(Exception):
    """Error base de validación sintáctica o de tipos en la definición del genoma."""


class MissingAcademicProvenanceError(GenomeValidationError):
    """Error levantado cuando una hipótesis carece de referencia académica o procedencia D1."""


class CompiledCandidateStateError(GenomeValidationError):
    """Invariante interno de una estrategia compilada violado (geometría o ciclo de vida)."""
