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

from collections.abc import Mapping
from dataclasses import dataclass

from genesis.backtest.ledger import BreachEvent, BreachKind
from genesis.backtest.metrics import profit_factor
from genesis.backtest.risk_profile import RiskProfile
from genesis.validation._returns import extract_trade_returns
from genesis.validation.dsr_pbo import DsrPboResult
from genesis.validation.errors import VerdictConfigError
from genesis.validation.montecarlo import McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import PropSimResult
from genesis.validation.purged_cv import PurgedCvResult
from genesis.validation.sensitivity import SensitivityResult
from genesis.validation.wfa import WfaResult

CONFIG_VERSION: str = "genesis-validation-j/1"
"""Versión del esquema de configuración de este Change (Issue J, decisión 10 §3)."""

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
_C2_MIN_PF = 0.8

_P1_MIN_PASS = 0.5
_P2_MAX_ATTEMPTS = 2.0
_P3_MAX_DAILY_BREACH = 0.02
_P4_MIN_SURVIVAL_MONTHS = 6.0
_P5_MIN_PAYOUT = 0.0

_T1_MIN_DSR = 0.95
_T2_MAX_CORRELATION = 0.3


@dataclass(frozen=True, slots=True)
class CandidateValidationBundle:
    """Insumos de un candidato ya producidos por H/I/J, sin recalcular nada (R57).

    Las claves de `wfa_results_by_symbol`/`dsr_pbo_results_by_symbol`/
    `sensitivity_results_by_symbol`/`mc_symbol_results_by_symbol` deben coincidir
    exactamente (R58); `purged_cv_results_by_symbol` es opcional (solo diagnóstico
    informativo del manifest, R106).
    """

    candidate_id: str
    wfa_results_by_symbol: Mapping[str, WfaResult]
    dsr_pbo_results_by_symbol: Mapping[str, DsrPboResult]
    sensitivity_results_by_symbol: Mapping[str, SensitivityResult]
    mc_symbol_results_by_symbol: Mapping[str, McSymbolResult]
    mc_portfolio_result: McPortfolioResult
    prop_sim_result: PropSimResult
    purged_cv_results_by_symbol: Mapping[str, PurgedCvResult] | None = None

    def __post_init__(self) -> None:
        """Valida que los símbolos coincidan exactamente entre los 4 mapas (R58)."""
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


@dataclass(frozen=True, slots=True)
class SymbolGateOutcome:
    """Valor + booleano de pasa/no-pasa por cada gate G1-G9 de un `(candidate_id, symbol)` (R59)."""

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
    all_pass: bool


def _build_symbol_gate_outcome(
    symbol: str,
    wfa_result: WfaResult,
    dsr_pbo_result: DsrPboResult,
    sensitivity_result: SensitivityResult,
    mc_symbol_result: McSymbolResult,
    risk_profile: RiskProfile,
    starting_balance: float,
) -> SymbolGateOutcome:
    """Construye `SymbolGateOutcome` para `symbol` comparando insumos ya producidos (R60/R61)."""
    del symbol  # solo para contexto de mensajes futuros (auditoría), no usado en el cómputo

    trades_oos_total = len(extract_trade_returns(wfa_result.oos_ledger_cosido))
    g1_pass = trades_oos_total >= _G1_MIN_TRADES_OOS

    wfe = wfa_result.wfe
    g2_pass = wfe >= _G2_MIN_WFE

    pf = profit_factor(wfa_result.oos_ledger_cosido)
    g3_pass = pf >= _G3_MIN_PROFIT_FACTOR

    dsr = dsr_pbo_result.dsr
    g4_pass = dsr >= _G4_MIN_DSR

    pbo = dsr_pbo_result.pbo
    g5_pass = pbo < _G5_MAX_PBO

    full_limit_dollar = risk_profile.max_loss_limit_pct / 100.0 * starting_balance
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

    all_pass = (
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
        all_pass=all_pass,
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
    risk_profile: RiskProfile,
    starting_balance: float,
) -> CandidateGateSummary:
    """Construye `CandidateGateSummary` de `bundle`: gates G por símbolo + C1/C2 + P1-P6."""
    symbol_gate_outcomes = {
        symbol: _build_symbol_gate_outcome(
            symbol,
            bundle.wfa_results_by_symbol[symbol],
            bundle.dsr_pbo_results_by_symbol[symbol],
            bundle.sensitivity_results_by_symbol[symbol],
            bundle.mc_symbol_results_by_symbol[symbol],
            risk_profile,
            starting_balance,
        )
        for symbol in bundle.wfa_results_by_symbol
    }

    n_symbols = len(symbol_gate_outcomes)
    n_passing = sum(1 for outcome in symbol_gate_outcomes.values() if outcome.all_pass)
    c1_fraction_passing = n_passing / n_symbols if n_symbols > 0 else 0.0
    c1_pass = c1_fraction_passing >= _C1_MIN_FRACTION

    non_passing_pf = [
        outcome.profit_factor for outcome in symbol_gate_outcomes.values() if not outcome.all_pass
    ]
    c2_min_pf_non_passing = min(non_passing_pf) if non_passing_pf else float("inf")
    c2_pass = c2_min_pf_non_passing >= _C2_MIN_PF

    prop_sim_result = bundle.prop_sim_result
    p1_pass = prop_sim_result.p_pass >= _P1_MIN_PASS
    p2_pass = prop_sim_result.expected_attempts <= _P2_MAX_ATTEMPTS
    p3_pass = prop_sim_result.p_daily_breach_funded_month <= _P3_MAX_DAILY_BREACH
    p4_pass = prop_sim_result.median_funded_survival_months >= _P4_MIN_SURVIVAL_MONTHS
    p5_pass = prop_sim_result.payout_p25_12m >= _P5_MIN_PAYOUT

    p6_violating = _p6_violating_symbols(bundle.wfa_results_by_symbol)
    p6_pass = not p6_violating

    passes_g_c_p = (
        c1_pass and c2_pass and p1_pass and p2_pass and p3_pass and p4_pass and p5_pass and p6_pass
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
    )
