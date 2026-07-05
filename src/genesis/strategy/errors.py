"""Jerarquía de excepciones de dominio de `genesis.strategy` (capa 2: estrategia)."""


class GenesisStrategyError(Exception):
    """Raíz de la jerarquía de excepciones de dominio de `genesis.strategy`.

    Jerarquía independiente de `genesis.data.errors.GenesisDataError` (ADR-C4): no
    existe una raíz `GenesisError` compartida entre capas en el repo actual.
    """


class LookaheadError(GenesisStrategyError):
    """Se solicitó un instante posterior al `current_time` vigente del reloj (§8).

    El mensaje DEBE incluir el timestamp solicitado y el `t_actual` vigente en el
    momento de la violación (fail-fast con contexto).
    """


class DuplicateCandidateError(GenesisStrategyError):
    """Colisión de letra en `CANDIDATE_REGISTRY`: ya existe un candidato registrado."""


class InspectorConfigError(GenesisStrategyError):
    """Configuración del embudo (`InspectorFunnelConfig`) inválida o incompleta."""


class CandidateBConfigError(GenesisStrategyError):
    """Configuración de `candidates.B.*` inválida o incompleta en `inspector_config.json` (R73).

    El mensaje debe incluir el campo faltante/inválido y la fuente del recurso leído
    (patrón fail-fast de `InspectorConfigError`, sin degradación silenciosa).
    """


class CandidateBStateError(GenesisStrategyError):
    """Invariante interno del Candidato B violado.

    Se lanza cuando `risk_levels()` se invoca sin una señal pendiente (R71) o cuando
    la geometría calculada produce `distancia_stop <= 0` (R67). El mensaje debe
    incluir el contexto explícito (campo/valor) que originó la violación.
    """
