"""Jerarquía de excepciones propia del Candidato A (`candidates.A.*`, R106, R110)."""

from genesis.strategy.errors import GenesisStrategyError


class CandidateAConfigError(GenesisStrategyError):
    """Configuración de `candidates.A.*` inválida o incompleta en `inspector_config.json`.

    El mensaje debe incluir el campo faltante/inválido y la fuente del recurso leído
    (patrón fail-fast de `CandidateBConfigError`, sin degradación silenciosa).
    """


class SmcEngineStateError(GenesisStrategyError):
    """Invariante interna imposible del motor `smc_engine`.

    Se lanza, por ejemplo, cuando se consulta el valor de un `IncrementalAtr` antes de
    su calentamiento (mismo criterio que `CandidateBStateError`). El mensaje debe
    incluir el contexto explícito (campo/valor) que originó la violación.
    """
