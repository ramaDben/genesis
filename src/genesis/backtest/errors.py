"""Jerarquía de excepciones de dominio de `genesis.backtest` (capa 3: backtest).

Raíz independiente de `genesis.strategy.errors.GenesisStrategyError` y de
`genesis.data.errors.GenesisDataError` (ADR-G5, sigue ADR-C4 archivado): no existe una
raíz `GenesisError` compartida entre capas en el repo. Todo mensaje de excepción de esta
capa debe incluir contexto explícito (símbolo, `timestamp`, `candidate_id`, valor
involucrado, R4/R59) — fail-fast, nunca degradación silenciosa.
"""


class GenesisBacktestError(Exception):
    """Raíz de la jerarquía de excepciones de dominio de `genesis.backtest` (capa 3).

    Jerarquía independiente de `genesis.strategy.errors.GenesisStrategyError` y de
    `genesis.data.errors.GenesisDataError` (ADR-G5): no hereda de ninguna de las dos.
    """


class SessionBoundaryError(GenesisBacktestError):
    """Guard defensivo fail-fast: posición del Candidato B viva tras el cierre de sesión.

    Se lanza cuando `bar.timestamp_utc` supera el `close_utc` de `session_window` y aún
    queda una posición abierta pese al cierre forzado proactivo (R23/R24).
    """


class BacktestConfigError(GenesisBacktestError):
    """Configuración inválida o incompleta de la capa 3 (R3).

    Disparadores normativos: (a) ficha de riesgo o de costos inválida/incompleta al
    cargar el recurso empaquetado; (b) el candidato inyectado no implementa
    `RiskLevelsProvider`; (c) el símbolo solicitado no está en la tabla de sesiones
    `genesis.data.sessions.SESSIONS`.
    """
