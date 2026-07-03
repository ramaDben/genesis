"""Tabla normativa de sesiones de contado por índice y resolución de DST (spec §2.3).

Sin I/O, determinista, no depende de ningún estado externo mutable: toda conversión de
zona horaria usa `zoneinfo` (stdlib) para resolver el desplazamiento DST del **mercado
subyacente** (nunca la zona horaria del operador ni offsets hardcodeados).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class SessionSpec:
    """Especificación de la sesión de contado de un índice en horario local estándar."""

    symbol: str
    market_tz: str
    open_local: time
    close_local: time


SESSIONS: Mapping[str, SessionSpec] = {
    "US500": SessionSpec(
        symbol="US500",
        market_tz="America/New_York",
        open_local=time(9, 30),
        close_local=time(16, 0),
    ),
    "NAS100": SessionSpec(
        symbol="NAS100",
        market_tz="America/New_York",
        open_local=time(9, 30),
        close_local=time(16, 0),
    ),
    "US30": SessionSpec(
        symbol="US30",
        market_tz="America/New_York",
        open_local=time(9, 30),
        close_local=time(16, 0),
    ),
    "GER40": SessionSpec(
        symbol="GER40",
        market_tz="Europe/Berlin",
        open_local=time(9, 0),
        close_local=time(17, 30),
    ),
}
"""4 filas normativas del spec §2.3.

Las horas locales son las de apertura/cierre de la sesión de contado en el huso horario
del mercado subyacente (9:30–16:00 hora de Nueva York para los índices US, equivalente a
14:30–21:00 UTC en horario estándar; 9:00–17:30 hora de Berlín para GER40, equivalente a
08:00–16:30 UTC en horario estándar). `session_window` resuelve el DST vigente para la
fecha solicitada vía `zoneinfo`, nunca un offset fijo.
"""


def session_window(symbol: str, session_date: date) -> tuple[datetime, datetime]:
    """Retorna `(open_utc, close_utc)` para `symbol` en `session_date`.

    El desplazamiento DST se resuelve para el **mercado subyacente** (`America/New_York`
    o `Europe/Berlin`) usando `zoneinfo`, nunca la zona horaria del sistema operativo ni
    la del operador (R13, R40). Es pura y determinista: la misma entrada produce siempre
    la misma salida (R15).

    Lanza `KeyError` con las claves válidas en el mensaje si `symbol` no está en
    `SESSIONS`.
    """
    try:
        spec = SESSIONS[symbol]
    except KeyError as exc:
        valid_symbols = ", ".join(sorted(SESSIONS))
        message = (
            f"Símbolo '{symbol}' no soportado por la tabla de sesiones. Válidos: {valid_symbols}."
        )
        raise KeyError(message) from exc

    market_tz = ZoneInfo(spec.market_tz)
    open_local = datetime.combine(session_date, spec.open_local, tzinfo=market_tz)
    close_local = datetime.combine(session_date, spec.close_local, tzinfo=market_tz)
    return open_local.astimezone(UTC), close_local.astimezone(UTC)
