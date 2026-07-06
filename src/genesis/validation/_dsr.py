"""Deflated Sharpe Ratio interno (Bailey & López de Prado, 2014), módulo privado (R14-R22).

Usado **exclusivamente** como criterio de selección IS dentro de `wfa.py`; no se
exporta en `src/genesis/validation/__init__.py` (R14) — no es la implementación
normativa del gate G4/T1 (Issue I, `dsr_pbo.py`). Sin `scipy`/`statsmodels`/
`matplotlib`/`quantstats` (R21): la inversa de la CDF normal (`_standard_normal_ppf`)
se implementa con el algoritmo racional de Acklam (tres tramos) más un paso de
refinamiento de Halley sobre `math.erf`.
"""

import math
from collections.abc import Sequence

import numpy as np

_MIN_RETURNS_SAMPLES = 2
_EULER_MASCHERONI = 0.5772156649015329
"""Constante de Euler-Mascheroni (γ), usada en el término de corrección del DSR (R16)."""

# Coeficientes racionales de Acklam (aproximación de `_standard_normal_ppf`, R18).
_ACKLAM_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_ACKLAM_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_ACKLAM_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_ACKLAM_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_ACKLAM_P_LOW = 0.02425
_ACKLAM_P_HIGH = 1.0 - _ACKLAM_P_LOW


def _standard_normal_cdf(x: float) -> float:
    """CDF de la normal estándar (R17), `stdlib` puro: `0.5·(1 + erf(x/√2))`."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _acklam_rational_approximation(p: float) -> float:
    """Aproximación racional en tres tramos de Acklam para `_standard_normal_ppf` (R18)."""
    a, b, c, d = _ACKLAM_A, _ACKLAM_B, _ACKLAM_C, _ACKLAM_D
    if p < _ACKLAM_P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        numerator = ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        denominator = (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        return numerator / denominator
    if p <= _ACKLAM_P_HIGH:
        q = p - 0.5
        r = q * q
        numerator = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        denominator = ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
        return numerator / denominator
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    numerator = ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
    denominator = (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    return -numerator / denominator


def _standard_normal_ppf(p: float) -> float:
    """Inversa de `_standard_normal_cdf` (R18): Acklam + 1 paso de refinamiento de Halley.

    Dominio válido `0 < p < 1`; fuera de rango lanza `ValueError` con contexto (no
    debería ocurrir con los `1 - 1/n_trials` de `n_trials ∈ {9, 27}` de `wfa.py`).
    """
    if not (0.0 < p < 1.0):
        message = f"_standard_normal_ppf(p={p!r}) fuera del dominio válido (0, 1)."
        raise ValueError(message)

    x = _acklam_rational_approximation(p)

    # Refinamiento de Halley sobre `_standard_normal_cdf` (1 paso, converge cúbicamente).
    e = _standard_normal_cdf(x) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    x = x - u / (1.0 + x * u / 2.0)
    return x


def deflated_sharpe_ratio(returns: Sequence[float], n_trials: int) -> float:
    """Deflated Sharpe Ratio (Bailey & López de Prado, 2014) sobre `returns` (R14-R16).

    `n_trials` se recibe siempre como argumento explícito del llamador (`wfa.py` lo
    invoca con `n_trials=9`, R19) — esta función no hardcodea ningún valor de
    trials. Retorna `0.0` (sin lanzar excepción) si `len(returns) < 2`,
    `std(returns, ddof=1) == 0`, o si el denominador de la varianza del estimador de
    Sharpe es no positivo (muestra degenerada, guarda numérica de Rg-2).
    """
    n = len(returns)
    if n < _MIN_RETURNS_SAMPLES:
        return 0.0

    values = np.asarray(returns, dtype=float)
    std = float(values.std(ddof=1))
    if std == 0.0:
        return 0.0
    sr_hat = float(values.mean() / std)

    standardized = (values - values.mean()) / std
    gamma3 = float(np.mean(standardized**3))
    gamma4 = float(np.mean(standardized**4))  # kurtosis no excedente (R16)

    denom = 1.0 - gamma3 * sr_hat + ((gamma4 - 1.0) / 4.0) * sr_hat**2
    if denom <= 0.0:
        return 0.0

    var_sr = denom / (n - 1)
    euler = _EULER_MASCHERONI
    sr0 = math.sqrt(var_sr) * (
        (1.0 - euler) * _standard_normal_ppf(1.0 - 1.0 / n_trials)
        + euler * _standard_normal_ppf(1.0 - 1.0 / (n_trials * math.e))
    )
    return _standard_normal_cdf((sr_hat - sr0) * math.sqrt(n - 1) / math.sqrt(denom))
