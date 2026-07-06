"""Tests de `dsr_pbo.py`: DSR de gate (G4) y PBO vía CSCV (G5), R21-R35, R48, R50-R51."""

import pytest

import genesis.validation.dsr_pbo as dsr_pbo_module
from genesis.backtest.ledger import Ledger, RunProvenance
from genesis.validation.dsr_pbo import MIN_TRADES_IS, deflated_sharpe_ratio_gate
from genesis.validation.wfa import WfaResult
from tests.validation.fixtures.ledgers import build_ledger

_PROVENANCE = RunProvenance(
    candidate_id="B",
    config_version="genesis-backtest/1",
    dataset_hash="test-dataset-hash",
    firm_profile_hash="test-firm-profile-hash",
    risk_profile_hash="test-risk-profile-hash",
)


def _build_synthetic_wfa_result(*, n_windows: int, oos_ledger: Ledger) -> WfaResult:
    """`WfaResult` sintético mínimo (sin ventanas reales) para el golden de `n_trials` (R51)."""
    return WfaResult(
        candidate_id="B",
        symbol="US500",
        config_version="genesis-validation/1",
        windows=(),
        oos_ledger_cosido=oos_ledger,
        wfe=0.0,
        n_windows=n_windows,
        n_trials_signal_total=n_windows * 9,
        n_trials_execution_total=n_windows * 27,
        seed=0,
    )


def test_min_trades_is_constante_local() -> None:
    """R2b/R34: `MIN_TRADES_IS` es propia de `dsr_pbo.py`, no reimportada de `wfa.py`."""
    assert MIN_TRADES_IS == 10


@pytest.mark.unit
def test_gate_n_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    """R51: `deflated_sharpe_ratio_gate` invoca `_dsr.deflated_sharpe_ratio` con `n_windows*9`."""
    ledger = build_ledger([10.0, -5.0, 8.0, -3.0, 12.0])
    wfa_result = _build_synthetic_wfa_result(n_windows=3, oos_ledger=ledger)

    captured: dict[str, object] = {}

    def _fake_dsr(returns: list[float], n_trials: int) -> float:
        captured["returns"] = returns
        captured["n_trials"] = n_trials
        return 0.5

    monkeypatch.setattr(dsr_pbo_module, "deflated_sharpe_ratio", _fake_dsr)

    result = deflated_sharpe_ratio_gate(wfa_result)

    assert result == 0.5
    assert captured["n_trials"] == 27  # n_windows(3) * 9, NO n_windows * 27 == 81
    assert captured["n_trials"] == wfa_result.n_trials_signal_total
    assert captured["returns"] == [10.0, -5.0, 8.0, -3.0, 12.0]


def test_deflated_sharpe_ratio_gate_no_reexpresa_torneo() -> None:
    """R22: sin ninguna referencia a deflación de torneo."""
    import genesis.validation.dsr_pbo as module

    with open(module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "n_candidates" not in content
    assert "tournament" not in content
    assert "torneo" not in content


def test_dsr_pbo_importa_deflated_sharpe_ratio_de_dsr() -> None:
    """R21: reutiliza `_dsr.deflated_sharpe_ratio` directamente, sin reimplementar la fórmula."""
    import genesis.validation.dsr_pbo as module

    with open(module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "from genesis.validation._dsr import deflated_sharpe_ratio" in content
    assert "n_trials_signal_total" in content


def test_dsr_pbo_no_importa_scipy() -> None:
    """R31/R58: `dsr_pbo.py` no importa `scipy` en ningún punto."""
    import genesis.validation.dsr_pbo as module

    with open(module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "import scipy" not in content
    assert "from scipy" not in content
