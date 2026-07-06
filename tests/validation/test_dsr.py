"""Tests de `_dsr.py`: PPF/CDF normal (R17-R18, R21-R22) y DSR golden (R14-R16, R20)."""

import math

import pytest

from genesis.validation._dsr import (
    _standard_normal_cdf,
    _standard_normal_ppf,
    deflated_sharpe_ratio,
)

pytestmark = pytest.mark.unit

# NO se importa `scipy` en ningún punto de este módulo de test (R22): el ancla de
# literatura de R18(b) es una constante hardcodeada, no un cálculo en tiempo de test.

_ROUND_TRIP_PROBABILITIES = (
    0.55,
    0.6,
    0.65,
    0.7,
    0.75,
    0.8,
    0.85,
    0.9,
    0.95,
    0.975,
    0.99,
    0.999,
    0.9999,
)


@pytest.mark.parametrize("p", _ROUND_TRIP_PROBABILITIES)
def test_ppf_round_trip(p: float) -> None:
    """R18(a): `Φ(Φ⁻¹(p)) ≈ p` dentro de `1e-9`."""
    assert abs(_standard_normal_cdf(_standard_normal_ppf(p)) - p) < 1e-9


def test_ppf_literature_anchor() -> None:
    """R18(b): ancla de literatura, constante hardcodeada (sin `scipy` en tiempo de test)."""
    assert abs(_standard_normal_ppf(0.975) - 1.9599639845400545) < 1e-6


def test_ppf_fuera_de_dominio_lanza_value_error() -> None:
    with pytest.raises(ValueError):
        _standard_normal_ppf(0.0)
    with pytest.raises(ValueError):
        _standard_normal_ppf(1.0)


def test_deflated_sharpe_menos_de_dos_muestras_retorna_cero() -> None:
    assert deflated_sharpe_ratio([1.0], 9) == 0.0
    assert deflated_sharpe_ratio([], 9) == 0.0


def test_deflated_sharpe_desviacion_cero_retorna_cero() -> None:
    assert deflated_sharpe_ratio([2.0, 2.0, 2.0], 9) == 0.0


def test_deflated_sharpe_golden() -> None:
    """R20: secuencia calculada a mano, paso a paso, con un oráculo PPF independiente.

    El oráculo de referencia de este test invierte `Φ` por bisección directa sobre
    `math.erf` (200 iteraciones, precisión << 1e-9), **sin** usar el algoritmo de
    Acklam+Halley de `_dsr.py` ni `scipy` (R20, R22): acota de forma independiente el
    componente de la fórmula (R16) más propenso a error de transcripción (Rg-4).

    Cálculo a mano (`returns`, `n_trials=9`):
      n = 10; mean = 2.6; std(ddof=1) = 7.15231120376872
      SR_hat = mean/std = 0.3635188578805127
      z = (x - mean)/std (estandarizados)
      γ3 = mean(z**3)   = 0.028730695804951967
      γ4 = mean(z**4)   = 0.9875823387814469   (kurtosis no excedente)
      denom = 1 - γ3·SR_hat + ((γ4-1)/4)·SR_hat**2 = 0.9891456143340934
      Var_SR = denom/(n-1) = 0.10990506825934371
      Φ⁻¹(1 - 1/9)       = 1.2206403488473487  (bisección directa sobre erf)
      Φ⁻¹(1 - 1/(9·e))   = 1.740615567999885   (bisección directa sobre erf)
      γ_EM = 0.5772156649015329
      SR0 = sqrt(Var_SR)·((1-γ_EM)·Φ⁻¹(1-1/9) + γ_EM·Φ⁻¹(1-1/(9e))) = 0.5041673716671936
      DSR = Φ((SR_hat - SR0)·sqrt(n-1)/sqrt(denom)) = 0.3356901697327985
    """
    returns = [10.0, -5.0, 8.0, -3.0, 12.0, -6.0, 7.0, -2.0, 9.0, -4.0]
    expected_dsr = 0.3356901697327985
    assert abs(deflated_sharpe_ratio(returns, n_trials=9) - expected_dsr) < 1e-9


def test_deflated_sharpe_n_trials_no_hardcodeado() -> None:
    """R19: `n_trials` distinto produce resultados distintos (no se ignora el argumento)."""
    returns = [10.0, -5.0, 8.0, -3.0, 12.0, -6.0, 7.0, -2.0, 9.0, -4.0]
    dsr_9 = deflated_sharpe_ratio(returns, n_trials=9)
    dsr_27 = deflated_sharpe_ratio(returns, n_trials=27)
    assert dsr_9 != dsr_27


def test_deflated_sharpe_es_finito() -> None:
    returns = [10.0, -5.0, 8.0, -3.0, 12.0, -6.0, 7.0, -2.0, 9.0, -4.0]
    result = deflated_sharpe_ratio(returns, n_trials=9)
    assert math.isfinite(result)
