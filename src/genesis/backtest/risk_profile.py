"""Ficha propia de riesgo `RiskProfile` (capa 3), sin tocar `FirmProfile` (ADR-G2).

`FirmProfile` (capa 1) no expone el límite máximo de pérdida total ni la política de
tenencia de fin de semana (Rg-2 del spec); esta capa define su propia ficha, cargada
con el mismo patrón que `load_firm_profile`/`profiles/the5ers.json`. El balance de
cierre del día anterior (`previous_day_close_balance`) es estado de ejecución del
`SimulationClock` (T3), nunca config estática (R14).
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path

from genesis.backtest.errors import BacktestConfigError

_CONFIG_PACKAGE = "genesis.backtest"
_CONFIG_RESOURCE = "risk_profile.json"


class MaxLossLimitKind(StrEnum):
    """Tipo de límite máximo de pérdida total de la cuenta (R10)."""

    STATIC = "static"
    TRAILING = "trailing"


@dataclass(frozen=True, slots=True)
class RiskProfile:
    """Ficha propia de riesgo de la capa 3 (R11).

    No duplica campos ya expuestos por `FirmProfile` (`daily_loss_limit_pct`,
    `daily_reset_time` se leen de ahí); `weekend_holding_allowed` no tiene equivalente
    en `FirmProfile` (spec §1.3).
    """

    max_loss_limit_pct: float
    max_loss_limit_kind: MaxLossLimitKind
    weekend_holding_allowed: bool


def load_risk_profile(path: Path | None = None) -> RiskProfile:
    """Carga `RiskProfile` desde `path`, o desde el recurso empaquetado por defecto (R12).

    `path=None` -> recurso empaquetado `genesis.backtest/risk_profile.json` (patrón
    `load_firm_profile`). Defaults del recurso empaquetado (spec §1.3):
    `max_loss_limit_pct=10.0`, `max_loss_limit_kind=STATIC`,
    `weekend_holding_allowed=True`. Lanza `BacktestConfigError` con el campo faltante
    en el mensaje ante configuración inválida o incompleta (fail-fast).
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
        return RiskProfile(
            max_loss_limit_pct=float(payload["max_loss_limit_pct"]),
            max_loss_limit_kind=MaxLossLimitKind(payload["max_loss_limit_kind"]),
            weekend_holding_allowed=bool(payload["weekend_holding_allowed"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Ficha de riesgo inválida/incompleta en '{source}': {exc}"
        raise BacktestConfigError(message) from exc


def risk_profile_hash(profile: RiskProfile) -> str:
    """Hash `sha256` canónico de `profile` sobre JSON ordenado (R13, patrón `firm_profile_hash`).

    Determinista: la misma ficha produce siempre el mismo hash; se incorpora a
    `RunProvenance` (T6, R45).
    """
    canonical = {
        "max_loss_limit_pct": profile.max_loss_limit_pct,
        "max_loss_limit_kind": profile.max_loss_limit_kind.value,
        "weekend_holding_allowed": profile.weekend_holding_allowed,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
