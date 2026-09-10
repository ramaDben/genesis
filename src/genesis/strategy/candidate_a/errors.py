"""Jerarquía de excepciones propia del Candidato A (`candidates.A.*`, R106, R110)."""

from genesis.strategy.common.errors import IncrementalAtrStateError
from genesis.strategy.errors import GenesisStrategyError


class CandidateAConfigError(GenesisStrategyError):
    """Configuración de `candidates.A.*` inválida o incompleta en `inspector_config.json`.

    El mensaje debe incluir el campo faltante/inválido y la fuente del recurso leído
    (patrón fail-fast de `CandidateBConfigError`, sin degradación silenciosa).
    """


# Alias del error de estado para preservar compatibilidad con código existente
SmcEngineStateError = IncrementalAtrStateError
