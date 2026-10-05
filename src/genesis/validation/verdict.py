"""Veredicto de torneo: bundle, gates G/C/P/T1/T2, tearsheet y manifest (Issue J).

Capa 4 (`genesis.validation`), primer módulo que (a) evalúa umbrales de gate contra
un booleano (H/I solo producen números), (b) aplica la ficha de economía del
challenge a un veredicto de negocio y (c) serializa artefactos a disco. Reutiliza
las dataclasses de resultado ya cerradas de H/I (`WfaResult`, `DsrPboResult`,
`SensitivityResult`, `McSymbolResult`, `McPortfolioResult`, `PurgedCvResult`) **sin
recalcular** ninguna de sus métricas (R61): solo compara los valores ya producidos
contra los umbrales normativos, declarados como constantes de módulo nombradas
(`_G1_MIN_TRADES_OOS`, ..., ADR-J11) — nunca literales sueltos en la lógica de
comparación.
"""

import itertools
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import numpy as np

from genesis.backtest.ledger import BreachEvent, BreachKind
from genesis.backtest.metrics import (
    IntentAuthorizationCounts,
    intent_authorization_counts,
    profit_factor,
)
from genesis.data.house_rule import HouseRule
from genesis.data.metadata import current_git_commit
from genesis.data.profile import FirmProfile
from genesis.strategy.inspector import RejectionReason
from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation._returns import extract_trade_returns
from genesis.validation.dsr_pbo import DsrPboResult
from genesis.validation.errors import TrialLedgerConfigError, VerdictConfigError
from genesis.validation.montecarlo import McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import (
    BiasDirection,
    BreachEvaluationBasis,
    PropEconomicsProfile,
    PropSimConfig,
    PropSimResult,
    _build_daily_basket,
    simulate_challenge_paths,
)
from genesis.validation.purged_cv import PurgedCvResult
from genesis.validation.sensitivity import SensitivityResult
from genesis.validation.trial_ledger import TrialLedger, TrialLedgerSummary, TrialOutcomeKind
from genesis.validation.wfa import WfaResult

CONFIG_VERSION: str = "genesis-validation-j/4"
"""Versión del esquema de configuración de este Change (Issue J, decisión 10 §3).

`/2` desde Change #109: `manifest.json` sustituye `risk_profile_hash` por
`exit_geometry_hash` + `house_rule_hash`, y agrega el bloque de sesgo del proxy (D7).
`/3` desde Change #130: cada candidato del manifest gana `declared_universe`,
`symbols_evaluated`, `symbols_not_evaluated` y `status` de 3 valores por símbolo; C1 se mide
contra el universo declarado.
`/4` desde Change #135: el manifest gana `costs_hash_by_symbol` (la misma huella que entra
al `trial_id`) y `friction_status_by_symbol` (calidad de la fuente de spread/deslizamiento;
fuera del `trial_id`)."""

# Valor de `FrictionStatus.PROVISIONAL_HASTA_B4B` de capa 3, como texto: el manifest recibe
# `str` puros y el tearsheet solo lo traduce a lenguaje llano (Change #135, AE5).
_FRICTION_PROVISIONAL = "provisional_hasta_b4b"

# --- Umbrales de gate, constantes de módulo nombradas (ADR-J11, R63/R65) ---
_G1_MIN_TRADES_OOS = 300
_G2_MIN_WFE = 0.5
_G3_MIN_PROFIT_FACTOR = 1.3
_G4_MIN_DSR = 0.95
_G5_MAX_PBO = 0.25
_G6_MAXDD_FRACTION_OF_LIMIT = 0.5
_G7_MAX_BREACH_PROB = 0.05
_G8_MAX_DEGRADATION = 0.30
_G9_MIN_PF_STRESS = 1.15
_G9_STRESS_MULTIPLIER = 1.5

_C1_MIN_FRACTION = 0.60
_MIN_DECLARED_UNIVERSE_SIZE = 2
"""Tamaño mínimo del universo declarado (Change #130, SSoT `:600-603`).

No es una constante elegida: es el punto exacto en que C1 deja de ser vacío."""
_C2_MIN_PF = 0.8

_P1_MIN_PASS = 0.5
_P2_MAX_ATTEMPTS = 2.0
_P3_MAX_DAILY_BREACH = 0.02
_P4_MIN_SURVIVAL_MONTHS = 6.0
_P5_MIN_PAYOUT = 0.0

_T1_MIN_DSR = 0.95
_T2_MAX_CORRELATION = 0.3


class SymbolGateStatus(StrEnum):
    """Estado de un símbolo declarado frente a los gates G1-G9 (Change #130, R7)."""

    PASS = "PASS"  # noqa: S105  # nosec B105 - estado de gate, no una contraseña
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def _check_min_declared_universe_size(candidate_id: str, declared_universe: frozenset[str]) -> None:
    """R5: `|U| < 2` no admite veredicto (C1 sería vacío). Levanta `VerdictConfigError`."""
    if len(declared_universe) < _MIN_DECLARED_UNIVERSE_SIZE:
        message = (
            f"CandidateValidationBundle(candidate_id={candidate_id!r}): el universo declarado "
            f"declared_universe={sorted(declared_universe)!r} tiene "
            f"{len(declared_universe)} símbolo(s); se exigen al menos "
            f"{_MIN_DECLARED_UNIVERSE_SIZE} para emitir veredicto (disparador (f), Change #130)."
        )
        raise VerdictConfigError(message)


def _check_symbols_within_declared_universe(
    candidate_id: str,
    declared_universe: frozenset[str],
    evaluated_symbols: Iterable[str],
    not_applicable_symbols: Iterable[str] = (),
) -> None:
    """R1/R6: evaluados y 'no aplica' pertenecen a `U`; ningún símbolo es ambos a la vez."""
    evaluated = set(evaluated_symbols)
    not_applicable = set(not_applicable_symbols)
    prefix = f"CandidateValidationBundle(candidate_id={candidate_id!r}): "
    suffix = f"declared_universe={sorted(declared_universe)!r} (disparador (f), Change #130)."
    outside_evaluated = evaluated - declared_universe
    if outside_evaluated:
        message = (
            f"{prefix}símbolos evaluados fuera del universo declarado: "
            f"{sorted(outside_evaluated)!r}; {suffix}"
        )
        raise VerdictConfigError(message)
    outside_na = not_applicable - declared_universe
    if outside_na:
        message = (
            f"{prefix}símbolos marcados 'no aplica' fuera del universo declarado: "
            f"{sorted(outside_na)!r}; {suffix}"
        )
        raise VerdictConfigError(message)
    both = evaluated & not_applicable
    if both:
        message = (
            f"{prefix}símbolos a la vez evaluados y marcados 'no aplica': "
            f"{sorted(both)!r}; {suffix}"
        )
        raise VerdictConfigError(message)


def validate_declared_universe(
    candidate_id: str,
    declared_universe: frozenset[str],
    evaluated_symbols: Iterable[str],
) -> None:
    """Pre-flight público del universo declarado (R5 + R6), misma regla que usa el bundle.

    Lo invoca el runner antes de leer datos de mercado: un universo inválido no debe
    quemar un ensayo que el ledger no llegue a registrar. Levanta `VerdictConfigError`.
    """
    _check_min_declared_universe_size(candidate_id, declared_universe)
    _check_symbols_within_declared_universe(candidate_id, declared_universe, evaluated_symbols)


@dataclass(frozen=True, slots=True)
class CandidateValidationBundle:
    """Insumos de un candidato ya producidos por H/I/J, sin recalcular nada (R57).

    Las claves de `wfa_results_by_symbol`/`dsr_pbo_results_by_symbol`/
    `sensitivity_results_by_symbol`/`mc_symbol_results_by_symbol` deben coincidir
    exactamente (R58); `purged_cv_results_by_symbol` es opcional (solo diagnóstico
    informativo del manifest, R106).

    Change #130: `declared_universe` (sin default) es el denominador de C1; todo símbolo
    evaluado o marcado en `not_applicable_symbols` debe pertenecerle. El tamaño mínimo
    (`|U| >= 2`) se exige al emitir veredicto, no al construir el bundle.
    """

    candidate_id: str
    wfa_results_by_symbol: Mapping[str, WfaResult]
    dsr_pbo_results_by_symbol: Mapping[str, DsrPboResult]
    sensitivity_results_by_symbol: Mapping[str, SensitivityResult]
    mc_symbol_results_by_symbol: Mapping[str, McSymbolResult]
    mc_portfolio_result: McPortfolioResult
    prop_sim_result: PropSimResult
    declared_universe: frozenset[str]
    purged_cv_results_by_symbol: Mapping[str, PurgedCvResult] | None = None
    # Change #53 (Q5): configuración completa del candidato evaluado, identidad de
    # "lo que se evaluó" para el ledger de ensayos. Opcional: `__post_init__` no lo valida
    # (un bundle sin config sigue siendo legítimo cuando no hay ledger).
    candidate_config: Mapping[str, object] | None = None
    # Change #130 (D1): símbolos del universo cuya estrategia no está definida; cuentan
    # como no superados en C1. Es una declaración, nunca una inferencia de datos vacíos.
    not_applicable_symbols: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Valida R58 (símbolos entre los 4 mapas) y luego R1/R6 (universo declarado)."""
        symbol_sets: dict[str, set[str]] = {
            "wfa_results_by_symbol": set(self.wfa_results_by_symbol),
            "dsr_pbo_results_by_symbol": set(self.dsr_pbo_results_by_symbol),
            "sensitivity_results_by_symbol": set(self.sensitivity_results_by_symbol),
            "mc_symbol_results_by_symbol": set(self.mc_symbol_results_by_symbol),
        }
        reference_name, reference_symbols = next(iter(symbol_sets.items()))
        for map_name, symbols in symbol_sets.items():
            if symbols != reference_symbols:
                message = (
                    f"CandidateValidationBundle(candidate_id={self.candidate_id!r}): símbolos "
                    f"inconsistentes entre insumos ({reference_name}={sorted(reference_symbols)!r} "
                    f"vs. {map_name}={sorted(symbols)!r}, R58)."
                )
                raise VerdictConfigError(message)

        for field_name in ("declared_universe", "not_applicable_symbols"):
            value = getattr(self, field_name)
            if not isinstance(value, frozenset) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                message = (
                    f"CandidateValidationBundle(candidate_id={self.candidate_id!r}): "
                    f"{field_name}={value!r} debe ser un frozenset de str no vacíos "
                    "(disparador (f), Change #130)."
                )
                raise VerdictConfigError(message)
        _check_symbols_within_declared_universe(
            self.candidate_id,
            self.declared_universe,
            reference_symbols,
            self.not_applicable_symbols,
        )


@dataclass(frozen=True, slots=True)
class SymbolGateOutcome:
    """Valor + booleano de pasa/no-pasa por cada gate G1-G9 de un `(candidate_id, symbol)` (R59).

    `status` (Change #130, R7) resume el símbolo: `PASS` (G1-G9 en verde), `FAIL` o
    `NOT_APPLICABLE` (estrategia no definida para ese activo; cuenta como no superado).
    """

    trades_oos_total: int
    g1_pass: bool
    wfe: float
    g2_pass: bool
    profit_factor: float
    g3_pass: bool
    dsr: float
    g4_pass: bool
    pbo: float
    g5_pass: bool
    mc_maxdd_p95_pct_of_limit: float
    g6_pass: bool
    mc_breach_probability_12m: float
    g7_pass: bool
    sensitivity_has_cliff: bool
    sensitivity_max_degradation_pct: float
    g8_pass: bool
    pf_cost_stress_1_5x: float
    g9_pass: bool
    # Change #130 (R7): estado de 3 valores; `all_pass` se deriva (property).
    status: SymbolGateStatus
    # --- Change #51 (R2/R3): señal de "evidencia de sizing ausente", no un gate. No
    # participa de `status` ni de ningún `gN_pass` (los gates no se relajan). ---
    sizing_evidence_insufficient: bool
    intents_total: int
    intents_authorized: int
    rejections_by_reason: Mapping[str, int]
    # --- Change #53 (Q6): composición del ledger de ensayos sobre G4. `dsr` (arriba) es
    # el DSR *efectivo* que gatea; los 3 campos siguientes documentan de dónde sale. ---
    dsr_pre_ledger_deflation: float
    n_trials_g4_effective: int
    ledger_extra_trials: int

    @property
    def all_pass(self) -> bool:
        """`True` si y solo si `status` es `PASS` (conjunción G1-G9; 'no aplica' no pasa)."""
        return self.status is SymbolGateStatus.PASS


def _is_sizing_evidence_insufficient(counts: IntentAuthorizationCounts) -> bool:
    """Predicado literal de R3 (Change #51), con el desempate aprobado por el gate humano (D1).

    `True` si y solo si el rechazo fue **total** (`intents_total > 0` y
    `intents_authorized == 0`) y el motivo `LOT_SIZE_OUT_OF_BOUNDS` es dominante:
    `n_lot_size > 0` y `n_lot_size >= max(conteo de cualquier otro motivo)`. El
    empate cuenta a favor de `LOT_SIZE_OUT_OF_BOUNDS` (criterio del eval A7 del
    `spec.md`, adoptado por `design.md` Q3 y confirmado en la aprobación de diseño).
    Si `intents_total == 0` (sin señal de entrada, no rechazo de sizing) es `False`.
    """
    if counts.intents_total == 0 or counts.intents_authorized != 0:
        return False
    n_lot_size = counts.rejections_by_reason.get(RejectionReason.LOT_SIZE_OUT_OF_BOUNDS.value, 0)
    if n_lot_size == 0:
        return False
    n_max_other = max(
        (
            count
            for reason, count in counts.rejections_by_reason.items()
            if reason != RejectionReason.LOT_SIZE_OUT_OF_BOUNDS.value
        ),
        default=0,
    )
    return n_lot_size >= n_max_other


def _build_symbol_gate_outcome(
    symbol: str,
    wfa_result: WfaResult,
    dsr_pbo_result: DsrPboResult,
    sensitivity_result: SensitivityResult,
    mc_symbol_result: McSymbolResult,
    house_rule: HouseRule,
    *,
    ledger_extra_trials: int,
) -> SymbolGateOutcome:
    """Construye `SymbolGateOutcome` para `symbol` comparando insumos ya producidos (R60/R61).

    `ledger_extra_trials` (Change #53, Q1/PR-1/PR-3) es el N acumulado del ledger de
    ensayos que se suma a `wfa_result.n_trials_signal_total` para el DSR *efectivo* que
    gatea G4. Cortocircuito: `ledger_extra_trials == 0` reutiliza
    `dsr_pbo_result.dsr` verbatim, sin recomputar nada (byte-identidad con el
    comportamiento pre-Change, A3/A7). `dsr_pbo.py` no se toca.
    """
    del symbol  # solo para contexto de mensajes futuros (auditoría), no usado en el cómputo

    trade_returns = extract_trade_returns(wfa_result.oos_ledger_cosido)
    trades_oos_total = len(trade_returns)
    g1_pass = trades_oos_total >= _G1_MIN_TRADES_OOS

    wfe = wfa_result.wfe
    g2_pass = wfe >= _G2_MIN_WFE

    pf = profit_factor(wfa_result.oos_ledger_cosido)
    g3_pass = pf >= _G3_MIN_PROFIT_FACTOR

    dsr_pre_ledger_deflation = dsr_pbo_result.dsr
    n_trials_g4_effective = wfa_result.n_trials_signal_total + ledger_extra_trials
    dsr = (
        dsr_pbo_result.dsr
        if ledger_extra_trials == 0
        else deflated_sharpe_ratio(
            [trade.pnl_delta for trade in trade_returns], n_trials=n_trials_g4_effective
        )
    )
    g4_pass = dsr >= _G4_MIN_DSR

    pbo = dsr_pbo_result.pbo
    g5_pass = pbo < _G5_MAX_PBO

    full_limit_dollar = house_rule.max_loss_limit.amount
    mc_maxdd_p95_pct_of_limit = (
        mc_symbol_result.block_bootstrap.max_drawdown_p95 / full_limit_dollar
        if full_limit_dollar > 0
        else float("inf")
    )
    g6_pass = mc_maxdd_p95_pct_of_limit <= _G6_MAXDD_FRACTION_OF_LIMIT

    mc_breach_probability_12m = mc_symbol_result.block_bootstrap.breach_probability
    g7_pass = mc_breach_probability_12m < _G7_MAX_BREACH_PROB

    sensitivity_has_cliff = sensitivity_result.has_cliff
    sensitivity_max_degradation_pct = max(
        (perturbation.relative_drop for perturbation in sensitivity_result.perturbations),
        default=0.0,
    )
    g8_pass = (not sensitivity_has_cliff) and sensitivity_max_degradation_pct < _G8_MAX_DEGRADATION

    pf_cost_stress_1_5x = next(
        (
            outcome.profit_factor
            for outcome in sensitivity_result.cost_stress
            if outcome.multiplier == _G9_STRESS_MULTIPLIER
        ),
        float("-inf"),
    )
    g9_pass = pf_cost_stress_1_5x >= _G9_MIN_PF_STRESS

    gates_all_pass = (
        g1_pass
        and g2_pass
        and g3_pass
        and g4_pass
        and g5_pass
        and g6_pass
        and g7_pass
        and g8_pass
        and g9_pass
    )
    status = SymbolGateStatus.PASS if gates_all_pass else SymbolGateStatus.FAIL

    intent_counts = intent_authorization_counts(wfa_result.oos_ledger_cosido)
    sizing_evidence_insufficient = _is_sizing_evidence_insufficient(intent_counts)

    return SymbolGateOutcome(
        trades_oos_total=trades_oos_total,
        g1_pass=g1_pass,
        wfe=wfe,
        g2_pass=g2_pass,
        profit_factor=pf,
        g3_pass=g3_pass,
        dsr=dsr,
        g4_pass=g4_pass,
        pbo=pbo,
        g5_pass=g5_pass,
        mc_maxdd_p95_pct_of_limit=mc_maxdd_p95_pct_of_limit,
        g6_pass=g6_pass,
        mc_breach_probability_12m=mc_breach_probability_12m,
        g7_pass=g7_pass,
        sensitivity_has_cliff=sensitivity_has_cliff,
        sensitivity_max_degradation_pct=sensitivity_max_degradation_pct,
        g8_pass=g8_pass,
        pf_cost_stress_1_5x=pf_cost_stress_1_5x,
        g9_pass=g9_pass,
        status=status,
        sizing_evidence_insufficient=sizing_evidence_insufficient,
        intents_total=intent_counts.intents_total,
        intents_authorized=intent_counts.intents_authorized,
        rejections_by_reason=intent_counts.rejections_by_reason,
        dsr_pre_ledger_deflation=dsr_pre_ledger_deflation,
        n_trials_g4_effective=n_trials_g4_effective,
        ledger_extra_trials=ledger_extra_trials,
    )


def _not_applicable_symbol_gate_outcome(*, ledger_extra_trials: int) -> SymbolGateOutcome:
    """`SymbolGateOutcome` de un símbolo declarado 'no aplica' (D1): sin números que reportar."""
    nan = float("nan")
    return SymbolGateOutcome(
        trades_oos_total=0,
        g1_pass=False,
        wfe=nan,
        g2_pass=False,
        profit_factor=nan,
        g3_pass=False,
        dsr=nan,
        g4_pass=False,
        pbo=nan,
        g5_pass=False,
        mc_maxdd_p95_pct_of_limit=nan,
        g6_pass=False,
        mc_breach_probability_12m=nan,
        g7_pass=False,
        sensitivity_has_cliff=False,
        sensitivity_max_degradation_pct=nan,
        g8_pass=False,
        pf_cost_stress_1_5x=nan,
        g9_pass=False,
        status=SymbolGateStatus.NOT_APPLICABLE,
        sizing_evidence_insufficient=False,
        intents_total=0,
        intents_authorized=0,
        rejections_by_reason={},
        dsr_pre_ledger_deflation=nan,
        n_trials_g4_effective=0,
        ledger_extra_trials=ledger_extra_trials,
    )


@dataclass(frozen=True, slots=True)
class CandidateGateSummary:
    """Resumen congelado de gates G/C/P de un candidato (R67)."""

    candidate_id: str
    symbol_gate_outcomes: Mapping[str, SymbolGateOutcome]
    c1_fraction_passing: float
    c1_pass: bool
    c2_min_pf_non_passing: float
    c2_pass: bool
    p1_pass: bool
    p2_pass: bool
    p3_pass: bool
    p4_pass: bool
    p5_pass: bool
    p6_pass: bool
    p6_violating_symbols: Mapping[str, tuple[BreachKind, ...]]
    passes_g_c_p: bool
    # Change #51 (R4): símbolos con `sizing_evidence_insufficient=True`, agregados
    # hacia arriba sin colapsar/promediar. No participa de `passes_g_c_p`.
    symbols_with_insufficient_sizing_evidence: frozenset[str]
    # Change #130: denominador de C1 y declarados que nadie evaluó ni marcó 'no aplica'.
    declared_universe: frozenset[str]
    symbols_not_evaluated: frozenset[str]


def _evaluate_p1_to_p5(prop_sim_result: PropSimResult) -> tuple[bool, bool, bool, bool, bool]:
    """`(p1_pass, p2_pass, p3_pass, p4_pass, p5_pass)` contra las constantes `_P1..5` (R70).

    Compartido por `build_candidate_gate_summary` (candidato aislado) y `_compute_t2`
    (ensemble, R70): mismo criterio de umbrales para ambos, sin duplicar la
    comparación.
    """
    p1_pass = prop_sim_result.p_pass >= _P1_MIN_PASS
    p2_pass = prop_sim_result.expected_attempts <= _P2_MAX_ATTEMPTS
    p3_pass = prop_sim_result.p_daily_breach_funded_month < _P3_MAX_DAILY_BREACH
    p4_pass = prop_sim_result.median_funded_survival_months >= _P4_MIN_SURVIVAL_MONTHS
    p5_pass = prop_sim_result.payout_p25_12m > _P5_MIN_PAYOUT
    return p1_pass, p2_pass, p3_pass, p4_pass, p5_pass


def _p6_violating_symbols(
    wfa_results_by_symbol: Mapping[str, WfaResult],
) -> dict[str, tuple[BreachKind, ...]]:
    """`{symbol: (BreachKind, ...)}` de los símbolos con >=1 `BreachEvent` real (R62/R66)."""
    violating: dict[str, tuple[BreachKind, ...]] = {}
    for symbol, wfa_result in wfa_results_by_symbol.items():
        kinds = tuple(
            entry.payload.kind
            for entry in wfa_result.oos_ledger_cosido.entries
            if isinstance(entry.payload, BreachEvent)
        )
        if kinds:
            violating[symbol] = kinds
    return violating


def build_candidate_gate_summary(
    bundle: CandidateValidationBundle,
    house_rule: HouseRule,
    *,
    ledger_extra_trials: int = 0,
) -> CandidateGateSummary:
    """Construye `CandidateGateSummary` de `bundle`: gates G por símbolo + C1/C2 + P1-P6.

    `ledger_extra_trials` (Change #53) default `0`: con ledger ausente, comportamiento
    bit a bit idéntico al pre-Change (R12/R21). `house_rule` (Change #109, D8): G6
    lee `house_rule.max_loss_limit.amount` directo, ya no un porcentaje derivado de
    `starting_balance` — el parámetro `starting_balance` deja de ser necesario acá.
    """
    _check_min_declared_universe_size(bundle.candidate_id, bundle.declared_universe)

    symbol_gate_outcomes = {
        symbol: _build_symbol_gate_outcome(
            symbol,
            bundle.wfa_results_by_symbol[symbol],
            bundle.dsr_pbo_results_by_symbol[symbol],
            bundle.sensitivity_results_by_symbol[symbol],
            bundle.mc_symbol_results_by_symbol[symbol],
            house_rule,
            ledger_extra_trials=ledger_extra_trials,
        )
        for symbol in bundle.wfa_results_by_symbol
    }
    for symbol in sorted(bundle.not_applicable_symbols):
        symbol_gate_outcomes[symbol] = _not_applicable_symbol_gate_outcome(
            ledger_extra_trials=ledger_extra_trials
        )

    # R4: el denominador es el universo declarado, no lo que traiga el bundle.
    n_declared = len(bundle.declared_universe)
    n_passing = sum(
        1 for outcome in symbol_gate_outcomes.values() if outcome.status is SymbolGateStatus.PASS
    )
    c1_fraction_passing = n_passing / n_declared
    c1_pass = c1_fraction_passing >= _C1_MIN_FRACTION

    # D3: C2 sobre `FAIL` (idéntico a `not all_pass` sin 'no aplica'; `nan` no contamina `min`).
    non_passing_pf = [
        outcome.profit_factor
        for outcome in symbol_gate_outcomes.values()
        if outcome.status is SymbolGateStatus.FAIL
    ]
    c2_min_pf_non_passing = min(non_passing_pf) if non_passing_pf else float("inf")
    c2_pass = c2_min_pf_non_passing >= _C2_MIN_PF

    p1_pass, p2_pass, p3_pass, p4_pass, p5_pass = _evaluate_p1_to_p5(bundle.prop_sim_result)

    p6_violating = _p6_violating_symbols(bundle.wfa_results_by_symbol)
    p6_pass = not p6_violating

    passes_g_c_p = (
        c1_pass and c2_pass and p1_pass and p2_pass and p3_pass and p4_pass and p5_pass and p6_pass
    )

    symbols_with_insufficient_sizing_evidence = frozenset(
        symbol
        for symbol, outcome in symbol_gate_outcomes.items()
        if outcome.sizing_evidence_insufficient
    )

    return CandidateGateSummary(
        candidate_id=bundle.candidate_id,
        symbol_gate_outcomes=symbol_gate_outcomes,
        c1_fraction_passing=c1_fraction_passing,
        c1_pass=c1_pass,
        c2_min_pf_non_passing=c2_min_pf_non_passing,
        c2_pass=c2_pass,
        p1_pass=p1_pass,
        p2_pass=p2_pass,
        p3_pass=p3_pass,
        p4_pass=p4_pass,
        p5_pass=p5_pass,
        p6_pass=p6_pass,
        p6_violating_symbols=p6_violating,
        passes_g_c_p=passes_g_c_p,
        symbols_with_insufficient_sizing_evidence=symbols_with_insufficient_sizing_evidence,
        declared_universe=bundle.declared_universe,
        symbols_not_evaluated=(
            bundle.declared_universe
            - set(bundle.wfa_results_by_symbol)
            - bundle.not_applicable_symbols
        ),
    )


def _select_winning_candidate(
    candidates: Mapping[str, CandidateValidationBundle],
    candidate_summaries: Mapping[str, CandidateGateSummary],
) -> str | None:
    """Ganador del torneo entre los candidatos con `passes_g_c_p=True` (R72).

    Criterio total ordenado: mayor `prop_sim_result.payout_p25_12m`; desempate por
    mayor `median_funded_survival_months`; desempate final por `candidate_id`
    lexicográfico (determinismo, R94). `None` si ningún candidato pasa G+C+P.
    """
    passing_ids = [
        candidate_id
        for candidate_id, summary in candidate_summaries.items()
        if summary.passes_g_c_p
    ]
    if not passing_ids:
        return None

    def _sort_key(candidate_id: str) -> tuple[float, float, str]:
        prop_sim_result = candidates[candidate_id].prop_sim_result
        return (
            -prop_sim_result.payout_p25_12m,
            -prop_sim_result.median_funded_survival_months,
            candidate_id,
        )

    return min(passing_ids, key=_sort_key)


@dataclass(frozen=True, slots=True)
class TournamentDeflationOutcome:
    """Resultado congelado de la deflación de torneo T1 para el ganador (R71-R78)."""

    winning_candidate_id: str
    n_candidatos_torneo: int
    n_trials_signal_total_ganador: int
    n_trials_deflactado: int
    t1_dsr_pre_deflation: float
    t1_dsr: float
    t1_pass: bool


def _dsr_or_zero(returns: list[float], n_trials: int) -> float:
    """Invoca `deflated_sharpe_ratio` (R76); `0.0` si `n_trials=1` cae fuera del dominio del ppf.

    `_dsr.py` (H, cerrado, R119/R125) no admite `n_trials=1`
    (`_standard_normal_ppf(1.0 - 1.0/1) == _standard_normal_ppf(0.0)` queda fuera de
    `(0, 1)`; su propio docstring documenta que solo espera `n_trials` de `wfa.py`,
    `{9, 27}`). T1 sí necesita `n_trials=1` como referencia de trazabilidad "sin
    deflación" (R76); se captura el `ValueError` de dominio y se trata como
    degenerado — mismo criterio de "fail-soft a 0.0" que `deflated_sharpe_ratio` ya
    aplica para `len(returns)<2`/`std==0`/`denom<=0` — sin modificar el módulo
    cerrado.
    """
    try:
        return deflated_sharpe_ratio(returns, n_trials=n_trials)
    except ValueError:
        return 0.0


def _compute_t1(
    winning_candidate_id: str,
    candidates: Mapping[str, CandidateValidationBundle],
    *,
    no_go_iteration_used: bool = False,
    ledger_extra_trials: int,
) -> TournamentDeflationOutcome:
    """T1: deflación de torneo sobre la canasta diaria combinada del ganador (R71-R78).

    Reutiliza `_dsr.deflated_sharpe_ratio` **tal cual** (sin duplicar la fórmula,
    ADR-J6) y `_build_daily_basket` (compartida con `prop_sim.py`, ADR-J10).
    `n_candidatos_torneo = len(candidates)` (R71, nunca hardcodeado);
    `n_trials_deflactado = n_trials_signal_total_ganador + (n_candidatos_torneo - 1)`
    (R75), `+1` adicional si `no_go_iteration_used=True` (R95, la iteración cuenta
    como trial).
    """
    n_candidatos_torneo = len(candidates)
    winner_bundle = candidates[winning_candidate_id]
    n_trials_signal_total_ganador = sum(
        wfa_result.n_trials_signal_total
        for wfa_result in winner_bundle.wfa_results_by_symbol.values()
    )
    n_trials_deflactado = (
        n_trials_signal_total_ganador + (n_candidatos_torneo - 1) + ledger_extra_trials
    )
    if no_go_iteration_used:
        n_trials_deflactado += 1

    oos_ledgers_by_symbol = {
        symbol: wfa_result.oos_ledger_cosido
        for symbol, wfa_result in winner_bundle.wfa_results_by_symbol.items()
    }
    _basket_days, daily_totals = _build_daily_basket(oos_ledgers_by_symbol)
    daily_returns = [daily_totals[day] for day in sorted(daily_totals)]

    t1_dsr_pre_deflation = _dsr_or_zero(daily_returns, n_trials=1)
    t1_dsr = deflated_sharpe_ratio(daily_returns, n_trials=n_trials_deflactado)
    t1_pass = t1_dsr >= _T1_MIN_DSR

    return TournamentDeflationOutcome(
        winning_candidate_id=winning_candidate_id,
        n_candidatos_torneo=n_candidatos_torneo,
        n_trials_signal_total_ganador=n_trials_signal_total_ganador,
        n_trials_deflactado=n_trials_deflactado,
        t1_dsr_pre_deflation=t1_dsr_pre_deflation,
        t1_dsr=t1_dsr,
        t1_pass=t1_pass,
    )


def _candidate_daily_basket(
    bundle: CandidateValidationBundle,
) -> tuple[list[date], dict[date, float]]:
    """Canasta diaria combinada de `bundle` (compartida con `prop_sim.py`, ADR-J10, R73)."""
    oos_ledgers_by_symbol = {
        symbol: wfa_result.oos_ledger_cosido
        for symbol, wfa_result in bundle.wfa_results_by_symbol.items()
    }
    return _build_daily_basket(oos_ledgers_by_symbol)


def _pairwise_correlation(
    bundle_a: CandidateValidationBundle, bundle_b: CandidateValidationBundle
) -> float:
    """Correlación de Pearson (`numpy.corrcoef`) entre las canastas de dos candidatos (R79/R88).

    Restringida a la **intersección** de `trading_day`s; `VerdictConfigError` si
    quedan `<2` días comunes (R2d/R79). Simétrica por construcción (R88):
    `corrcoef` es simétrico y la intersección de conjuntos no depende del orden.
    """
    _days_a, totals_a = _candidate_daily_basket(bundle_a)
    _days_b, totals_b = _candidate_daily_basket(bundle_b)
    common_days = sorted(set(totals_a) & set(totals_b))
    if len(common_days) < 2:
        message = (
            f"_pairwise_correlation(candidate_id={bundle_a.candidate_id!r}, "
            f"{bundle_b.candidate_id!r}): intersección de trading_day con "
            f"{len(common_days)} días, se requieren >= 2 (R2d/R79)."
        )
        raise VerdictConfigError(message)

    values_a = np.array([totals_a[day] for day in common_days], dtype=float)
    values_b = np.array([totals_b[day] for day in common_days], dtype=float)
    return float(np.corrcoef(values_a, values_b)[0, 1])


def _pair_key(candidate_id_a: str, candidate_id_b: str) -> tuple[str, str]:
    """Clave canónica (orden alfabético) para un par de `candidate_id` (R88)."""
    return (
        (candidate_id_a, candidate_id_b)
        if candidate_id_a < candidate_id_b
        else (
            candidate_id_b,
            candidate_id_a,
        )
    )


def _max_mutually_eligible_subset(
    candidate_ids: Sequence[str], correlations: Mapping[tuple[str, str], float]
) -> tuple[str, ...]:
    """Subconjunto máximo mutuamente elegible dos a dos (correlación `< 0.3`, R80/ADR-J7).

    Enumeración decreciente de subconjuntos, determinista por orden canónico de
    `candidate_id` (`itertools.combinations` sobre la lista ya ordenada): retorna el
    primer subconjunto de tamaño máximo donde **todas** las correlaciones por pares
    son elegibles. `()` si ningún par de 2+ candidatos es mutuamente elegible.
    """
    sorted_ids = sorted(candidate_ids)
    for size in range(len(sorted_ids), 1, -1):
        for subset in itertools.combinations(sorted_ids, size):
            if all(
                correlations[_pair_key(a, b)] < _T2_MAX_CORRELATION
                for a, b in itertools.combinations(subset, 2)
            ):
                return subset
    return ()


def _inverse_volatility_weights(
    member_ids: Sequence[str],
    baskets_by_id: Mapping[str, tuple[list[date], dict[date, float]]],
    common_days: Sequence[date],
) -> dict[str, float]:
    """Pesos vol-inversa normalizados (`sum(w_i) == 1.0`) sobre `common_days` (R81).

    `VerdictConfigError` si algún `std_i == 0.0` (canasta constante: peso
    infinito/indefinido).
    """
    stds: dict[str, float] = {}
    for candidate_id in member_ids:
        _days, totals = baskets_by_id[candidate_id]
        values = np.array([totals[day] for day in common_days], dtype=float)
        std = float(values.std())
        if std == 0.0:
            message = (
                f"_inverse_volatility_weights: candidate_id={candidate_id!r} tiene "
                "desviación estándar 0.0 sobre la intersección del subconjunto elegible (R81)."
            )
            raise VerdictConfigError(message)
        stds[candidate_id] = std

    inverse = {candidate_id: 1.0 / std for candidate_id, std in stds.items()}
    total_inverse = sum(inverse.values())
    return {candidate_id: value / total_inverse for candidate_id, value in inverse.items()}


@dataclass(frozen=True, slots=True)
class EnsembleResult:
    """Resultado congelado del ensemble T2 (R83): subconjunto elegible + pesos + prop_sim."""

    member_candidate_ids: tuple[str, ...]
    pairwise_correlations: Mapping[tuple[str, str], float]
    weights: Mapping[str, float]
    prop_sim_result: PropSimResult
    passes_p_gates: bool


def _compute_t2(
    candidates: Mapping[str, CandidateValidationBundle],
    candidate_summaries: Mapping[str, CandidateGateSummary],
    starting_balance: float,
    firm_profile: FirmProfile,
    prop_economics_profile: PropEconomicsProfile,
    ensemble_prop_sim_config: PropSimConfig,
) -> EnsembleResult | None:
    """T2: ensemble por correlación Pearson + vol-inversa (R79-R90, ADR-J7).

    `None` si `<2` candidatos pasan G+C+P (R85) o si ningún par G+C+P tiene
    correlación `< 0.3` (R84). Invoca `simulate_challenge_paths` (núcleo puro
    reutilizado de `prop_sim.py`, R82) con `ensemble_prop_sim_config.seed`
    **independiente** de los seeds de cada candidato — responsabilidad del
    llamador de `run_verdict` de pasar un `PropSimConfig` con seed propio. `P6` no
    aplica al ensemble (sin `Ledger` real, R83).

    `firm_profile` es un parámetro necesario para invocar `simulate_challenge_paths`
    (breach diario, R25/R33) que no aparece en la firma pseudocódigo de
    `run_verdict` en `design.md` §1.9 — omisión del diseño detectada en
    implementación: sin este parámetro el ensemble no es computable. Se añade aquí y
    se propaga por `run_verdict` (B4).
    """
    passing_ids = sorted(
        candidate_id
        for candidate_id, summary in candidate_summaries.items()
        if summary.passes_g_c_p
    )
    if len(passing_ids) < 2:
        return None

    correlations: dict[tuple[str, str], float] = {}
    for candidate_id_a, candidate_id_b in itertools.combinations(passing_ids, 2):
        correlations[_pair_key(candidate_id_a, candidate_id_b)] = _pairwise_correlation(
            candidates[candidate_id_a], candidates[candidate_id_b]
        )

    subset = _max_mutually_eligible_subset(passing_ids, correlations)
    if len(subset) < 2:
        return None

    baskets_by_id = {
        candidate_id: _candidate_daily_basket(candidates[candidate_id]) for candidate_id in subset
    }
    common_days = set(baskets_by_id[subset[0]][1])
    for candidate_id in subset[1:]:
        common_days &= set(baskets_by_id[candidate_id][1])
    common_days_sorted = sorted(common_days)
    if len(common_days_sorted) < 2:
        message = (
            f"_compute_t2: intersección de trading_day del subconjunto {subset!r} tiene "
            f"{len(common_days_sorted)} días, se requieren >= 2 (R2d/R79)."
        )
        raise VerdictConfigError(message)

    weights = _inverse_volatility_weights(subset, baskets_by_id, common_days_sorted)

    daily_pnl_ensemble = {
        day: sum(
            weights[candidate_id] * baskets_by_id[candidate_id][1][day] for candidate_id in subset
        )
        for day in common_days_sorted
    }

    ensemble_prop_sim_result = simulate_challenge_paths(
        daily_pnl_ensemble,
        starting_balance,
        prop_economics_profile,
        firm_profile,
        ensemble_prop_sim_config,
        "ensemble",
    )
    passes_p_gates = all(_evaluate_p1_to_p5(ensemble_prop_sim_result))

    return EnsembleResult(
        member_candidate_ids=subset,
        pairwise_correlations=correlations,
        weights=weights,
        prop_sim_result=ensemble_prop_sim_result,
        passes_p_gates=passes_p_gates,
    )


class VerdictKind(StrEnum):
    """Veredicto final del torneo (R91), exactamente 4 miembros."""

    GO = "go"
    GO_ENSEMBLE = "go-ensemble"
    GO_PARCIAL = "go-parcial"
    NO_GO = "no-go"


@dataclass(frozen=True, slots=True)
class VerdictResult:
    """Resultado congelado del veredicto de torneo completo (R93)."""

    verdict: VerdictKind
    winning_candidate_id: str | None
    candidate_summaries: Mapping[str, CandidateGateSummary]
    t1_dsr: float | None
    t1_dsr_pre_deflation: float | None
    n_candidatos_torneo: int
    n_trials_deflactado: int | None
    ensemble: EnsembleResult | None
    economics_confirmed: bool
    no_go_iteration_used: bool = False
    # Change #53 (Q8): estado del ledger de ensayos CONSUMIDO por esta invocación de
    # `run_verdict` (snapshot único, R94). `None` si `ledger=None` (comportamiento
    # pre-Change, R12).
    trial_ledger_snapshot: TrialLedgerSummary | None = None
    ledger_extra_trials: int = 0


def _require_candidate_config(bundle: CandidateValidationBundle) -> Mapping[str, object]:
    """`bundle.candidate_config`, fail-fast si es `None` (Q5, D2: nunca omisión silenciosa)."""
    if bundle.candidate_config is None:
        message = (
            f"_require_candidate_config(candidate_id={bundle.candidate_id!r}): "
            "candidate_config es None; con un ledger de ensayos no-None, cada bundle "
            "evaluado debe traer su configuración completa (Q5)."
        )
        raise TrialLedgerConfigError(message)
    return bundle.candidate_config


def _trial_id_for_bundle(ledger: TrialLedger, bundle: CandidateValidationBundle) -> str:
    """`trial_id` de `bundle` vía `ledger.trial_id_for_config` (PR-2): única derivación
    sancionada, nunca calculada ni pasada a mano por el llamador.
    """
    return ledger.trial_id_for_config(_require_candidate_config(bundle))


def record_trial_completions(
    ledger: TrialLedger,
    candidates: Mapping[str, CandidateValidationBundle],
    *,
    recorded_at_utc: str | None = None,
) -> tuple[str, ...]:
    """Borde de escritura (R15 enmendado, Q10): registra un `TrialRecord` `WFA_COMPLETADO`
    por cada `(candidate_id, symbol)` de `candidates`, usando las claves de identidad
    institucional del `TrialIdentityContext` de `ledger`. `run_verdict` no invoca esta
    función: se llama en el borde del llamador, junto a `write_verdict_artifacts` (Q8).

    Devuelve los `trial_id` registrados en orden canónico de `candidate_id` (determinismo,
    R94). Idempotente por construcción (`TrialLedger.record` delega en `append_trial`, R8).
    """
    trial_ids: list[str] = []
    for candidate_id in sorted(candidates):
        bundle = candidates[candidate_id]
        candidate_config = _require_candidate_config(bundle)
        for symbol in sorted(bundle.wfa_results_by_symbol):
            record = ledger.build_record(
                candidate_id,
                symbol,
                candidate_config,
                TrialOutcomeKind.WFA_COMPLETADO,
                recorded_at_utc=recorded_at_utc,
            )
            ledger.record(record)
            trial_ids.append(record.trial_id)
    return tuple(trial_ids)


def run_verdict(
    candidates: Mapping[str, CandidateValidationBundle],
    starting_balance: float,
    firm_profile: FirmProfile,
    prop_economics_profile: PropEconomicsProfile,
    ensemble_prop_sim_config: PropSimConfig,
    *,
    no_go_iteration_used: bool = False,
    ledger: TrialLedger | None = None,
) -> VerdictResult:
    """Veredicto de torneo completo (R91-R95bis).

    `firm_profile` es un parámetro necesario para `_compute_t2`/
    `simulate_challenge_paths` (breach diario, R25/R33) que no aparece en la firma
    pseudocódigo de `run_verdict` en `design.md` §1.9 — omisión de diseño detectada
    en implementación (sin este parámetro el ensemble no es computable); se añade
    aquí, inmediatamente después de `starting_balance`, siguiendo el mismo orden de
    parámetros que `prop_sim.run_prop_sim`.

    Prioridad estricta (R92): (a) `ensemble is not None and
    ensemble.passes_p_gates` -> `GO_ENSEMBLE`; (b) ganador `passes_g_c_p and
    t1_pass` -> `GO`; (c) resto -> `NO_GO`. Un candidato que falla C1 nunca emite
    `GO_PARCIAL` (Change #130, R12; el miembro del enum se conserva sin emisor hasta
    B.8). Invariancia al orden (R94/R95bis): el ganador se elige por criterio total
    ordenado (`payout_p25_12m`,
    desempate `median_funded_survival_months`, desempate final `candidate_id`
    lexicográfico); T2 itera en orden canónico de `candidate_id`. Permutar
    `candidates` no cambia `verdict`/`winning_candidate_id`.
    """
    if not candidates:
        message = "run_verdict: candidates está vacío, no hay ningún candidato que evaluar (R2a)."
        raise VerdictConfigError(message)
    if starting_balance <= 0:
        message = f"run_verdict: starting_balance={starting_balance!r} debe ser > 0 (R2c)."
        raise VerdictConfigError(message)
    house_rule = firm_profile.house_rule
    if house_rule is None:
        message = (
            f"La ficha de firma {firm_profile.name!r} no declara 'house_rule' (no es una "
            "prop firm, D2); run_verdict no puede evaluar ningún candidato del torneo "
            f"({sorted(candidates)!r})."
        )
        raise VerdictConfigError(message)

    # Change #53 (Q4/Q8): un único snapshot de lectura, sin efectos secundarios (Q10).
    # `ledger=None` -> extra=0, comportamiento bit a bit idéntico al pre-Change (R12).
    trial_ledger_snapshot: TrialLedgerSummary | None = None
    ledger_extra_trials = 0
    if ledger is not None:
        trial_ledger_snapshot = ledger.read_summary()
        own_trial_ids = {_trial_id_for_bundle(ledger, bundle) for bundle in candidates.values()}
        ledger_extra_trials = len(trial_ledger_snapshot.trial_ids - own_trial_ids)

    candidate_summaries = {
        candidate_id: build_candidate_gate_summary(
            bundle, house_rule, ledger_extra_trials=ledger_extra_trials
        )
        for candidate_id, bundle in candidates.items()
    }
    n_candidatos_torneo = len(candidates)
    # D4b: `economics_confirmed` deja de inferirse de un hash (falso positivo/negativo
    # en las dos direcciones); campo explícito de la ficha.
    economics_confirmed = not prop_economics_profile.is_placeholder

    winning_candidate_id = _select_winning_candidate(candidates, candidate_summaries)
    t1: TournamentDeflationOutcome | None = None
    if winning_candidate_id is not None:
        t1 = _compute_t1(
            winning_candidate_id,
            candidates,
            no_go_iteration_used=no_go_iteration_used,
            ledger_extra_trials=ledger_extra_trials,
        )

    ensemble = _compute_t2(
        candidates,
        candidate_summaries,
        starting_balance,
        firm_profile,
        prop_economics_profile,
        ensemble_prop_sim_config,
    )

    if ensemble is not None and ensemble.passes_p_gates:
        verdict = VerdictKind.GO_ENSEMBLE
    elif (
        winning_candidate_id is not None
        and candidate_summaries[winning_candidate_id].passes_g_c_p
        and t1 is not None
        and t1.t1_pass
    ):
        verdict = VerdictKind.GO
    else:
        # Change #130 (R12): sin GO-PARCIAL por C1 fallido; quien falla C1 es NO-GO
        # (SSoT `:1217-1220`). `GO_PARCIAL` queda sin emisor hasta B.8.
        verdict = VerdictKind.NO_GO

    return VerdictResult(
        verdict=verdict,
        winning_candidate_id=winning_candidate_id,
        candidate_summaries=candidate_summaries,
        t1_dsr=t1.t1_dsr if t1 is not None else None,
        t1_dsr_pre_deflation=t1.t1_dsr_pre_deflation if t1 is not None else None,
        n_candidatos_torneo=n_candidatos_torneo,
        n_trials_deflactado=t1.n_trials_deflactado if t1 is not None else None,
        ensemble=ensemble,
        economics_confirmed=economics_confirmed,
        no_go_iteration_used=no_go_iteration_used,
        trial_ledger_snapshot=trial_ledger_snapshot,
        ledger_extra_trials=ledger_extra_trials,
    )


_P3_WARNING = (
    "**Advertencia (decisión 4):** P3 (probabilidad de breach diario en un mes fondeado) se "
    "evalúa **solo** sobre la base balance-a-balance (cierre-a-cierre); es una **cota inferior "
    "conservadora**. La base de equity flotante intradía real puede disparar el breach diario "
    "antes de lo que este proxy indica."
)
_D7_BIAS_WARNING = (
    "`max_loss_limit` evaluado con el proxy **cierre-a-cierre** de ADR-J4: "
    "**subestima** la probabilidad de breach, por lo tanto **sesga `p_pass` al alza**. "
    "No es un margen de seguridad."
)
_DH4_FUNDED_STARTING_BALANCE_NOTICE = (
    "`funded_starting_balance` no aplicado: PA-106-5 fuera de alcance del #109 "
    "(issue de continuación #112)."
)
_ECONOMICS_WARNING = (
    "**Advertencia (decisión 2):** la economía del challenge "
    "(`challenge_cost_pct_of_balance`/`profit_split_pct`) usa valores **placeholder**, aún no "
    "confirmados contra los términos vigentes de The5ers. Un veredicto GO no debe leerse como "
    "decisión de negocio definitiva hasta confirmar ambos valores."
)


def _trial_ledger_payload(snapshot: TrialLedgerSummary, ledger_extra_trials: int) -> dict:
    """Payload serializable de `snapshot` (Q2), compartido por el manifest y el tearsheet.

    Única fuente de las cifras del ledger: paridad por construcción, mismo patrón que
    `_candidate_summary_payload`.
    """
    return {
        "n_trials_total": snapshot.n_trials_total,
        "n_rows": snapshot.n_rows,
        "n_duplicate_trial_ids": snapshot.n_duplicate_trial_ids,
        "content_hash": snapshot.content_hash,
        "n_extra_trials_applied": ledger_extra_trials,
        "n_trials_by_symbol": dict(snapshot.n_trials_by_symbol),
        "n_trials_by_candidate_family": dict(snapshot.n_trials_by_candidate_family),
        "n_trials_by_firm_profile_hash": dict(snapshot.n_trials_by_firm_profile_hash),
    }


def _candidate_summary_payload(summary: CandidateGateSummary) -> dict:
    """Payload serializable de `summary`, compartido por `render_tearsheet` y el manifest (R97).

    Única fuente de las cifras por candidato: tearsheet y manifest se generan a
    partir del **mismo** diccionario, garantizando paridad por construcción (no
    solo por convención).
    """
    return {
        "passes_g_c_p": summary.passes_g_c_p,
        "c1_fraction_passing": summary.c1_fraction_passing,
        "c1_pass": summary.c1_pass,
        "c2_min_pf_non_passing": summary.c2_min_pf_non_passing,
        "c2_pass": summary.c2_pass,
        "p1_pass": summary.p1_pass,
        "p2_pass": summary.p2_pass,
        "p3_pass": summary.p3_pass,
        "p4_pass": summary.p4_pass,
        "p5_pass": summary.p5_pass,
        "p6_pass": summary.p6_pass,
        "p6_violating_symbols": {
            symbol: [kind.value for kind in kinds]
            for symbol, kinds in summary.p6_violating_symbols.items()
        },
        "symbol_gate_outcomes": {
            symbol: {
                "trades_oos_total": outcome.trades_oos_total,
                "g1_pass": outcome.g1_pass,
                "wfe": outcome.wfe,
                "g2_pass": outcome.g2_pass,
                "profit_factor": outcome.profit_factor,
                "g3_pass": outcome.g3_pass,
                "dsr": outcome.dsr,
                "g4_pass": outcome.g4_pass,
                "pbo": outcome.pbo,
                "g5_pass": outcome.g5_pass,
                "mc_maxdd_p95_pct_of_limit": outcome.mc_maxdd_p95_pct_of_limit,
                "g6_pass": outcome.g6_pass,
                "mc_breach_probability_12m": outcome.mc_breach_probability_12m,
                "g7_pass": outcome.g7_pass,
                "sensitivity_has_cliff": outcome.sensitivity_has_cliff,
                "sensitivity_max_degradation_pct": outcome.sensitivity_max_degradation_pct,
                "g8_pass": outcome.g8_pass,
                "pf_cost_stress_1_5x": outcome.pf_cost_stress_1_5x,
                "g9_pass": outcome.g9_pass,
                "all_pass": outcome.all_pass,
                "status": outcome.status.value,
                "sizing_evidence_insufficient": outcome.sizing_evidence_insufficient,
                "intents_total": outcome.intents_total,
                "intents_authorized": outcome.intents_authorized,
                "rejections_by_reason": dict(sorted(outcome.rejections_by_reason.items())),
            }
            for symbol, outcome in summary.symbol_gate_outcomes.items()
        },
        "symbols_with_insufficient_sizing_evidence": sorted(
            summary.symbols_with_insufficient_sizing_evidence
        ),
        "declared_universe": sorted(summary.declared_universe),
        "symbols_evaluated": sorted(
            symbol
            for symbol, outcome in summary.symbol_gate_outcomes.items()
            if outcome.status is not SymbolGateStatus.NOT_APPLICABLE
        ),
        "symbols_not_evaluated": sorted(summary.symbols_not_evaluated),
    }


def render_tearsheet(result: VerdictResult) -> str:
    """Tearsheet Markdown puro de `result`, sin I/O (R96/R104).

    Generado del **mismo** `VerdictResult` que el manifest (R97, única fuente de
    verdad, vía `_candidate_summary_payload`). Siempre incluye la advertencia de
    cota inferior de P3 (decisión 4); si `economics_confirmed=False`, añade también
    la advertencia de economía placeholder (decisión 2, R107). Sin
    `quantstats`/`matplotlib` (R104): Markdown puro.
    """
    lines: list[str] = [
        f"# Veredicto de torneo: {result.verdict.value.upper()}",
        "",
        f"- **Ganador**: {result.winning_candidate_id or '(ninguno)'}",
        f"- **Candidatos en torneo**: {result.n_candidatos_torneo}",
        f"- **Economía confirmada**: {result.economics_confirmed}",
        "",
        f"> {_P3_WARNING}",
        "",
        f"> {_D7_BIAS_WARNING}",
        "",
        f"> {_DH4_FUNDED_STARTING_BALANCE_NOTICE}",
    ]
    if not result.economics_confirmed:
        lines.append(">")
        lines.append(f"> {_ECONOMICS_WARNING}")
    lines.append("")

    lines.append("## Candidatos")
    for candidate_id, summary in result.candidate_summaries.items():
        payload = _candidate_summary_payload(summary)
        lines.append(f"### `{candidate_id}`")
        lines.append(f"- `passes_g_c_p`: {payload['passes_g_c_p']}")
        n_universe = len(payload["declared_universe"])
        no_evaluados = payload["symbols_not_evaluated"]
        lines.append(
            f"- Universo declarado (|U|={n_universe}): "
            + ", ".join(payload["declared_universe"])
            + "; no evaluados (cuentan como no superados): "
            + (", ".join(no_evaluados) if no_evaluados else "(ninguno)")
        )
        lines.append(
            f"- C1 sobre |U|={n_universe}: "
            f"{payload['c1_fraction_passing']:.4f} (pass={payload['c1_pass']}); "
            f"C2: {payload['c2_min_pf_non_passing']:.4f} (pass={payload['c2_pass']})"
        )
        lines.append("- P1..P6: " + ", ".join(f"P{i}={payload[f'p{i}_pass']}" for i in range(1, 7)))
        symbols_sin_evidencia = payload["symbols_with_insufficient_sizing_evidence"]
        lines.append(
            "- Símbolos sin evidencia de sizing: "
            + (", ".join(symbols_sin_evidencia) if symbols_sin_evidencia else "(ninguno)")
        )
        lines.append("")
        lines.append(
            "| symbol | trades | g1 | wfe | g2 | pf | g3 | dsr | g4 | pbo | g5 | "
            "maxdd/lim | g6 | breach% | g7 | cliff | degrad% | g8 | pf_stress | g9 | all | "
            "status | sizing_insuf |"
        )
        lines.append(
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
            "---|---|"
        )
        for symbol, outcome in payload["symbol_gate_outcomes"].items():
            lines.append(
                f"| {symbol} | {outcome['trades_oos_total']} | {outcome['g1_pass']} | "
                f"{outcome['wfe']:.3f} | {outcome['g2_pass']} | {outcome['profit_factor']:.3f} | "
                f"{outcome['g3_pass']} | {outcome['dsr']:.3f} | {outcome['g4_pass']} | "
                f"{outcome['pbo']:.3f} | {outcome['g5_pass']} | "
                f"{outcome['mc_maxdd_p95_pct_of_limit']:.3f} | {outcome['g6_pass']} | "
                f"{outcome['mc_breach_probability_12m']:.3f} | {outcome['g7_pass']} | "
                f"{outcome['sensitivity_has_cliff']} | "
                f"{outcome['sensitivity_max_degradation_pct']:.3f} | {outcome['g8_pass']} | "
                f"{outcome['pf_cost_stress_1_5x']:.3f} | {outcome['g9_pass']} | "
                f"{outcome['all_pass']} | {outcome['status']} | "
                f"{outcome['sizing_evidence_insufficient']} |"
            )
        lines.append("")

    lines.append("## T1 (deflación de torneo)")
    if result.t1_dsr is not None:
        lines.append(f"- DSR pre-deflación: {result.t1_dsr_pre_deflation:.4f}")
        lines.append(f"- DSR post-deflación: {result.t1_dsr:.4f}")
        lines.append(f"- n_trials_deflactado: {result.n_trials_deflactado}")
    else:
        lines.append("- No evaluado (ningún candidato pasó G+C+P).")
    lines.append("")

    if result.trial_ledger_snapshot is not None:
        ledger_payload = _trial_ledger_payload(
            result.trial_ledger_snapshot, result.ledger_extra_trials
        )
        lines.append("## Ledger de ensayos")
        lines.append(
            f"- n_trials_total: {ledger_payload['n_trials_total']}, "
            f"n_extra_trials_applied: {ledger_payload['n_extra_trials_applied']}, "
            f"content_hash: {ledger_payload['content_hash']}"
        )
        lines.append("")

    lines.append("## T2 (ensemble)")
    if result.ensemble is not None:
        ensemble = result.ensemble
        lines.append(f"- Miembros: {', '.join(ensemble.member_candidate_ids)}")
        lines.append(f"- Pasa gates P: {ensemble.passes_p_gates}")
        lines.append("- Correlaciones por par:")
        for (candidate_a, candidate_b), corr in sorted(ensemble.pairwise_correlations.items()):
            lines.append(f"  - ({candidate_a}, {candidate_b}): {corr:.4f}")
        lines.append("- Pesos:")
        for candidate_id, weight in sorted(ensemble.weights.items()):
            lines.append(f"  - {candidate_id}: {weight:.4f}")
    else:
        lines.append("- No aplica (ningún subconjunto mutuamente elegible).")
    lines.append("")

    return "\n".join(lines)


def _purged_cv_summary_payload(
    purged_cv_results_by_candidate: Mapping[str, Mapping[str, PurgedCvResult]],
) -> dict:
    """Bloque informativo de diagnóstico del Purged K-Fold (R106), no participa en el veredicto."""
    summary: dict = {
        candidate_id: {
            symbol: {
                "n_folds": result.config.n_folds,
                "total_trades": result.total_trades,
                "purged_trade_count_sum": sum(fold.purged_trade_count for fold in result.folds),
            }
            for symbol, result in by_symbol.items()
        }
        for candidate_id, by_symbol in purged_cv_results_by_candidate.items()
    }
    summary["_note"] = "diagnóstico informativo, no participa en el veredicto (R106)"
    return summary


def _check_identity_maps_share_keys(
    dataset_hash_by_symbol: Mapping[str, str],
    costs_hash_by_symbol: Mapping[str, str],
    friction_status_by_symbol: Mapping[str, str],
) -> None:
    """Los tres mapas por símbolo del manifest cubren los mismos símbolos (Change #135, D6).

    Un manifest no declara costos de un símbolo que no evaluó, ni evalúa uno sin declarar
    sus costos. Cubre también el camino sin ledger, donde no corre la guarda de R16.
    """
    dataset_keys = sorted(dataset_hash_by_symbol)
    costs_keys = sorted(costs_hash_by_symbol)
    friction_keys = sorted(friction_status_by_symbol)
    if not dataset_keys == costs_keys == friction_keys:
        message = (
            "Los mapas por símbolo del manifest deben tener las mismas claves (Change #135, "
            f"D6): dataset_hash_by_symbol={dataset_keys!r}, "
            f"costs_hash_by_symbol={costs_keys!r}, "
            f"friction_status_by_symbol={friction_keys!r}."
        )
        raise VerdictConfigError(message)


def _friction_status_section(friction_status_by_symbol: Mapping[str, str]) -> str:
    """Sección del tearsheet con la marca de fricción por símbolo (Change #135, AE5)."""
    lines = ["", "## Costos de fricción", ""]
    for symbol in sorted(friction_status_by_symbol):
        status = friction_status_by_symbol[symbol]
        if status == _FRICTION_PROVISIONAL:
            lines.append(
                f"- `{symbol}`: spread y deslizamiento provisionales hasta B.4b "
                f"(piso sin medición de mercado; `{status}`)."
            )
        else:
            lines.append(f"- `{symbol}`: `{status}`.")
    return "\n".join(lines) + "\n"


def verdict_result_to_manifest_json(
    result: VerdictResult,
    config_version: str,
    dataset_hash_by_symbol: Mapping[str, str],
    firm_profile_hash: str,
    exit_geometry_hash: str,
    house_rule_hash: str,
    costs_hash_by_symbol: Mapping[str, str],
    friction_status_by_symbol: Mapping[str, str],
    prop_economics_profile_hash_value: str,
    seeds: Mapping[str, Mapping[str, int]],
    git_commit: str,
    purged_cv_results_by_candidate: Mapping[str, Mapping[str, PurgedCvResult]] | None = None,
) -> str:
    """Serializa `result` a JSON determinista byte a byte (`sort_keys=True`, R98/R103).

    Campos mínimos de R98: `config_version`, `dataset_hash_by_symbol`,
    `firm_profile_hash`, `exit_geometry_hash`, `house_rule_hash` (Change #109, D9:
    sustituyen a `risk_profile_hash`), `costs_hash_by_symbol` y
    `friction_status_by_symbol` (Change #135, con las mismas claves que
    `dataset_hash_by_symbol`, D6), `prop_economics_profile_hash`,
    `candidate_ids`, `winning_candidate_id`, `verdict`, `seeds`, `git_commit`,
    `n_candidatos_torneo`, `n_trials_deflactado`, `t1_dsr`/`t1_dsr_pre_deflation`,
    `economics_confirmed`, `prop_sim_bias` (D7: sesgo del proxy cierre-a-cierre),
    resultados por candidato (mismos campos que el tearsheet, R97) y
    `purged_cv_summary` si `purged_cv_results_by_candidate` no es `None` (R106).
    Fuera de `__all__` (§1.10): detalle de composición de `write_verdict_artifacts`.
    """
    _check_identity_maps_share_keys(
        dataset_hash_by_symbol, costs_hash_by_symbol, friction_status_by_symbol
    )
    payload: dict = {
        "config_version": config_version,
        "verdict_schema_version": CONFIG_VERSION,
        "dataset_hash_by_symbol": dict(dataset_hash_by_symbol),
        "firm_profile_hash": firm_profile_hash,
        "exit_geometry_hash": exit_geometry_hash,
        "house_rule_hash": house_rule_hash,
        "costs_hash_by_symbol": dict(costs_hash_by_symbol),
        "friction_status_by_symbol": dict(friction_status_by_symbol),
        "prop_economics_profile_hash": prop_economics_profile_hash_value,
        "candidate_ids": sorted(result.candidate_summaries),
        "winning_candidate_id": result.winning_candidate_id,
        "verdict": result.verdict.value,
        "seeds": {candidate_id: dict(value) for candidate_id, value in seeds.items()},
        "git_commit": git_commit,
        "n_candidatos_torneo": result.n_candidatos_torneo,
        "n_trials_deflactado": result.n_trials_deflactado,
        "t1_dsr": result.t1_dsr,
        "t1_dsr_pre_deflation": result.t1_dsr_pre_deflation,
        "economics_confirmed": result.economics_confirmed,
        "no_go_iteration_used": result.no_go_iteration_used,
        "prop_sim_bias": {
            "breach_evaluation_basis": BreachEvaluationBasis.CLOSE_TO_CLOSE_PROXY.value,
            "bias_direction": BiasDirection.UNDERESTIMATES_BREACH.value,
            "funded_starting_balance_aplicado": False,
            "nota": "funded_starting_balance no aplicado: PA-106-5 fuera de alcance del #109",
        },
        "candidates": {
            candidate_id: _candidate_summary_payload(summary)
            for candidate_id, summary in result.candidate_summaries.items()
        },
    }
    if purged_cv_results_by_candidate is not None:
        payload["purged_cv_summary"] = _purged_cv_summary_payload(purged_cv_results_by_candidate)
    if result.trial_ledger_snapshot is not None:
        # Change #53 (R16/Q2): única clave nueva de primer nivel, emitida siempre que el
        # snapshot no sea None (incluso vacío); ausente con ledger=None (A13).
        payload["trial_ledger"] = _trial_ledger_payload(
            result.trial_ledger_snapshot, result.ledger_extra_trials
        )

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def manifest_json_to_verdict_summary(raw: str) -> Mapping[str, object]:
    """Reconstruye los escalares serializables de `raw` (round-trip, R99/R105).

    No reconstruye las dataclasses anidadas (`WfaResult`/`DsrPboResult`/etc., que
    nunca se serializan); solo los escalares/mapas ya presentes en el JSON. Fuera de
    `__all__` (§1.10).
    """
    return json.loads(raw)


def write_verdict_artifacts(
    result: VerdictResult,
    output_dir: Path,
    config_version: str,
    dataset_hash_by_symbol: Mapping[str, str],
    firm_profile_hash: str,
    exit_geometry_hash: str,
    house_rule_hash: str,
    costs_hash_by_symbol: Mapping[str, str],
    friction_status_by_symbol: Mapping[str, str],
    prop_economics_profile_hash_value: str,
    seeds: Mapping[str, Mapping[str, int]],
    git_commit: str | None = None,
    purged_cv_results_by_candidate: Mapping[str, Mapping[str, PurgedCvResult]] | None = None,
) -> tuple[Path, Path]:
    """Única I/O de escritura del Change (R100-R102): `manifest.json` + `tearsheet.md`.

    `output_dir` siempre provisto por el llamador (sin ruta por defecto).
    `git_commit is None` -> `current_git_commit()` (`genesis.data.metadata`),
    propagando `GenesisDataError` sin capturar (R101). El tearsheet agrega una sección con
    la marca de fricción por símbolo (Change #135, AE5).
    """
    resolved_git_commit = git_commit if git_commit is not None else current_git_commit()
    manifest_json = verdict_result_to_manifest_json(
        result,
        config_version=config_version,
        dataset_hash_by_symbol=dataset_hash_by_symbol,
        firm_profile_hash=firm_profile_hash,
        exit_geometry_hash=exit_geometry_hash,
        house_rule_hash=house_rule_hash,
        costs_hash_by_symbol=costs_hash_by_symbol,
        friction_status_by_symbol=friction_status_by_symbol,
        prop_economics_profile_hash_value=prop_economics_profile_hash_value,
        seeds=seeds,
        git_commit=resolved_git_commit,
        purged_cv_results_by_candidate=purged_cv_results_by_candidate,
    )
    tearsheet_markdown = render_tearsheet(result) + _friction_status_section(
        friction_status_by_symbol
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    tearsheet_path = output_dir / "tearsheet.md"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    tearsheet_path.write_text(tearsheet_markdown, encoding="utf-8")
    return manifest_path, tearsheet_path
