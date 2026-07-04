"""Embudo de viabilidad compartido `inspect()` (spec §5.1, R13-R21).

Función pura que decide si un `EntryIntent` se autoriza o se rechaza contra la ficha
de símbolo/firma, agnóstica a qué candidato produjo la intención. Consume
exclusivamente puertos ya existentes de `genesis.data`
(`SymbolFigure`, `FirmProfile`, `news_windows`): NO reimplementa validación de
lotaje ni de ventanas de noticias, y NO importa `genesis.strategy.common` ni ningún
`genesis.strategy.candidate_*` (R18).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from importlib import resources
from pathlib import Path

from genesis.data.calendar import EconomicEvent, news_windows
from genesis.data.profile import FirmProfile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import EntryIntent
from genesis.strategy.errors import InspectorConfigError

_CONFIG_PACKAGE = "genesis.strategy"
_CONFIG_RESOURCE = "inspector_config.json"


class RejectionReason(StrEnum):
    """Motivo de rechazo de un `EntryIntent` por el embudo de viabilidad (R15).

    Exactamente 3 miembros en este Change. El cierre forzado por sesión (invariante
    del Candidato B/simulador) queda deliberadamente fuera de este `StrEnum`: no es
    una validación de viabilidad pre-trade de este embudo (spec §1.3).
    """

    INSUFFICIENT_RR = "insufficient_rr"
    LOT_SIZE_OUT_OF_BOUNDS = "lot_size_out_of_bounds"
    NEWS_WINDOW = "news_window"


@dataclass(frozen=True, slots=True)
class InspectorVerdict:
    """Veredicto del embudo de viabilidad: autorizado o rechazado con motivo (R14).

    `rejection_reason` es `None` si y solo si `authorized is True`.
    """

    authorized: bool
    rejection_reason: RejectionReason | None


AUTHORIZED: InspectorVerdict = InspectorVerdict(authorized=True, rejection_reason=None)
"""Singleton canónico del veredicto autorizado (ningún motivo de rechazo disparó)."""


@dataclass(frozen=True, slots=True)
class InspectorFunnelConfig:
    """Parámetros globales del embudo (namespace `inspector.*`, R16).

    Exclusivamente parámetros globales de embudo; nunca parámetros de señal de un
    candidato concreto (esos viven en `candidates.<letra>.*`, fuera de este Change).
    """

    min_rr: float
    min_lot: float
    max_lot: float
    lot_step_tolerance: float = 1e-9


def _is_lot_size_out_of_bounds(
    intent: EntryIntent, figure: SymbolFigure, config: InspectorFunnelConfig
) -> bool:
    sizing_hint = intent.sizing_hint
    if sizing_hint < config.min_lot or sizing_hint > config.max_lot:
        return True
    volume_step = figure.volume_step
    if volume_step <= 0:
        return False
    steps = sizing_hint / volume_step
    nearest_step = round(steps)
    return abs(steps - nearest_step) > config.lot_step_tolerance / volume_step


def inspect(
    intent: EntryIntent,
    *,
    symbol: str,
    intent_time: datetime,
    proposed_rr: float,
    figure: SymbolFigure,
    firm_profile: FirmProfile,
    news_events: Sequence[EconomicEvent],
    config: InspectorFunnelConfig,
) -> InspectorVerdict:
    """Decide si `intent` se autoriza o se rechaza contra la ficha de símbolo/firma (R13).

    Orden determinista de motivos (primer motivo que dispara gana):
    `NEWS_WINDOW` -> `INSUFFICIENT_RR` -> `LOT_SIZE_OUT_OF_BOUNDS`; si nada dispara,
    retorna `AUTHORIZED`.
    """
    windows = news_windows(news_events, symbol, firm_profile)
    if any(start <= intent_time <= end for start, end in windows):
        return InspectorVerdict(authorized=False, rejection_reason=RejectionReason.NEWS_WINDOW)

    if proposed_rr < config.min_rr:
        return InspectorVerdict(authorized=False, rejection_reason=RejectionReason.INSUFFICIENT_RR)

    if _is_lot_size_out_of_bounds(intent, figure, config):
        return InspectorVerdict(
            authorized=False, rejection_reason=RejectionReason.LOT_SIZE_OUT_OF_BOUNDS
        )

    return AUTHORIZED


def load_inspector_funnel_config(path: Path | None = None) -> InspectorFunnelConfig:
    """Carga `InspectorFunnelConfig` desde `path`, o desde el recurso empaquetado (R19, R21).

    `path=None` -> recurso empaquetado `genesis.strategy/inspector_config.json`
    (patrón `genesis.data.profile.load_firm_profile`). Lanza `InspectorConfigError`
    con contexto (campo faltante + fuente) si el JSON está incompleto o inválido —
    nunca degradación silenciosa.
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
        inspector_section = payload["inspector"]
        return InspectorFunnelConfig(
            min_rr=float(inspector_section["min_rr"]),
            min_lot=float(inspector_section["min_lot"]),
            max_lot=float(inspector_section["max_lot"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Configuración del embudo Inspector inválida/incompleta en '{source}': {exc}"
        raise InspectorConfigError(message) from exc
