"""DSR normativo de gate (G4) y PBO vía CSCV (G5) del candidato aislado, Issue I.

Reutiliza `_dsr.deflated_sharpe_ratio` (H) tal cual para el DSR de gate, sin
duplicar la fórmula; el PBO (Bailey, Borwein, López de Prado & Zhu, 2015) es
código propio de este módulo, sin equivalente en `_dsr.py`. Calcula DSR/PBO
**por candidato aislado** (insumo de los gates G4/G5); nunca aplica ninguna
deflación adicional (esa responsabilidad, distinta y posterior, es exclusiva
de `verdict.py`, Issue J).
"""

from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation._returns import extract_trade_returns
from genesis.validation.wfa import WfaResult

CONFIG_VERSION: str = "genesis-validation-i/1"
"""Versión del esquema de configuración de este Change (Issue I, decisión 10 §3)."""

MIN_TRADES_IS: int = 10
"""Umbral mínimo de trades IS agregados por configuración de señal de una ventana
(R2b/R34): por debajo de este umbral esa configuración recibe DSR-IS `-inf` en
`SignalTrialMatrix.dsr_is_by_window`. Constante propia de este módulo — NO
reimportada de `wfa.py` (mismo valor que H por diseño, declarada localmente)."""


def deflated_sharpe_ratio_gate(wfa_result: WfaResult) -> float:
    """DSR normativo del gate G4 sobre el `oos_ledger_cosido` de `wfa_result` (R21-R23).

    `n_trials` proviene **exclusivamente** de `wfa_result.n_trials_signal_total`
    (= `n_windows * 9`, señal, decisión 1 §3 del spec) — nunca un literal
    hardcodeado, de modo que revertir al conteo de ejecución
    (`n_trials_execution_total`, 27 por ventana) sea un cambio de una línea
    (Rg-1). NO aplica ninguna deflación adicional posterior: esa
    responsabilidad (T1) es exclusiva de `verdict.py` (Issue J).
    """
    returns = [trade.pnl_delta for trade in extract_trade_returns(wfa_result.oos_ledger_cosido)]
    return deflated_sharpe_ratio(returns, n_trials=wfa_result.n_trials_signal_total)
