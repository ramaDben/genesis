"""Tabla normativa de sesiones de contado por índice y resolución de DST (spec §2.3).

Sin I/O, determinista, no depende de ningún estado externo mutable: toda conversión de
zona horaria usa `zoneinfo` (stdlib) para resolver el desplazamiento DST del **mercado
subyacente** (nunca la zona horaria del operador ni offsets hardcodeados).

Extensión aditiva (Issue D, spec §2.x, §3.1): el universo del Candidato A añade
XAUUSD/EURUSD/GBPUSD/USDJPY, cuya ventana normativa es el solapamiento Londres-NY dado
**directamente en UTC** ("12:00-17:00 UTC aprox."), a diferencia de la tabla de índices
(hora local del mercado subyacente, resuelta vía `zoneinfo`). `FixedUtcWindowSpec` modela
esa ventana fija sin DST por lado (trade-off documentado, spec §8): las 4 `SessionSpec`
existentes y su rama de `session_window` quedan byte-idénticas.
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


@dataclass(frozen=True, slots=True)
class FixedUtcWindowSpec:
    """Ventana de sesión dada directamente en UTC (solapamiento Londres-NY, spec §2.x, R91).

    A diferencia de `SessionSpec` (hora local del mercado subyacente, resuelta vía
    `zoneinfo`), esta ventana es fija todo el año: no distingue horario de verano/
    invierno de Londres ni de Nueva York por separado (trade-off aceptado, spec §8).
    """

    symbol: str
    open_utc: time
    close_utc: time


SESSIONS: Mapping[str, SessionSpec | FixedUtcWindowSpec] = {
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
    "XAUUSD": FixedUtcWindowSpec(symbol="XAUUSD", open_utc=time(12, 0), close_utc=time(17, 0)),
    "EURUSD": FixedUtcWindowSpec(symbol="EURUSD", open_utc=time(12, 0), close_utc=time(17, 0)),
    "GBPUSD": FixedUtcWindowSpec(symbol="GBPUSD", open_utc=time(12, 0), close_utc=time(17, 0)),
    "USDJPY": FixedUtcWindowSpec(symbol="USDJPY", open_utc=time(12, 0), close_utc=time(17, 0)),
    "BTCUSDT": FixedUtcWindowSpec(symbol="BTCUSDT", open_utc=time(13, 30), close_utc=time(20, 0)),
}
"""4 filas normativas del spec §2.3 (índices) + 4 filas del spec §2.x (oro/majors, R92).

Las horas locales de los índices son las de apertura/cierre de la sesión de contado en
el huso horario del mercado subyacente (9:30-16:00 hora de Nueva York para los índices
US, equivalente a 14:30-21:00 UTC en horario estándar; 9:00-17:30 hora de Berlín para
GER40, equivalente a 08:00-16:30 UTC en horario estándar). `session_window` resuelve el
DST vigente para la fecha solicitada vía `zoneinfo`, nunca un offset fijo.

XAUUSD/EURUSD/GBPUSD/USDJPY usan el solapamiento Londres-NY dado directamente en UTC
(12:00-17:00 UTC "aprox.", spec §2.x): una ventana fija sin resolución de DST por lado.
"""


def session_window(symbol: str, session_date: date) -> tuple[datetime, datetime]:
    """Retorna `(open_utc, close_utc)` para `symbol` en `session_date`.

    Despacha por el tipo de la entrada en `SESSIONS` (R93): si es `FixedUtcWindowSpec`,
    construye la ventana combinando `session_date` con las horas directamente en UTC
    (sin `zoneinfo` de mercado subyacente); si es `SessionSpec`, preserva el
    comportamiento exacto anterior (DST resuelto para el mercado subyacente vía
    `zoneinfo`, nunca la zona horaria del sistema operativo ni la del operador, R13,
    R40). Es pura y determinista: la misma entrada produce siempre la misma salida (R15).

    Lanza `KeyError` con las claves válidas en el mensaje si `symbol` no está en
    `SESSIONS` (R94).
    """
    try:
        spec = SESSIONS[symbol]
    except KeyError as exc:
        valid_symbols = ", ".join(sorted(SESSIONS))
        message = (
            f"Símbolo '{symbol}' no soportado por la tabla de sesiones. Válidos: {valid_symbols}."
        )
        raise KeyError(message) from exc

    if isinstance(spec, FixedUtcWindowSpec):
        open_utc = datetime.combine(session_date, spec.open_utc, tzinfo=UTC)
        close_utc = datetime.combine(session_date, spec.close_utc, tzinfo=UTC)
        return open_utc, close_utc

    market_tz = ZoneInfo(spec.market_tz)
    open_local = datetime.combine(session_date, spec.open_local, tzinfo=market_tz)
    close_local = datetime.combine(session_date, spec.close_local, tzinfo=market_tz)
    return open_local.astimezone(UTC), close_local.astimezone(UTC)
