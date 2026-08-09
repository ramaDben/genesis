"""Métricas clásicas y prop, puras sobre un `Ledger` ya poblado (R48–R50).

Ninguna función muta el `Ledger` recibido (R50); todas se calculan por post-proceso
del registro append-only, desacopladas del `Simulator` en ejecución. Solo `numpy` +
stdlib (R41/R58): sin `scipy`/`statsmodels`/`matplotlib`/`quantstats`.

Modelo de PnL por trade (decisión de implementación, sin R-número que fije la fórmula
exacta): el PnL de cada `FillRecord` de salida es el delta de `equity_after` respecto
al `FillRecord` inmediatamente anterior en el ledger (los `FillRecord` de entrada solo
descuentan costos, nunca acreditan PnL de mercado).
"""

from collections.abc import Mapping
from dataclasses import dataclass

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


def _profit_factor_from(deltas: list[float]) -> float:
    """Fórmula de PF, aislada de cómo se obtuvieron los deltas."""
    gross_profit = sum(delta for delta in deltas if delta > 0)
    gross_loss = -sum(delta for delta in deltas if delta < 0)
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _sharpe_pointwise_from(deltas: list[float]) -> float:
    """Fórmula del Sharpe puntual, aislada de cómo se obtuvieron los deltas."""
    if len(deltas) < _MIN_SHARPE_SAMPLES:
        return 0.0
    values = np.array(deltas, dtype=float)
    std = float(values.std(ddof=1))
    if std == 0.0:
        return 0.0
    return float(values.mean() / std)


def _max_drawdown_from(equity_curve: list[float]) -> float:
    """Fórmula del máximo drawdown, aislada de cómo se obtuvo la curva."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _win_rate_from(deltas: list[float]) -> float:
    """Fórmula del win-rate, aislada de cómo se obtuvieron los deltas."""
    if not deltas:
        return 0.0
    wins = sum(1 for delta in deltas if delta > 0)
    return wins / len(deltas)


def _daily_breaches(ledger: Ledger) -> list[BreachEvent]:
    """`BreachEvent` de tipo `DAILY` del ledger, en orden de aparición."""
    return [
        payload
        for entry in ledger.entries
        if isinstance(payload := entry.payload, BreachEvent) and payload.kind is BreachKind.DAILY
    ]


@dataclass(frozen=True, slots=True)
class LedgerMetricsSummary:
    """Las cuatro métricas clásicas de un `Ledger`, obtenidas de un solo recorrido."""

    profit_factor: float
    sharpe_pointwise: float
    max_drawdown: float
    win_rate: float


def ledger_metrics_summary(ledger: Ledger) -> LedgerMetricsSummary:
    """PF, Sharpe, MaxDD y win-rate con **una** pasada sobre `ledger.entries`.

    Las cuatro funciones públicas siguen existiendo con su firma intacta y cada una hace
    su propio recorrido: son correctas y baratas cuando se necesita una sola métrica, que
    es el caso de todos los llamadores actuales. Esta función es para quien necesita
    varias a la vez, y evita los cuatro recorridos que eso costaba.

    Los valores son idénticos a los de las funciones individuales por construcción:
    ambas rutas aplican las mismas fórmulas (`_profit_factor_from` y compañía) sobre las
    mismas secuencias en el mismo orden, así que no hay reordenamiento de acumulaciones
    de float que pueda mover el último bit.
    """
    running = _running_equity_deltas(ledger)
    exit_deltas = [delta for fill, delta in running if fill.is_exit]
    equity_curve = [fill.equity_after for fill, _ in running]
    return LedgerMetricsSummary(
        profit_factor=_profit_factor_from(exit_deltas),
        sharpe_pointwise=_sharpe_pointwise_from(exit_deltas),
        max_drawdown=_max_drawdown_from(equity_curve),
        win_rate=_win_rate_from(exit_deltas),
    )


def profit_factor(ledger: Ledger) -> float:
    """Ganancia bruta / pérdida bruta de los `FillRecord` de salida (R48)."""
    return _profit_factor_from(_exit_deltas(ledger))


def sharpe_pointwise(ledger: Ledger) -> float:
    """Media / desviación estándar de los deltas de salida (R48); `0.0` si hay <2 muestras."""
    return _sharpe_pointwise_from(_exit_deltas(ledger))


def max_drawdown(ledger: Ledger) -> float:
    """Máxima caída desde el pico de la curva de `equity_after` (R48)."""
    return _max_drawdown_from([fill.equity_after for fill, _ in _running_equity_deltas(ledger)])


def win_rate(ledger: Ledger) -> float:
    """Fracción de `FillRecord` de salida con delta de equity positivo (R48)."""
    return _win_rate_from(_exit_deltas(ledger))


def worst_daily_floating_excursion(ledger: Ledger) -> float:
    """Peor `magnitude` entre los `BreachEvent(DAILY)` registrados (R49); `0.0` si no hay."""
    return max((breach.magnitude for breach in _daily_breaches(ledger)), default=0.0)


def min_distance_to_daily_limit(ledger: Ledger, firm_profile: FirmProfile) -> float:
    """Distancia mínima observada al límite de pérdida diaria (R49).

    `threshold - magnitude` sobre los `BreachEvent(DAILY)` del ledger (negativo si el
    límite fue superado). Sin ningún breach DAILY, no hubo cercanía observada y se
    retorna `firm_profile.daily_loss_limit_pct` como distancia de referencia.
    """
    distances = [breach.threshold - breach.magnitude for breach in _daily_breaches(ledger)]
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


@dataclass(frozen=True, slots=True)
class IntentAuthorizationCounts:
    """Conteo absoluto de intents de un `Ledger`, autorizados vs. rechazados por motivo (R1).

    A diferencia de `rejection_rate_by_reason` (tasa normalizada sobre eventos de
    riesgo, `RejectionRecord + BreachEvent`), este es un conteo absoluto sobre
    intents propuestos por el candidato (`RejectionRecord + FillRecord` de
    entrada); `BreachEvent` no participa, porque no es un intent propuesto.
    """

    intents_authorized: int
    """`count(FillRecord con is_exit=False)`: intents que el embudo autorizó."""

    intents_total: int
    """`intents_authorized + count(RejectionRecord)`: todos los intents propuestos."""

    rejections_by_reason: Mapping[str, int]
    """Conteo de `RejectionRecord` por `RejectionReason.value`; `"unknown"` si `None`."""


def intent_authorization_counts(ledger: Ledger) -> IntentAuthorizationCounts:
    """Cuenta intents autorizados y rechazados por motivo de un `(candidate_id, symbol)` (R1).

    Precondición: `ledger` corresponde a un único `(candidate_id, symbol)` (p. ej.
    `wfa_result.oos_ledger_cosido`); esta función **no** filtra por esos campos, igual
    que `extract_trade_returns`/`profit_factor` sobre el mismo ledger (Q2 de
    `design.md`, Change #51). Un solo recorrido O(n), sin mutar `ledger` (R50).
    `BreachEvent` no cuenta como intent. `"unknown"` para `RejectionRecord` con
    `verdict.rejection_reason is None` (estado imposible por invariante de
    `InspectorVerdict`; se contabiliza en vez de fallar, el fail-fast de ese
    invariante es responsabilidad del Inspector).
    """
    intents_authorized = 0
    rejections_by_reason: dict[str, int] = {}
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if not payload.is_exit:
                intents_authorized += 1
        elif isinstance(payload, RejectionRecord):
            reason = payload.verdict.rejection_reason
            key = reason.value if reason is not None else "unknown"
            rejections_by_reason[key] = rejections_by_reason.get(key, 0) + 1
    intents_total = intents_authorized + sum(rejections_by_reason.values())
    return IntentAuthorizationCounts(
        intents_authorized=intents_authorized,
        intents_total=intents_total,
        rejections_by_reason=rejections_by_reason,
    )
