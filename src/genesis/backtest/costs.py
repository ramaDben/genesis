"""Modelo de costos por instrumento con `stress` de primera clase (R37–R41; Change #135).

Los costos viven en una **tabla con una fila por símbolo** (`CostsConfig` de filas
`InstrumentCosts`): comisión ida y vuelta en USD por contrato, spread de entrada y
deslizamiento por pata en ticks, la marca de procedencia de la fricción y la fuente con su
fecha de lectura. No hay valor de respaldo: un símbolo sin fila no tiene costos, y sin costos
no hay reporte (R40). La comisión se cobra por pata (la mitad del ida y vuelta en cada una).

Funciones puras sobre `SymbolFigure`/`CostsConfig`/`TickRow`; ninguna hace I/O salvo
`load_costs_config` al leer el archivo. Solo stdlib (R41): sin `scipy`/`statsmodels`/
`matplotlib`/`quantstats`. La validación no toca la red ni el reloj.
"""

import hashlib
import json
import math
import re
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from importlib import resources
from operator import attrgetter
from pathlib import Path
from urllib.parse import urlsplit

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import TickRow
from genesis.data.symbols import SymbolFigure

_CONFIG_PACKAGE = "genesis.backtest"
_CONFIG_RESOURCE = "costs_config.json"

_ROW_FIELDS = (
    "round_trip_usd",
    "spread_ticks",
    "slippage_ticks",
    "friction_status",
    "source_url",
    "read_on",
)
_SYMBOL_RULE = "debe ser una cadena no vacía sin espacios en los extremos"
_READ_ON_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class FrictionStatus(StrEnum):
    """Procedencia de `spread_ticks`/`slippage_ticks` (R1). Conjunto cerrado: B.4b lo amplía."""

    PROVISIONAL_HASTA_B4B = "provisional_hasta_b4b"


def _invalid_field(symbol: object, field: str, value: object, rule: str) -> BacktestConfigError:
    return BacktestConfigError(
        f"InstrumentCosts(symbol={symbol!r}): {field}={value!r} inválido: {rule}"
    )


def _finite_number(symbol: str, field: str, value: object, *, positive: bool) -> float:
    """Valida un campo numérico de la fila y lo normaliza a `float` (sin `-0.0`)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _invalid_field(symbol, field, value, "debe ser un número (int o float), no bool")
    number = float(value) + 0.0
    if not math.isfinite(number):
        raise _invalid_field(symbol, field, value, "debe ser finito")
    if positive and number <= 0:
        raise _invalid_field(symbol, field, value, "debe ser > 0")
    if not positive and number < 0:
        raise _invalid_field(symbol, field, value, "debe ser >= 0")
    return number


@dataclass(frozen=True, slots=True)
class InstrumentCosts:
    """Fila de costos de un símbolo (R1), validada al construirse (R3).

    `round_trip_usd`: USD por contrato, ida y vuelta, tal como lo publica la firma.
    `spread_ticks`: spread de entrada, en ticks. `slippage_ticks`: deslizamiento por pata, en
    ticks. `friction_status`: procedencia de las dos cifras en ticks. `source_url`/`read_on`:
    fuente primaria de `round_trip_usd` y fecha de su lectura (`YYYY-MM-DD`).
    """

    symbol: str
    round_trip_usd: float
    spread_ticks: float
    slippage_ticks: float
    friction_status: FrictionStatus
    source_url: str
    read_on: str

    def __post_init__(self) -> None:
        symbol = self.symbol
        if not isinstance(symbol, str) or not symbol or symbol != symbol.strip():
            raise _invalid_field(symbol, "symbol", symbol, _SYMBOL_RULE)
        round_trip = _finite_number(symbol, "round_trip_usd", self.round_trip_usd, positive=True)
        spread = _finite_number(symbol, "spread_ticks", self.spread_ticks, positive=False)
        slippage = _finite_number(symbol, "slippage_ticks", self.slippage_ticks, positive=False)
        object.__setattr__(self, "round_trip_usd", round_trip)
        object.__setattr__(self, "spread_ticks", spread)
        object.__setattr__(self, "slippage_ticks", slippage)

        status = self.friction_status
        allowed = [member.value for member in FrictionStatus]
        if not isinstance(status, str) or status not in allowed:
            raise _invalid_field(symbol, "friction_status", status, f"debe ser uno de {allowed!r}")
        object.__setattr__(self, "friction_status", FrictionStatus(status))

        url = self.source_url
        if (
            not isinstance(url, str)
            or not url
            or url != url.strip()
            or not url.startswith("https://")
            or not urlsplit(url).hostname
        ):
            raise _invalid_field(
                symbol, "source_url", url, "debe ser una URL https:// con host, sin espacios"
            )

        read_on = self.read_on
        if not isinstance(read_on, str) or not _READ_ON_PATTERN.fullmatch(read_on):
            raise _invalid_field(symbol, "read_on", read_on, "debe tener el formato YYYY-MM-DD")
        try:
            date.fromisoformat(read_on)
        except ValueError as exc:
            raise _invalid_field(
                symbol, "read_on", read_on, f"no es una fecha del calendario ({exc})"
            ) from exc


def _missing_row_error(symbol: str, available: Sequence[str]) -> BacktestConfigError:
    """Mensaje único de R9: símbolo, símbolos con fila y ausencia de respaldo (D3)."""
    return BacktestConfigError(
        f"symbol={symbol!r} no tiene fila en la tabla de costos por instrumento. "
        f"Símbolos con fila: {list(available)!r}. "
        "Sin valor de respaldo: un símbolo sin fila no tiene costos, y sin costos no hay "
        "reporte (B.4a; R40 de backtest)."
    )


@dataclass(frozen=True, slots=True)
class CostsConfig:
    """Tabla de costos por instrumento (R1, R12): tupla ordenada por símbolo, única, no vacía.

    Inmutable, hasheable y comparable por valor: construirla con otro orden de filas da la
    misma tabla. La única consulta por símbolo es `instrument`, que falla si no hay fila (R4).
    """

    instruments: tuple[InstrumentCosts, ...]

    def __post_init__(self) -> None:
        raw = self.instruments
        if isinstance(raw, str | bytes) or not isinstance(raw, Iterable):
            raise BacktestConfigError(
                f"CostsConfig: instruments={raw!r} inválido: debe ser una colección de filas"
            )
        rows = tuple(raw)
        for row in rows:
            if not isinstance(row, InstrumentCosts):
                raise BacktestConfigError(
                    f"CostsConfig: fila {row!r} inválida: debe ser InstrumentCosts"
                )
        if not rows:
            raise BacktestConfigError("CostsConfig: la tabla de costos no puede estar vacía")
        symbols = [row.symbol for row in rows]
        repeated = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
        if repeated:
            raise BacktestConfigError(f"CostsConfig: símbolos repetidos en la tabla: {repeated!r}")
        object.__setattr__(self, "instruments", tuple(sorted(rows, key=attrgetter("symbol"))))

    @property
    def symbols(self) -> tuple[str, ...]:
        """Símbolos con fila, en orden."""
        return tuple(row.symbol for row in self.instruments)

    def instrument(self, symbol: str) -> InstrumentCosts:
        """Fila de `symbol` (comparación exacta); `BacktestConfigError` si no tiene (R9)."""
        for row in self.instruments:
            if row.symbol == symbol:
                return row
        raise _missing_row_error(symbol, self.symbols)


def spread_for(
    symbol: str,
    timestamp: datetime,
    figure: SymbolFigure,
    ticks_window: Sequence[TickRow] | None,
    config: CostsConfig,
    *,
    stress: float = 1.0,
) -> float:
    """Spread de entrada para `symbol`, en puntos de precio (R37; R6 de Change #135).

    Resuelve la fila del símbolo siempre primero, haya o no ticks, para que la falla por
    símbolo sin fila no dependa de la cobertura del día. Con ventana de ticks no vacía devuelve
    la mediana de `ask - bid`; sin ventana, `spread_ticks * figure.tick_size`. En ambos casos
    multiplicado por `stress`. `timestamp` se conserva en la firma para extensión futura.
    """
    del timestamp
    row = config.instrument(symbol)
    if ticks_window:
        base = statistics.median(tick.ask - tick.bid for tick in ticks_window)
    else:
        base = row.spread_ticks * figure.tick_size
    return base * stress


def commission_for(
    symbol: str, sizing_hint: float, config: CostsConfig, *, stress: float = 1.0
) -> float:
    """Comisión de **una pata** en USD: la mitad del ida y vuelta de la fila (R37; R5).

    Se evalúa `round_trip_usd / 2 * sizing_hint * stress`, en ese orden y sin redondeo, para
    que la pata de apertura más la de cierre sumen exactamente el ida y vuelta.
    """
    return config.instrument(symbol).round_trip_usd / 2 * sizing_hint * stress


def slippage_for(
    symbol: str, figure: SymbolFigure, config: CostsConfig, *, stress: float = 1.0
) -> float:
    """Deslizamiento de **una pata**, en puntos de precio: `slippage_ticks * tick_size` (R7)."""
    return config.instrument(symbol).slippage_ticks * figure.tick_size * stress


def swap_for(
    symbol: str,
    days_held: int,
    figure: SymbolFigure,
    is_long: bool,
    *,
    stress: float = 1.0,
) -> float:
    """Costo de swap por tenencia nocturna, con triple rollover (R37).

    Aplica factor triple cuando `days_held` cruza `figure.swap_rollover_day` (miércoles
    MT5), usando `figure.swap_long`/`figure.swap_short` según `is_long`. `symbol` se
    conserva en la firma para futura extensión sin romper el contrato.
    """
    del symbol
    base = figure.swap_long if is_long else figure.swap_short
    multiplier = 3.0 if days_held == figure.swap_rollover_day else 1.0
    return base * multiplier * stress


def costs_hash(symbol: str, config: CostsConfig) -> str:
    """Huella SHA-256 de los costos de `symbol` (R13), para la identidad de corrida y ensayo.

    Entran solo los tres números que determinan la simulación (`round_trip_usd`,
    `spread_ticks`, `slippage_ticks`), normalizados a `float` sin `-0.0`, serializados con
    `json.dumps(..., ensure_ascii=False, sort_keys=True)` como `exit_geometry_hash`. No entran
    `source_url`, `read_on`, `friction_status` ni el símbolo: releer la fuente sin que el
    número cambie no es otro ensayo. Un símbolo sin fila falla según R9.
    """
    row = config.instrument(symbol)
    payload = {
        "round_trip_usd": float(row.round_trip_usd) + 0.0,
        "slippage_ticks": float(row.slippage_ticks) + 0.0,
        "spread_ticks": float(row.spread_ticks) + 0.0,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """`object_pairs_hook` que rechaza claves repetidas en cualquier objeto del JSON (T-f)."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BacktestConfigError(f"clave duplicada {key!r} en un objeto del JSON")
        result[key] = value
    return result


def _parse_table(payload: object) -> CostsConfig:
    """Valida la estructura del JSON en el orden de D7 y construye la tabla."""
    if not isinstance(payload, dict):
        raise BacktestConfigError(
            f"la raíz debe ser un objeto JSON, se recibió {type(payload).__name__}"
        )
    unknown = sorted(key for key in payload if key != "instruments" and not key.startswith("_"))
    if unknown:
        raise BacktestConfigError(
            f"claves desconocidas en la raíz: {unknown!r}. El formato anterior a B.4a (valores "
            "globales para todos los símbolos) ya no se admite: los costos van en "
            "`instruments`, una fila por símbolo con su fuente."
        )
    if "instruments" not in payload:
        raise BacktestConfigError("falta la clave `instruments`")
    instruments = payload["instruments"]
    if not isinstance(instruments, dict):
        raise BacktestConfigError(
            f"`instruments` debe ser un objeto JSON, se recibió {type(instruments).__name__}"
        )
    if not instruments:
        raise BacktestConfigError("`instruments` está vacío")

    rows: list[InstrumentCosts] = []
    for symbol in sorted(instruments):
        if not symbol or symbol != symbol.strip():
            raise _invalid_field(symbol, "symbol", symbol, _SYMBOL_RULE)
        fields = instruments[symbol]
        if not isinstance(fields, dict):
            raise _invalid_field(symbol, "fila", fields, "debe ser un objeto JSON")
        extra = sorted(key for key in fields if key not in _ROW_FIELDS)
        if extra:
            raise _invalid_field(symbol, "claves", extra, f"desconocidas; se esperan {_ROW_FIELDS}")
        missing = [key for key in _ROW_FIELDS if key not in fields]
        if missing:
            raise _invalid_field(symbol, "claves", missing, "faltan en la fila")
        rows.append(
            InstrumentCosts(
                symbol=symbol,
                round_trip_usd=fields["round_trip_usd"],
                spread_ticks=fields["spread_ticks"],
                slippage_ticks=fields["slippage_ticks"],
                friction_status=fields["friction_status"],
                source_url=fields["source_url"],
                read_on=fields["read_on"],
            )
        )
    return CostsConfig(instruments=tuple(rows))


def load_costs_config(path: Path | None = None) -> CostsConfig:
    """Carga la tabla de costos desde `path`, o desde el recurso empaquetado (R39; D7).

    `path=None` -> recurso empaquetado `genesis.backtest/costs_config.json`. Valida en orden
    determinista y se detiene en el primer error, con `BacktestConfigError` que cita la fuente,
    el símbolo, el campo y el valor recibido. Rechaza el formato anterior a B.4a.
    """
    if path is not None:
        raw_text = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        resource = resources.files(_CONFIG_PACKAGE).joinpath(_CONFIG_RESOURCE)
        raw_text = resource.read_text(encoding="utf-8")
        source = f"{_CONFIG_PACKAGE}/{_CONFIG_RESOURCE}"

    prefix = f"Tabla de costos inválida en {source!r}: "
    try:
        payload = json.loads(raw_text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise BacktestConfigError(f"{prefix}JSON ilegible ({exc})") from exc
    except BacktestConfigError as exc:
        raise BacktestConfigError(f"{prefix}{exc}") from exc
    try:
        return _parse_table(payload)
    except BacktestConfigError as exc:
        raise BacktestConfigError(f"{prefix}{exc}") from exc
