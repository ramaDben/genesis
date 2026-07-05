"""Métricas clásicas y prop, puras sobre un `Ledger` ya poblado (R48–R50).

Ninguna función muta el `Ledger` recibido (R50); todas se calculan por post-proceso
del registro append-only, desacopladas del `Simulator` en ejecución. Solo `numpy` +
stdlib (R41/R58): sin `scipy`/`statsmodels`/`matplotlib`/`quantstats`.

Modelo de PnL por trade (decisión de implementación, sin R-número que fije la fórmula
exacta): el PnL de cada `FillRecord` de salida es el delta de `equity_after` respecto
al `FillRecord` inmediatamente anterior en el ledger (los `FillRecord` de entrada solo
descuentan costos, nunca acreditan PnL de mercado).
"""

import numpy as np

from genesis.backtest.ledger import BreachEvent, BreachKind, FillRecord, Ledger, RejectionRecord
from genesis.data.profile import FirmProfile

_MIN_SHARPE_SAMPLES = 2


def _running_equity_deltas(ledger: Ledger) -> list[tuple[FillRecord, float]]:
    """Delta de `equity_after` de cada `FillRecord` respecto al `FillRecord` anterior.

    El primer `FillRecord` del ledger no tiene referencia previa; su delta es `0.0`
    (no participa de PF/win-rate, que solo miran salidas, R50: no muta `ledger`).
    """
    deltas: list[tuple[FillRecord, float]] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            delta = 0.0 if previous_equity is None else payload.equity_after - previous_equity
            deltas.append((payload, delta))
            previous_equity = payload.equity_after
    return deltas


def _exit_deltas(ledger: Ledger) -> list[float]:
    return [delta for fill, delta in _running_equity_deltas(ledger) if fill.is_exit]


def profit_factor(ledger: Ledger) -> float:
    """Ganancia bruta / pérdida bruta de los `FillRecord` de salida (R48)."""
    deltas = _exit_deltas(ledger)
    gross_profit = sum(delta for delta in deltas if delta > 0)
    gross_loss = -sum(delta for delta in deltas if delta < 0)
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def sharpe_pointwise(ledger: Ledger) -> float:
    """Media / desviación estándar de los deltas de salida (R48); `0.0` si hay <2 muestras."""
    deltas = _exit_deltas(ledger)
    if len(deltas) < _MIN_SHARPE_SAMPLES:
        return 0.0
    values = np.array(deltas, dtype=float)
    std = float(values.std(ddof=1))
    if std == 0.0:
        return 0.0
    return float(values.mean() / std)


def max_drawdown(ledger: Ledger) -> float:
    """Máxima caída desde el pico de la curva de `equity_after` (R48)."""
    equity_curve = [fill.equity_after for fill, _ in _running_equity_deltas(ledger)]
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def win_rate(ledger: Ledger) -> float:
    """Fracción de `FillRecord` de salida con delta de equity positivo (R48)."""
    deltas = _exit_deltas(ledger)
    if not deltas:
        return 0.0
    wins = sum(1 for delta in deltas if delta > 0)
    return wins / len(deltas)


def worst_daily_floating_excursion(ledger: Ledger) -> float:
    """Peor `magnitude` entre los `BreachEvent(DAILY)` registrados (R49); `0.0` si no hay."""
    magnitudes = [
        payload.magnitude
        for entry in ledger.entries
        if isinstance(payload := entry.payload, BreachEvent) and payload.kind is BreachKind.DAILY
    ]
    return max(magnitudes, default=0.0)


def min_distance_to_daily_limit(ledger: Ledger, firm_profile: FirmProfile) -> float:
    """Distancia mínima observada al límite de pérdida diaria (R49).

    `threshold - magnitude` sobre los `BreachEvent(DAILY)` del ledger (negativo si el
    límite fue superado). Sin ningún breach DAILY, no hubo cercanía observada y se
    retorna `firm_profile.daily_loss_limit_pct` como distancia de referencia.
    """
    distances = [
        payload.threshold - payload.magnitude
        for entry in ledger.entries
        if isinstance(payload := entry.payload, BreachEvent) and payload.kind is BreachKind.DAILY
    ]
    if not distances:
        return firm_profile.daily_loss_limit_pct
    return min(distances)


def max_concurrent_exposure(ledger: Ledger) -> int:
    """Número máximo de posiciones simultáneamente abiertas observado en el ledger (R49)."""
    open_count = 0
    max_open = 0
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if payload.is_exit:
                open_count = max(open_count - 1, 0)
            else:
                open_count += 1
                max_open = max(max_open, open_count)
    return max_open


def rejection_rate_by_reason(ledger: Ledger) -> dict[str, float]:
    """Tasa de rechazo por motivo, agregando `RejectionReason` (C) y `BreachKind` (G) (R49).

    Denominador: total de `RejectionRecord` + `BreachEvent` del ledger (eventos de
    riesgo observados); `{}` si no hay ninguno.
    """
    counts: dict[str, int] = {}
    total = 0
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, RejectionRecord):
            reason = payload.verdict.rejection_reason
            key = reason.value if reason is not None else "unknown"
            counts[key] = counts.get(key, 0) + 1
            total += 1
        elif isinstance(payload, BreachEvent):
            key = payload.kind.value
            counts[key] = counts.get(key, 0) + 1
            total += 1
    if total == 0:
        return {}
    return {key: count / total for key, count in counts.items()}
