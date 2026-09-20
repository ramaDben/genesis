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


class CandidateFactoryError(GenesisStrategyError):
    """No se pudo construir un candidato desde parámetros nombrados (`factories.py`).

    Cubre los dos fallos de la costura de inyección: `candidate_id` sin fábrica por
    defecto registrada, y `params` al que le falta una clave que la fábrica exige. El
    mensaje debe nombrar el `candidate_id` y la clave/fábricas disponibles — nunca un
    `KeyError` opaco aguas adentro.
    """


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


class ExitGeometryConfigError(GenesisStrategyError):
    """Estado imposible en `ExitGeometry`: `trailing_lookback < 1` o `trailing_atr_mult <= 0.0`.

    Vive en capa 2 porque `ExitGeometry` vive en capa 2 (Change #109, §1.2): el
    contenedor no puede lanzar `BacktestConfigError` sin importar capa 3 y recrear
    la arista inversa que la mudanza vino a eliminar. ADR-G5 prohíbe una raíz
    compartida entre capas, así que la validación estructural necesita su propio
    error de dominio aquí.

    Quien carga la geometría desde el recurso empaquetado —`load_exit_geometry`,
    que se queda en capa 3 junto al fallback `source=CONFIG`— atrapa este error y
    lo relanza como `BacktestConfigError`: el contrato de la capa 3 no cambia.
    El mensaje debe incluir el valor recibido (fail-fast con contexto).
    """
