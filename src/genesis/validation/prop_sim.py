"""Simulación de challenge prop firm: ficha de economía + resampleo + máquina de estados (Issue J).

Capa 4 (`genesis.validation`). Primer módulo del Change que (a) aplica una ficha de
economía de challenge (`PropEconomicsProfile`) a una simulación de cuenta y (b)
recorre día a día una serie de P&L resampleada para producir el veredicto de los
gates P1-P6 (spec §1.3, §7.3). Reimplementa localmente el criterio de canasta diaria
de `montecarlo._build_basket`/`_default_block_size` (`montecarlo.py:107-113,268-341`,
ADR-J2/J10) **sin** importar sus símbolos privados (R16): mismo criterio de
aislamiento entre Changes que ADR-H5/ADR-I1. Solo `numpy` + stdlib (R121): sin
`scipy`/`statsmodels`/`matplotlib`/`quantstats`. `simulate_challenge_paths` es un
núcleo puro (ADR-J3), reutilizado también por `verdict.py` (T2, ensemble) sobre una
canasta ponderada sin fabricar `Ledger`s sintéticos. Todo I/O de disco de este Change
vive en `verdict.write_verdict_artifacts` (R123): `prop_sim.py` permanece 100% en
memoria.
"""

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from genesis.validation.errors import PropSimConfigError

_CONFIG_PACKAGE = "genesis.validation"
_CONFIG_RESOURCE = "prop_economics_the5ers.json"


@dataclass(frozen=True, slots=True)
class PhaseSpec:
    """Una fase del challenge (evaluación o verificación), spec §1.3 (R7).

    `max_calendar_days=None` significa "sin límite de plazo" (The5ers v1, spec §1.3).
    """

    profit_target_pct: float
    min_profitable_days: int
    min_profit_per_day_pct: float
    max_calendar_days: int | None


@dataclass(frozen=True, slots=True)
class PropEconomicsProfile:
    """Ficha propia de economía del challenge, capa 4 (R8, ADR-J1).

    No duplica ningún campo ya expuesto por `FirmProfile` (capa 1) ni por
    `RiskProfile` (capa 3): `phases`/`challenge_cost_pct_of_balance`/
    `profit_split_pct`/`payout_cycle_days` no existen en ninguna de las dos.
    `challenge_cost_pct_of_balance=3.0` y `profit_split_pct=80.0` son
    **placeholders** explícitos "a confirmar" (R9, decisión 2 del gate humano);
    `payout_cycle_days=14` ("payouts quincenales") es definitivo, no placeholder.
    """

    name: str
    phases: tuple[PhaseSpec, ...]
    challenge_cost_pct_of_balance: float
    profit_split_pct: float
    payout_cycle_days: int
    max_lots: float | None
    max_positions: int | None
    consistency_rule_pct: float | None

    def __post_init__(self) -> None:
        """Valida la ficha, fail-fast vía `PropSimConfigError` (R12)."""
        if not self.phases:
            message = f"PropEconomicsProfile(name={self.name!r}).phases está vacío (R12)."
            raise PropSimConfigError(message)
        for index, phase in enumerate(self.phases):
            if phase.profit_target_pct <= 0:
                message = (
                    f"PropEconomicsProfile(name={self.name!r}).phases[{index}]"
                    f".profit_target_pct={phase.profit_target_pct!r} debe ser > 0 (R12)."
                )
                raise PropSimConfigError(message)
            if phase.min_profitable_days < 0:
                message = (
                    f"PropEconomicsProfile(name={self.name!r}).phases[{index}]"
                    f".min_profitable_days={phase.min_profitable_days!r} debe ser >= 0 (R12)."
                )
                raise PropSimConfigError(message)
            if phase.min_profit_per_day_pct < 0:
                message = (
                    f"PropEconomicsProfile(name={self.name!r}).phases[{index}]"
                    f".min_profit_per_day_pct={phase.min_profit_per_day_pct!r} debe ser >= 0 "
                    "(R12)."
                )
                raise PropSimConfigError(message)
        if self.payout_cycle_days <= 0:
            message = (
                f"PropEconomicsProfile(name={self.name!r}).payout_cycle_days="
                f"{self.payout_cycle_days!r} debe ser > 0 (R12)."
            )
            raise PropSimConfigError(message)
        if self.challenge_cost_pct_of_balance < 0:
            message = (
                f"PropEconomicsProfile(name={self.name!r}).challenge_cost_pct_of_balance="
                f"{self.challenge_cost_pct_of_balance!r} debe ser >= 0 (R12)."
            )
            raise PropSimConfigError(message)
        if not (0.0 < self.profit_split_pct <= 100.0):
            message = (
                f"PropEconomicsProfile(name={self.name!r}).profit_split_pct="
                f"{self.profit_split_pct!r} debe estar en (0.0, 100.0] (R12)."
            )
            raise PropSimConfigError(message)


def _phase_spec_from_payload(payload: dict[str, Any]) -> PhaseSpec:
    try:
        max_calendar_days_raw = payload["max_calendar_days"]
        max_calendar_days = None if max_calendar_days_raw is None else int(max_calendar_days_raw)
        return PhaseSpec(
            profit_target_pct=float(payload["profit_target_pct"]),
            min_profitable_days=int(payload["min_profitable_days"]),
            min_profit_per_day_pct=float(payload["min_profit_per_day_pct"]),
            max_calendar_days=max_calendar_days,
        )
    except (KeyError, TypeError, ValueError) as exc:
        message = f"Fase de PropEconomicsProfile inválida/incompleta: {payload!r} ({exc})."
        raise PropSimConfigError(message) from exc


def load_prop_economics_profile(path: Path | None = None) -> PropEconomicsProfile:
    """Carga `PropEconomicsProfile` desde `path`, o desde el recurso empaquetado (R10).

    `path=None` -> recurso empaquetado `genesis.validation/prop_economics_the5ers.json`
    (patrón `load_risk_profile`, `risk_profile.py:44-70`). `path` explícito permite
    cargar una ficha confirmada distinta del placeholder (R14). Lanza
    `PropSimConfigError` con el campo faltante/inválido en el mensaje ante
    configuración inválida o incompleta (fail-fast, R1f).
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
        phases = tuple(_phase_spec_from_payload(phase) for phase in payload["phases"])
        max_lots_raw = payload["max_lots"]
        max_positions_raw = payload["max_positions"]
        consistency_rule_pct_raw = payload["consistency_rule_pct"]
        return PropEconomicsProfile(
            name=payload["name"],
            phases=phases,
            challenge_cost_pct_of_balance=float(payload["challenge_cost_pct_of_balance"]),
            profit_split_pct=float(payload["profit_split_pct"]),
            payout_cycle_days=int(payload["payout_cycle_days"]),
            max_lots=None if max_lots_raw is None else float(max_lots_raw),
            max_positions=None if max_positions_raw is None else int(max_positions_raw),
            consistency_rule_pct=(
                None if consistency_rule_pct_raw is None else float(consistency_rule_pct_raw)
            ),
        )
    except PropSimConfigError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Ficha de economía del challenge inválida/incompleta en '{source}': {exc}"
        raise PropSimConfigError(message) from exc


def prop_economics_profile_hash(profile: PropEconomicsProfile) -> str:
    """Hash `sha256` canónico de `profile` sobre JSON ordenado (R11, patrón `risk_profile_hash`).

    Determinista: la misma ficha produce siempre el mismo hash; base de
    `economics_confirmed` (R14, `verdict.py`).
    """
    canonical = {
        "name": profile.name,
        "phases": [
            {
                "profit_target_pct": phase.profit_target_pct,
                "min_profitable_days": phase.min_profitable_days,
                "min_profit_per_day_pct": phase.min_profit_per_day_pct,
                "max_calendar_days": phase.max_calendar_days,
            }
            for phase in profile.phases
        ],
        "challenge_cost_pct_of_balance": profile.challenge_cost_pct_of_balance,
        "profit_split_pct": profile.profit_split_pct,
        "payout_cycle_days": profile.payout_cycle_days,
        "max_lots": profile.max_lots,
        "max_positions": profile.max_positions,
        "consistency_rule_pct": profile.consistency_rule_pct,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


_DEFAULT_PROFILE_HASH = prop_economics_profile_hash(load_prop_economics_profile())
"""Hash de la ficha placeholder empaquetada, calculado en tiempo de import (R14).

Base de `VerdictResult.economics_confirmed` (`verdict.py`, B4): `True` solo si el
llamador de `run_verdict` pasó una `PropEconomicsProfile` con un hash distinto de
este (es decir, una ficha confirmada, no el placeholder de fábrica).
"""
