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
