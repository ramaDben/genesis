"""Jerarquía de excepciones de dominio de `genesis.data` (capa 1: datos)."""


class GenesisDataError(Exception):
    """Raíz de la jerarquía de excepciones de dominio de `genesis.data`.

    Todas las excepciones específicas de esta capa (``AccountScopeError``,
    ``DayBoundaryError``, ``QualityError``, ``CalendarError``, etc.) heredan de esta
    clase, de modo que el código consumidor puede capturarlas de forma agregada cuando
    lo necesite, sin perder el detalle de la causa concreta en el mensaje.
    """


class AccountScopeError(GenesisDataError):
    """Cuenta con permiso de trading real/challenge detectada al conectar."""
