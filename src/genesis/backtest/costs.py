"""Modelo de costos con `stress` de primera clase (R37–R41).

Funciones puras sobre `SymbolFigure`/`CostsConfig`/`TickRow`; ninguna hace I/O salvo
`load_costs_config` al cargar el recurso empaquetado. Solo `numpy` + stdlib (R41): sin
`scipy`/`statsmodels`/`matplotlib`/`quantstats`.
"""

import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path

from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import TickRow
from genesis.data.symbols import SymbolFigure

_CONFIG_PACKAGE = "genesis.backtest"
_CONFIG_RESOURCE = "costs_config.json"


@dataclass(frozen=True, slots=True)
class CostsConfig:
    """Defaults de costos empaquetados (R39): fallback fijo cuando no hay ticks."""

    default_spread_points: float
    commission_per_lot: float
    slippage_points: float


def spread_for(
    symbol: str,
    timestamp: datetime,
    figure: SymbolFigure,
    ticks_window: Sequence[TickRow] | None,
    config: CostsConfig,
    *,
    stress: float = 1.0,
) -> float:
    """Costo de spread para `symbol` en `timestamp` (R37).

    Muestrea la mediana de `ask - bid` de `ticks_window` si hay cobertura; si es
    `None`/vacía usa `config.default_spread_points` (fallback fijo conservador).
    `symbol`/`timestamp`/`figure` se conservan en la firma para futura extensión sin
    romper el contrato de la función; hoy no participan del cálculo.
    """
    del symbol, timestamp, figure
    if ticks_window:
        base = statistics.median(tick.ask - tick.bid for tick in ticks_window)
    else:
        base = config.default_spread_points
    return base * stress


def commission_for(sizing_hint: float, config: CostsConfig, *, stress: float = 1.0) -> float:
    """Costo de comisión proporcional al lotaje (R37)."""
    return sizing_hint * config.commission_per_lot * stress


def slippage_for(figure: SymbolFigure, config: CostsConfig, *, stress: float = 1.0) -> float:
    """Costo de slippage fijo de la ficha de costos (R37). `figure` reservado para extensión."""
    del figure
    return config.slippage_points * stress


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


def load_costs_config(path: Path | None = None) -> CostsConfig:
    """Carga `CostsConfig` desde `path`, o desde el recurso empaquetado por defecto (R39).

    `path=None` -> recurso empaquetado `genesis.backtest/costs_config.json`. Lanza
    `BacktestConfigError` con contexto si el JSON está incompleto o inválido.
    """
    if path is not None:
        raw_text = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        resource = resources.files(_CONFIG_PACKAGE).joinpath(_CONFIG_RESOURCE)
        raw_text = resource.read_text(encoding="utf-8")
        source = f"{_CONFIG_PACKAGE}/{_CONFIG_RESOURCE}"

    try:
        payload = json.loads(raw_text)
        return CostsConfig(
            default_spread_points=float(payload["default_spread_points"]),
            commission_per_lot=float(payload["commission_per_lot"]),
            slippage_points=float(payload["slippage_points"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Configuración de costos inválida/incompleta en '{source}': {exc}"
        raise BacktestConfigError(message) from exc
