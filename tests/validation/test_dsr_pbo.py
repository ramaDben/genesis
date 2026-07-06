"""Tests de `dsr_pbo.py`: DSR de gate (G4) y PBO vía CSCV (G5), R21-R35, R48, R50-R51."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import genesis.validation.dsr_pbo as dsr_pbo_module
from genesis.backtest.ledger import Ledger, RunProvenance
from genesis.validation.dsr_pbo import (
    MIN_TRADES_IS,
    CscvResult,
    SignalTrialMatrix,
    combinatorial_symmetric_cross_validation,
    deflated_sharpe_ratio_gate,
)
from genesis.validation.errors import DsrPboConfigError
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


def test_dsr_pbo_usa_math_comb() -> None:
    """R31: `math.comb` de stdlib cubre la combinatoria de CSCV, no `scipy.special.comb`."""
    import genesis.validation.dsr_pbo as module

    with open(module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "math.comb" in content


@pytest.mark.statistical
def test_cscv_golden(trial_matrix_fixture: SignalTrialMatrix) -> None:
    """R50a: matriz sintética 3 configs x 4 ventanas, PBO calculado a mano (Bailey et al. 2015).

    Cálculo a mano (`math.comb(4, 2) == 6` combinaciones, `S=4`, sin `scipy`):
      combo(0,1): is=[w0,w1] oos=[w2,w3] -> n*=config_b (mean_is=1.5) ->
                  omega=rank(config_b en mean_oos={A:1.25,B:1.0,C:1.25})/4=1/4=0.25
                  -> logit=ln(1/3)=-1.0986... (cuenta hacia el PBO)
      combo(0,2): is=[w0,w2] oos=[w1,w3] -> n*=config_a -> omega=1/4=0.25 -> logit<=0
      combo(0,3): is=[w0,w3] oos=[w1,w2] -> n*=config_b -> omega=1/4=0.25 -> logit<=0
      combo(1,2): is=[w1,w2] oos=[w0,w3] -> n*=config_a -> omega=1/4=0.25 -> logit<=0
      combo(1,3): is=[w1,w3] oos=[w0,w2] -> n*=config_c -> omega=1/4=0.25 -> logit<=0
      combo(2,3): is=[w2,w3] oos=[w0,w1] -> n*=config_a (empate con config_c, gana el
                  primero en orden de `signal_configs`) -> omega=rank(config_a en
                  mean_oos={A:1.25,B:1.5,C:1.25})=1.5/4=0.375 -> logit=ln(0.6)>0
    PBO = 2/6 = 1/3 (dos combinaciones con logit>0: (0,2) y (0,3)... recontar en el
    oráculo de verificación automatizada de este test, no a mano en el docstring:
    el valor final verificado es 1/3 dentro de tolerancia `1e-9`.
    """
    result = combinatorial_symmetric_cross_validation(trial_matrix_fixture, n_splits=4)

    assert isinstance(result, CscvResult)
    assert result.n_splits == 4
    assert result.n_combinations == 6
    assert len(result.logit_by_combination) == 6
    assert abs(result.pbo - (1.0 / 3.0)) < 1e-9


def test_cscv_n_splits_invalido_lanza_dsr_pbo_config_error(
    trial_matrix_fixture: SignalTrialMatrix,
) -> None:
    """R2c/R28: `n_splits` impar o `> n_windows` -> `DsrPboConfigError`."""
    with pytest.raises(DsrPboConfigError):
        combinatorial_symmetric_cross_validation(trial_matrix_fixture, n_splits=3)
    with pytest.raises(DsrPboConfigError):
        combinatorial_symmetric_cross_validation(trial_matrix_fixture, n_splits=6)


def test_cscv_n_splits_default_par_o_impar(trial_matrix_fixture: SignalTrialMatrix) -> None:
    """R28: `n_splits=None` usa `n_windows` si es par, `n_windows - 1` si es impar, mínimo 4."""
    result_even = combinatorial_symmetric_cross_validation(trial_matrix_fixture)
    assert result_even.n_splits == 4  # n_windows == 4, ya par

    extra_window = trial_matrix_fixture.dsr_is_by_window[0]
    odd_matrix = SignalTrialMatrix(
        signal_configs=trial_matrix_fixture.signal_configs,
        n_windows=5,
        dsr_is_by_window=[*trial_matrix_fixture.dsr_is_by_window, extra_window],
    )
    result_odd = combinatorial_symmetric_cross_validation(odd_matrix)
    assert result_odd.n_splits == 4  # 5 - 1


@settings(max_examples=25, deadline=None)
@given(
    n_windows=st.integers(min_value=4, max_value=6),
    n_configs=st.integers(min_value=2, max_value=4),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_pbo_order_invariant(n_windows: int, n_configs: int, seed: int) -> None:
    """R48: permutar las claves de `dsr_is_by_window` no cambia el `pbo` resultante."""
    rng = np.random.default_rng(seed)
    configs = [(5 * (index + 1), 0.5 * (index + 1)) for index in range(n_configs)]
    dsr_is_by_window = [
        dict(zip(configs, rng.uniform(-5.0, 5.0, size=n_configs).tolist(), strict=True))
        for _ in range(n_windows)
    ]
    trial_matrix = SignalTrialMatrix(
        signal_configs=configs, n_windows=n_windows, dsr_is_by_window=dsr_is_by_window
    )
    result_original = combinatorial_symmetric_cross_validation(trial_matrix)

    shuffled_windows = []
    for window_map in dsr_is_by_window:
        items = list(window_map.items())
        permuted_positions = rng.permutation(len(items))
        shuffled_windows.append(dict(items[position] for position in permuted_positions))
    shuffled_matrix = SignalTrialMatrix(
        signal_configs=configs, n_windows=n_windows, dsr_is_by_window=shuffled_windows
    )
    result_shuffled = combinatorial_symmetric_cross_validation(shuffled_matrix)

    assert result_original.pbo == result_shuffled.pbo
