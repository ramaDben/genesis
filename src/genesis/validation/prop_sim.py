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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

from genesis.backtest.ledger import FillRecord, Ledger
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile
from genesis.data.profile import FirmProfile
from genesis.validation._shared import clip
from genesis.validation.errors import PropSimConfigError

CONFIG_VERSION: str = "genesis-validation-j/1"
"""Versión del esquema de configuración de este Change (Issue J, decisión 10 §3)."""

_CONFIG_PACKAGE = "genesis.validation"
_CONFIG_RESOURCE = "prop_economics_the5ers.json"

_MIN_BLOCK_SIZE = 5
_MAX_BLOCK_SIZE = 60
"""Cota del tamaño de bloque del bootstrap circular (R18), mismos valores que
`montecarlo._MIN_BLOCK_SIZE`/`_MAX_BLOCK_SIZE` (`montecarlo.py:27-28`), reimplementados
localmente sin importar el módulo (ADR-J2/J10, R16)."""


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


def _default_block_size(n_days: int) -> int:
    """`clip(round(n_days ** (1/3)), 5, 60)` (R18), misma fórmula que en `montecarlo.py`."""
    return clip(round(n_days ** (1.0 / 3.0)), _MIN_BLOCK_SIZE, _MAX_BLOCK_SIZE)


def _extract_exit_deltas_by_day(ledger: Ledger) -> list[tuple[date, float]]:
    """Deltas de `equity_after` de los `FillRecord` de salida, etiquetados por `trading_day`.

    Proxy `payload.timestamp_utc.date()` (ADR-H8), reimplementado localmente sin
    importar `montecarlo._extract_exit_returns_by_day` (R16, mismo criterio de
    aislamiento entre Changes que ADR-H5/ADR-I1).
    """
    deltas_by_day: list[tuple[date, float]] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                trading_day = payload.timestamp_utc.date()
                deltas_by_day.append((trading_day, payload.equity_after - previous_equity))
            previous_equity = payload.equity_after
    return deltas_by_day


def _build_daily_basket(
    oos_ledgers_by_symbol: Mapping[str, Ledger],
) -> tuple[list[date], dict[date, float]]:
    """Canasta diaria de P&L, sumada across símbolos por `trading_day` (R15).

    A diferencia de `montecarlo._build_basket` (que retiene `(symbol, delta)` por
    día), aquí se colapsa directamente a un total por día: los gates P de
    `verdict.py` operan a nivel de cuenta, sin distinguir símbolo (R15). Compartida
    entre `prop_sim.py` y `verdict.py` dentro del Change (ADR-J10): única fuente de
    la canasta diaria, evita divergencia entre T1/T2 y `run_prop_sim` (Rg-5).
    """
    daily_totals: dict[date, float] = {}
    for ledger in oos_ledgers_by_symbol.values():
        for trading_day, delta in _extract_exit_deltas_by_day(ledger):
            daily_totals[trading_day] = daily_totals.get(trading_day, 0.0) + delta
    basket_days = sorted(daily_totals)
    return basket_days, daily_totals


def _resample_daily_pnl_path(
    basket_days: Sequence[date],
    daily_totals: Mapping[date, float],
    block_size: int,
    rng: np.random.Generator,
    *,
    target_len: int,
) -> np.ndarray:
    """Moving-block bootstrap circular sobre `basket_days`, `target_len` valores exactos (R20).

    Reimplementación local del criterio de `montecarlo._resample_day_sequence`
    (`montecarlo.py:305-325`, ADR-J2): bloques contiguos de `block_size` días,
    envueltos circularmente sobre `basket_days`, con reposición entre bloques.
    """
    n = len(basket_days)
    n_blocks_needed = -(-target_len // block_size)  # ceil division
    starts = rng.integers(0, n, size=n_blocks_needed)
    values: list[float] = []
    for start in starts:
        for offset in range(block_size):
            day = basket_days[(start + offset) % n]
            values.append(daily_totals[day])
    return np.array(values[:target_len], dtype=float)


@dataclass(frozen=True, slots=True)
class PropSimConfig:
    """Configuración de `simulate_challenge_paths`/`run_prop_sim` (R21).

    `path_horizon_trading_days=750 >= 12*21=252` por defecto: holgura para
    múltiples reinicios de intento antes de fondear (spec §1.3). `seed` es
    requerido, sin default, e **independiente** del `seed` de
    `monte_carlo_portfolio` (R19, decisión 9 §3).
    """

    n_paths: int
    seed: int
    max_attempts: int = 10
    horizon_months: int = 12
    trading_days_per_month: int = 21
    path_horizon_trading_days: int = 750
    block_size: int | None = None

    def __post_init__(self) -> None:
        """Valida la configuración, fail-fast vía `PropSimConfigError` (R21)."""
        if self.n_paths <= 0:
            message = f"PropSimConfig.n_paths={self.n_paths!r} debe ser > 0 (R21)."
            raise PropSimConfigError(message)
        if self.max_attempts < 1:
            message = f"PropSimConfig.max_attempts={self.max_attempts!r} debe ser >= 1 (R21)."
            raise PropSimConfigError(message)
        if self.horizon_months < 1:
            message = f"PropSimConfig.horizon_months={self.horizon_months!r} debe ser >= 1 (R21)."
            raise PropSimConfigError(message)
        if self.trading_days_per_month < 1:
            message = (
                f"PropSimConfig.trading_days_per_month={self.trading_days_per_month!r} "
                "debe ser >= 1 (R21)."
            )
            raise PropSimConfigError(message)
        required_horizon = self.horizon_months * self.trading_days_per_month
        if self.path_horizon_trading_days < required_horizon:
            message = (
                f"PropSimConfig.path_horizon_trading_days={self.path_horizon_trading_days!r} "
                f"insuficiente: debe ser >= horizon_months*trading_days_per_month="
                f"{required_horizon!r} (R21)."
            )
            raise PropSimConfigError(message)
        if self.block_size is not None and self.block_size <= 0:
            message = f"PropSimConfig.block_size={self.block_size!r} debe ser None o > 0 (R21)."
            raise PropSimConfigError(message)


class PropSimOutcomeKind(StrEnum):
    """Estado terminal de una trayectoria de challenge (R23), exactamente 4 miembros.

    Ampliar esta enumeración es un cambio de alcance que requiere un Change nuevo
    (mismo criterio que `BreachKind`, `ledger.py:22-32`): no relajar el contrato
    silenciosamente.
    """

    FUNDED_SURVIVED_HORIZON = "funded_survived_horizon"
    FUNDED_BREACHED_TOTAL = "funded_breached_total"
    NEVER_FUNDED_ATTEMPTS_EXHAUSTED = "never_funded_attempts_exhausted"
    IN_PROGRESS_UNFUNDED_AT_PATH_END = "in_progress_unfunded_at_path_end"


@dataclass(frozen=True, slots=True)
class PathOutcome:
    """Resultado congelado de una única trayectoria de challenge (R31).

    `funded_trading_day_index`/`breach_trading_day_index` son índices posicionales
    (0-based) dentro de la secuencia de P&L diario de la trayectoria, `None` si el
    evento correspondiente nunca ocurrió. `funded_survival_trading_days` es `None`
    únicamente si la trayectoria nunca llegó a fondearse (`outcome ==
    NEVER_FUNDED_ATTEMPTS_EXHAUSTED`); si llegó a fondearse (incluida
    `IN_PROGRESS_UNFUNDED_AT_PATH_END` con financiamiento parcial sin resolución),
    contiene el conteo de días fondeados observados. Ningún campo evalúa un umbral
    de gate P contra un booleano (R32): solo produce números, la comparación es
    responsabilidad de `verdict.py`.
    """

    outcome: PropSimOutcomeKind
    n_attempts_used: int
    funded_trading_day_index: int | None
    breach_trading_day_index: int | None
    funded_survival_trading_days: int | None
    net_payout_12m: float
    n_funded_months_observed: int
    n_funded_months_with_daily_breach: int


def _simulate_single_path(
    daily_pnl: Sequence[float] | np.ndarray,
    starting_balance: float,
    prop_economics_profile: PropEconomicsProfile,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    config: PropSimConfig,
) -> tuple[PathOutcome, float]:
    """Recorre `daily_pnl` día a día para UNA trayectoria (forward-only, R24).

    Reproduce la semántica de ancla de `simulator._evaluate_total_breach`
    (`simulator.py:380-406`): base balance-a-balance para el breach DIARIO (R25/R33,
    **nunca** la base de equity flotante intradía: ADR-J4, R34/R35 — el proxy
    cierre-a-cierre es una **cota inferior conservadora** de la probabilidad real de
    breach diario, la equity flotante intradía real puede disparar antes) y ancla
    dual `STATIC`/`TRAILING` para el breach TOTAL (R25/R27/R36). Retorna
    `(PathOutcome, challenge_cost_paid)`: el costo del challenge se acumula aparte
    porque `PathOutcome` no lo expone (R31) — se agrega a
    `PropSimResult.total_challenge_cost_paid` en `simulate_challenge_paths`/
    `run_prop_sim` (R37, informativo, no es un gate).
    """
    is_trailing = risk_profile.max_loss_limit_kind is MaxLossLimitKind.TRAILING
    phases = prop_economics_profile.phases
    challenge_cost = starting_balance * prop_economics_profile.challenge_cost_pct_of_balance / 100.0
    horizon_days = config.horizon_months * config.trading_days_per_month

    attempt = 1
    phase_index = 0
    balance = starting_balance
    phase_start_balance = starting_balance
    phase_profitable_days = 0
    attempt_peak_balance = starting_balance
    is_funded = False
    funded_trading_day_index: int | None = None
    funded_reference_balance = 0.0
    days_since_last_payout = 0
    n_funded_days_observed = 0
    cumulative_net_payout = 0.0
    n_funded_months_observed = 0
    n_funded_months_with_daily_breach = 0
    current_month_had_daily_breach = False
    # R37: el primer intento también cuenta ("por cada intento iniciado, incluido el
    # primero"); los reinicios posteriores acumulan `challenge_cost` adicional más abajo.
    total_challenge_cost_paid = challenge_cost

    for day_index, pnl in enumerate(daily_pnl):
        phase_start_of_day_balance = balance
        balance += pnl
        attempt_peak_balance = max(attempt_peak_balance, balance)

        daily_loss = max(0.0, phase_start_of_day_balance - balance)
        daily_threshold = phase_start_of_day_balance * firm_profile.daily_loss_limit_pct / 100.0
        breach_daily = daily_loss >= daily_threshold

        if is_funded:
            attempt_reference = attempt_peak_balance if is_trailing else funded_reference_balance
        else:
            attempt_reference = attempt_peak_balance if is_trailing else starting_balance
        total_loss = max(0.0, attempt_reference - balance)
        total_threshold = attempt_reference * risk_profile.max_loss_limit_pct / 100.0
        breach_total = total_loss >= total_threshold

        if not is_funded:
            if breach_daily or breach_total:
                if attempt < config.max_attempts:
                    attempt += 1
                    balance = starting_balance
                    phase_index = 0
                    phase_start_balance = starting_balance
                    phase_profitable_days = 0
                    attempt_peak_balance = starting_balance
                    total_challenge_cost_paid += challenge_cost
                    continue
                return (
                    PathOutcome(
                        outcome=PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED,
                        n_attempts_used=attempt,
                        funded_trading_day_index=None,
                        breach_trading_day_index=day_index,
                        funded_survival_trading_days=None,
                        net_payout_12m=0.0,
                        n_funded_months_observed=0,
                        n_funded_months_with_daily_breach=0,
                    ),
                    total_challenge_cost_paid,
                )

            phase = phases[phase_index]
            daily_return_pct = (
                0.0
                if phase_start_of_day_balance == 0.0
                else 100.0 * pnl / phase_start_of_day_balance
            )
            if daily_return_pct >= phase.min_profit_per_day_pct:
                phase_profitable_days += 1
            profit_since_phase_start = balance - phase_start_balance
            target_amount = phase_start_balance * phase.profit_target_pct / 100.0
            if (
                profit_since_phase_start >= target_amount
                and phase_profitable_days >= phase.min_profitable_days
            ):
                if phase_index + 1 == len(phases):
                    is_funded = True
                    funded_trading_day_index = day_index
                    funded_reference_balance = balance
                    days_since_last_payout = 0
                else:
                    phase_index += 1
                    phase_start_balance = balance
                    phase_profitable_days = 0
            continue

        # Rama fondeada (R27/R28/R29): breach DIARIO es continuable, solo TOTAL termina.
        if breach_daily:
            current_month_had_daily_breach = True
        if breach_total:
            return (
                PathOutcome(
                    outcome=PropSimOutcomeKind.FUNDED_BREACHED_TOTAL,
                    n_attempts_used=attempt,
                    funded_trading_day_index=funded_trading_day_index,
                    breach_trading_day_index=day_index,
                    funded_survival_trading_days=n_funded_days_observed,
                    net_payout_12m=cumulative_net_payout,
                    n_funded_months_observed=n_funded_months_observed,
                    n_funded_months_with_daily_breach=n_funded_months_with_daily_breach,
                ),
                total_challenge_cost_paid,
            )

        days_since_last_payout += 1
        if days_since_last_payout == prop_economics_profile.payout_cycle_days:
            payout = (
                max(0.0, balance - funded_reference_balance)
                * prop_economics_profile.profit_split_pct
                / 100.0
            )
            cumulative_net_payout += payout
            funded_reference_balance = balance
            days_since_last_payout = 0

        n_funded_days_observed += 1
        if n_funded_days_observed % config.trading_days_per_month == 0:
            n_funded_months_observed += 1
            if current_month_had_daily_breach:
                n_funded_months_with_daily_breach += 1
            current_month_had_daily_breach = False

        if n_funded_days_observed >= horizon_days:
            return (
                PathOutcome(
                    outcome=PropSimOutcomeKind.FUNDED_SURVIVED_HORIZON,
                    n_attempts_used=attempt,
                    funded_trading_day_index=funded_trading_day_index,
                    breach_trading_day_index=None,
                    funded_survival_trading_days=n_funded_days_observed,
                    net_payout_12m=cumulative_net_payout,
                    n_funded_months_observed=n_funded_months_observed,
                    n_funded_months_with_daily_breach=n_funded_months_with_daily_breach,
                ),
                total_challenge_cost_paid,
            )

    return (
        PathOutcome(
            outcome=PropSimOutcomeKind.IN_PROGRESS_UNFUNDED_AT_PATH_END,
            n_attempts_used=attempt,
            funded_trading_day_index=funded_trading_day_index,
            breach_trading_day_index=None,
            funded_survival_trading_days=n_funded_days_observed if is_funded else None,
            net_payout_12m=cumulative_net_payout,
            n_funded_months_observed=n_funded_months_observed,
            n_funded_months_with_daily_breach=n_funded_months_with_daily_breach,
        ),
        total_challenge_cost_paid,
    )


_FUNDED_OUTCOME_KINDS = frozenset(
    {PropSimOutcomeKind.FUNDED_SURVIVED_HORIZON, PropSimOutcomeKind.FUNDED_BREACHED_TOTAL}
)
"""Trayectorias que "alcanzaron el fondeo" a efectos de P1/P2/P4 (R42-R47).

`IN_PROGRESS_UNFUNDED_AT_PATH_END` queda **fuera** de este conjunto aunque la
trayectoria haya llegado a fondearse parcialmente (financiamiento sin resolución al
agotar `path_horizon_trading_days`): no alcanzó ni la censura al horizonte ni un
breach total, por lo que no cuenta como "fondeo resuelto" para los agregados P.
"""


@dataclass(frozen=True, slots=True)
class PropSimResult:
    """Resultado agregado de `simulate_challenge_paths`/`run_prop_sim` (R41)."""

    candidate_id: str
    config_version: str
    seed: int
    n_paths: int
    p_pass: float
    expected_attempts: float
    expected_attempts_p50: float
    expected_attempts_p90: float
    p_daily_breach_funded_month: float
    median_funded_survival_months: float
    payout_p25_12m: float
    n_paths_never_funded: int
    n_paths_funded_breached_total: int
    n_paths_funded_survived_horizon: int
    total_challenge_cost_paid: float


def _aggregate_path_outcomes(
    outcomes: Sequence[PathOutcome],
    total_challenge_cost_paid: float,
    *,
    candidate_id: str,
    config_version: str,
    seed: int,
    trading_days_per_month: int,
) -> PropSimResult:
    """Agregados P1-P5 sobre `outcomes` (R42-R48), censura por la derecha (ADR-J5)."""
    n_paths = len(outcomes)
    funded_outcomes = [outcome for outcome in outcomes if outcome.outcome in _FUNDED_OUTCOME_KINDS]

    p_pass = len(funded_outcomes) / n_paths

    if funded_outcomes:
        attempts_used = np.array(
            [outcome.n_attempts_used for outcome in funded_outcomes], dtype=float
        )
        expected_attempts = float(attempts_used.mean())
        expected_attempts_p50 = float(np.percentile(attempts_used, 50))
        expected_attempts_p90 = float(np.percentile(attempts_used, 90))
    else:
        expected_attempts = float("inf")
        expected_attempts_p50 = float("inf")
        expected_attempts_p90 = float("inf")

    months_observed_total = sum(outcome.n_funded_months_observed for outcome in outcomes)
    months_with_breach_total = sum(
        outcome.n_funded_months_with_daily_breach for outcome in outcomes
    )
    p_daily_breach_funded_month = (
        months_with_breach_total / months_observed_total if months_observed_total > 0 else 0.0
    )

    if funded_outcomes:
        survival_months = np.array(
            [
                (outcome.funded_survival_trading_days or 0) / trading_days_per_month
                for outcome in funded_outcomes
            ],
            dtype=float,
        )
        median_funded_survival_months = float(np.percentile(survival_months, 50))
    else:
        median_funded_survival_months = 0.0

    payouts = np.array([outcome.net_payout_12m for outcome in outcomes], dtype=float)
    payout_p25_12m = float(np.percentile(payouts, 25))

    return PropSimResult(
        candidate_id=candidate_id,
        config_version=config_version,
        seed=seed,
        n_paths=n_paths,
        p_pass=p_pass,
        expected_attempts=expected_attempts,
        expected_attempts_p50=expected_attempts_p50,
        expected_attempts_p90=expected_attempts_p90,
        p_daily_breach_funded_month=p_daily_breach_funded_month,
        median_funded_survival_months=median_funded_survival_months,
        payout_p25_12m=payout_p25_12m,
        n_paths_never_funded=sum(
            1
            for outcome in outcomes
            if outcome.outcome is PropSimOutcomeKind.NEVER_FUNDED_ATTEMPTS_EXHAUSTED
        ),
        n_paths_funded_breached_total=sum(
            1 for outcome in outcomes if outcome.outcome is PropSimOutcomeKind.FUNDED_BREACHED_TOTAL
        ),
        n_paths_funded_survived_horizon=sum(
            1
            for outcome in outcomes
            if outcome.outcome is PropSimOutcomeKind.FUNDED_SURVIVED_HORIZON
        ),
        total_challenge_cost_paid=total_challenge_cost_paid,
    )


def simulate_challenge_paths(
    daily_pnl_by_day: Mapping[date, float],
    starting_balance: float,
    prop_economics_profile: PropEconomicsProfile,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    config: PropSimConfig,
    candidate_id: str,
) -> PropSimResult:
    """Núcleo puro: resamplea `config.n_paths` trayectorias y agrega P1-P5 (ADR-J3).

    Opera sobre una serie de P&L diario ya combinada (`daily_pnl_by_day`), sin
    depender de `Ledger`: reutilizado también por `verdict.py` (T2, R82) sobre la
    canasta ponderada del ensemble sin fabricar `Ledger`s sintéticos.
    `PropSimConfigError` si `daily_pnl_by_day` está vacío (guarda defensiva; el
    disparo normativo R17 vive en `run_prop_sim`/la construcción del ensemble en
    `verdict.py`). RNG explícito (`numpy.random.default_rng(config.seed)`), loop
    secuencial sobre `n_paths` (R22/R124): determinismo bit a bit (R51).
    """
    if not daily_pnl_by_day:
        message = (
            f"simulate_challenge_paths: daily_pnl_by_day vacío para "
            f"candidate_id={candidate_id!r} (R17)."
        )
        raise PropSimConfigError(message)

    basket_days = sorted(daily_pnl_by_day)
    resolved_block_size = (
        config.block_size
        if config.block_size is not None
        else _default_block_size(len(basket_days))
    )
    rng = np.random.default_rng(config.seed)

    outcomes: list[PathOutcome] = []
    total_challenge_cost_paid = 0.0
    for _path_index in range(config.n_paths):
        resampled_pnl = _resample_daily_pnl_path(
            basket_days,
            daily_pnl_by_day,
            resolved_block_size,
            rng,
            target_len=config.path_horizon_trading_days,
        )
        outcome, cost_paid = _simulate_single_path(
            resampled_pnl,
            starting_balance,
            prop_economics_profile,
            firm_profile,
            risk_profile,
            config,
        )
        outcomes.append(outcome)
        total_challenge_cost_paid += cost_paid

    return _aggregate_path_outcomes(
        outcomes,
        total_challenge_cost_paid,
        candidate_id=candidate_id,
        config_version=CONFIG_VERSION,
        seed=config.seed,
        trading_days_per_month=config.trading_days_per_month,
    )


def run_prop_sim(
    oos_ledgers_by_symbol: Mapping[str, Ledger],
    starting_balance: float,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    prop_economics_profile: PropEconomicsProfile,
    config: PropSimConfig,
    candidate_id: str,
) -> PropSimResult:
    """Envoltorio de `simulate_challenge_paths` sobre los `Ledger` OOS reales (R50).

    Construye la canasta diaria (`_build_daily_basket`, R15) y delega en
    `simulate_challenge_paths` (núcleo puro). `PropSimConfigError` si la canasta
    resultante queda vacía (R17): ningún trade OOS extraíble de
    `oos_ledgers_by_symbol` en ningún símbolo.
    """
    basket_days, daily_totals = _build_daily_basket(oos_ledgers_by_symbol)
    if not basket_days:
        message = (
            f"run_prop_sim: candidate_id={candidate_id!r} sin ningún trade OOS extraíble de "
            f"oos_ledgers_by_symbol (símbolos={list(oos_ledgers_by_symbol)!r}, R17)."
        )
        raise PropSimConfigError(message)

    return simulate_challenge_paths(
        daily_totals,
        starting_balance,
        prop_economics_profile,
        firm_profile,
        risk_profile,
        config,
        candidate_id,
    )
