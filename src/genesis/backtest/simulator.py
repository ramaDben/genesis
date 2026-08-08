"""`Simulator` — orquestador event-driven de la capa 3 (R20–R36, ADR-G3/G9).

Único módulo "tope" de `genesis.backtest`: consume todos los demás módulos de esta
capa más los puertos ya cerrados de `genesis.strategy` (capa 2) y `genesis.data`
(capa 1), sin modificar ninguno de los dos árboles (R57). `RiskLevelsProvider` es un
puerto adicional requisito duro (ADR-G3): el `Simulator` exige que el candidato lo
implemente al construirse, en vez de un `RejectionReason` nuevo o un rechazo
silencioso (R21).

Modelo de costos monetario (decisión de implementación, sin R-número específico que
fije la fórmula exacta de P&L): el P&L en puntos de precio se convierte a dinero vía
`figure.tick_value`; comisión y swap se cobran como cargos explícitos (`cost_applied`)
separados del precio de ejecución, que permanece geométricamente puro (bar.open/nivel
SL-TP/precio de tick) para no contaminar la tabla golden de fills (R32–R36).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, cast, runtime_checkable

import pandas as pd

from genesis.backtest.clock import SimulationClock
from genesis.backtest.costs import CostsConfig, commission_for, slippage_for, spread_for, swap_for
from genesis.backtest.errors import BacktestConfigError, SessionBoundaryError
from genesis.backtest.ledger import (
    CONFIG_VERSION,
    BreachEvent,
    BreachKind,
    FillRecord,
    Ledger,
    RejectionRecord,
    RunProvenance,
)
from genesis.backtest.risk_profile import MaxLossLimitKind, RiskProfile, risk_profile_hash
from genesis.backtest.ticks import (
    TickCache,
    TickRow,
    has_ticks_in_bar_window,
    ticks_in_bar_window,
)
from genesis.data.calendar import EconomicEvent, news_windows
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, firm_profile_hash
from genesis.data.sessions import session_window
from genesis.data.store import AnnotatedBar, iter_bars
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import Direction, EntryIntent, StrategyCandidate
from genesis.strategy.inspector import InspectorFunnelConfig, inspect

_FRIDAY_WEEKDAY = 4
"""`date.weekday()` para viernes (0=lunes); usado por el breach WEEKEND (R28)."""

_SESSION_PROBE_DATE = date(2024, 1, 1)
"""Fecha arbitraria usada solo para validar `symbol in SESSIONS` al construir (R3c)."""


@runtime_checkable
class RiskLevelsProvider(Protocol):
    """Puerto adicional opcional que expone niveles de riesgo de una intención (R20, ADR-G3).

    `EntryIntent` de la capa 2 es intencionalmente mínimo (4 campos) y no porta
    geometría de niveles; los candidatos que necesiten fills SL/TP simulados
    implementan este puerto además de `StrategyCandidate`.
    """

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float]:
        """Retorna `(stop_loss, take_profit)` para `intent`, recién emitido por `on_bar`."""
        ...


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """Identidad inmutable de una posición abierta durante la simulación."""

    candidate_id: str
    symbol: str
    direction: Direction
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    sizing_hint: float


@dataclass
class AccountState:
    """Estado mutable de ejecución de la cuenta simulada (no es un value object, RI-G3)."""

    balance: float
    open_positions: list[OpenPosition]
    account_exhausted: bool = False


@dataclass(frozen=True, slots=True)
class ResolvedFill:
    """Resultado puro del motor de fills: precio geométrico y momento de ejecución."""

    price: float
    timestamp_utc: datetime


def _is_adverse_gap(direction: Direction, open_price: float, stop_loss: float) -> bool:
    if direction is Direction.LONG:
        return open_price <= stop_loss
    return open_price >= stop_loss


def _is_favorable_gap(direction: Direction, open_price: float, take_profit: float) -> bool:
    if direction is Direction.LONG:
        return open_price >= take_profit
    return open_price <= take_profit


def _touches_stop_loss(direction: Direction, price: float, stop_loss: float) -> bool:
    if direction is Direction.LONG:
        return price <= stop_loss
    return price >= stop_loss


def _touches_take_profit(direction: Direction, price: float, take_profit: float) -> bool:
    if direction is Direction.LONG:
        return price >= take_profit
    return price <= take_profit


def _resolve_fill_from_ticks(
    position: OpenPosition, bar: AnnotatedBar, day_ticks: Sequence[TickRow]
) -> ResolvedFill | None:
    """Rama con cobertura suficiente (R35): primer tick cronológico que toca SL o TP gana."""
    for tick in ticks_in_bar_window(bar, day_ticks):
        if _touches_stop_loss(position.direction, tick.last, position.stop_loss):
            return ResolvedFill(price=position.stop_loss, timestamp_utc=tick.timestamp_utc)
        if _touches_take_profit(position.direction, tick.last, position.take_profit):
            return ResolvedFill(price=position.take_profit, timestamp_utc=tick.timestamp_utc)
    return None


def _resolve_fill_fallback(position: OpenPosition, bar: AnnotatedBar) -> ResolvedFill | None:
    """Rama fallback sin cobertura de ticks (R32–R34), sobre `[bar.low, bar.high]`/`bar.open`."""
    direction = position.direction
    if _is_adverse_gap(direction, bar.open, position.stop_loss):
        return ResolvedFill(price=bar.open, timestamp_utc=bar.timestamp_utc)
    if _is_favorable_gap(direction, bar.open, position.take_profit):
        return ResolvedFill(price=position.take_profit, timestamp_utc=bar.timestamp_utc)

    sl_in_range = bar.low <= position.stop_loss <= bar.high
    tp_in_range = bar.low <= position.take_profit <= bar.high
    if sl_in_range:
        return ResolvedFill(price=position.stop_loss, timestamp_utc=bar.timestamp_utc)
    if tp_in_range:
        return ResolvedFill(price=position.take_profit, timestamp_utc=bar.timestamp_utc)
    return None


def _resolve_fill(
    position: OpenPosition,
    bar: AnnotatedBar,
    day_ticks: Sequence[TickRow],
    coverage: bool,
) -> ResolvedFill | None:
    """Motor de fills de salida intrabar (R32–R36, spec §5.2: nunca sobreestima el resultado)."""
    if coverage:
        return _resolve_fill_from_ticks(position, bar, day_ticks)
    return _resolve_fill_fallback(position, bar)


def _resolve_entry_fill(
    intent: EntryIntent,
    bar: AnnotatedBar,
    day_ticks: Sequence[TickRow],
    coverage: bool,
) -> ResolvedFill:
    """Precio de entrada (R22): primer tick de la vela si hay cobertura, si no `bar.open`.

    Geométricamente puro (sin spread/slippage): esos costos se cobran aparte como
    cargo explícito (`cost_applied`) para no contaminar el precio de ejecución.
    """
    if coverage:
        window_ticks = ticks_in_bar_window(bar, day_ticks)
        if window_ticks:
            first_tick = window_ticks[0]
            return ResolvedFill(price=first_tick.last, timestamp_utc=first_tick.timestamp_utc)
    return ResolvedFill(price=bar.open, timestamp_utc=bar.timestamp_utc)


def _compute_rr(
    direction: Direction, reference_price: float, stop_loss: float, take_profit: float
) -> float:
    """R:R propuesto para el embudo Inspector, a partir de `bar.close` como referencia."""
    if direction is Direction.LONG:
        risk = reference_price - stop_loss
        reward = take_profit - reference_price
    else:
        risk = stop_loss - reference_price
        reward = reference_price - take_profit
    if risk <= 0:
        return 0.0
    return reward / risk


class Simulator:
    """Orquestador event-driven de un backtest para `(candidate, symbol)` (R22).

    Verifica al construirse, antes de procesar la primera barra: `(1)` que
    `candidate` implementa `RiskLevelsProvider` (R21); `(2)` que `costs_config` es
    válido ("sin costos no hay reporte", R40); `(3)` que `symbol` está en la tabla de
    sesiones (`session_window`, R3c). Fail-fast con `BacktestConfigError` con contexto
    ante cualquier violación.
    """

    def __init__(
        self,
        candidate: StrategyCandidate,
        *,
        symbol: str,
        firm_profile: FirmProfile,
        risk_profile: RiskProfile,
        figure: SymbolFigure,
        funnel_config: InspectorFunnelConfig,
        costs_config: CostsConfig,
        news_events: Sequence[EconomicEvent],
        tick_store: RawParquetStore | None,
        starting_balance: float,
        dataset_hash: str,
        tick_cache: TickCache | None = None,
        stress: float = 1.0,
    ) -> None:
        if not isinstance(candidate, RiskLevelsProvider):
            message = (
                f"El candidato candidate_id={getattr(candidate, 'candidate_id', '?')!r} no "
                "implementa RiskLevelsProvider (risk_levels); requisito duro para simular "
                f"symbol={symbol!r} (R21, ADR-G3)."
            )
            raise BacktestConfigError(message)

        if not isinstance(costs_config, CostsConfig):
            message = (
                f"costs_config inválido para symbol={symbol!r}: se esperaba una instancia de "
                f"CostsConfig, se recibió {costs_config!r} (R40: sin costos no hay reporte)."
            )
            raise BacktestConfigError(message)

        try:
            session_window(symbol, _SESSION_PROBE_DATE)
        except KeyError as exc:
            message = (
                f"symbol={symbol!r} no está soportado por la tabla de sesiones "
                f"(genesis.data.sessions.SESSIONS): {exc} (R3c)."
            )
            raise BacktestConfigError(message) from exc

        self.candidate = candidate
        self.symbol = symbol
        self.firm_profile = firm_profile
        self.risk_profile = risk_profile
        self.figure = figure
        self.funnel_config = funnel_config
        self.costs_config = costs_config
        self.news_events = news_events
        self.tick_store = tick_store
        self.stress = stress
        # Caché de ticks compartible: si el orquestador de la ventana no inyecta uno, este
        # `Simulator` usa el suyo. En ambos casos la cota de días vivos es la misma.
        self._tick_cache = tick_cache if tick_cache is not None else TickCache()
        self._starting_balance = starting_balance
        self._intraday_peak_equity = starting_balance
        self._all_time_peak_equity = starting_balance
        self._session_closed_days: set[date] = set()

        candidate_id = getattr(candidate, "candidate_id", "?")
        provenance = RunProvenance(
            candidate_id=candidate_id,
            config_version=CONFIG_VERSION,
            dataset_hash=dataset_hash,
            firm_profile_hash=firm_profile_hash(firm_profile),
            risk_profile_hash=risk_profile_hash(risk_profile),
        )
        self.ledger = Ledger(provenance=provenance, entries=[])
        self.clock = SimulationClock()
        self.account = AccountState(balance=starting_balance, open_positions=[])
        self.clock.previous_day_close_balance = starting_balance

    def run(self, frame: pd.DataFrame) -> Ledger:
        """Ejecuta la simulación completa sobre `frame` y retorna el `Ledger` poblado (R22)."""
        for bar in iter_bars(frame, self.symbol, self.firm_profile):
            self._process_bar(bar)
        return self.ledger

    def _day_ticks_for(self, trading_day: date) -> list[TickRow]:
        """Ticks del `trading_day`: una lectura por día, no por barra (RI-G1).

        Delega en `TickCache`, que acota los días vivos: el caché anterior crecía sin
        límite y retenía los ticks de todo el run (Change #46, R30/R33).
        """
        if self.tick_store is None:
            return []
        return self._tick_cache.ticks_for_day(
            self.tick_store, self.symbol, trading_day, self.firm_profile
        )

    def _process_bar(self, bar: AnnotatedBar) -> None:
        # (0) reset diario: base doble del breach DAILY (R25).
        if self.clock.trading_day is not None and bar.trading_day != self.clock.trading_day:
            self.clock.previous_day_close_balance = self.account.balance
            self._intraday_peak_equity = self.account.balance
        # (a) alimenta el reloj (LookaheadError si retrocede, R5/R9).
        self.clock.advance(bar)

        day_ticks = self._day_ticks_for(bar.trading_day)
        # Mismo criterio de dos niveles que `has_sufficient_tick_coverage`, con la mitad
        # que solo depende del día resuelta por el caché en vez de por barra (R38).
        coverage = (
            self.tick_store is not None
            and self._tick_cache.has_chunk_for_day(
                self.tick_store, self.symbol, bar.trading_day, self.firm_profile
            )
            and has_ticks_in_bar_window(bar, day_ticks)
        )

        # (1) gestión de posiciones abiertas ANTES de nuevas entradas.
        self._manage_open_positions(bar, day_ticks, coverage)
        # (2) breaches en línea sobre equity flotante (T10).
        self._evaluate_breaches(bar, day_ticks, coverage)
        # (3)/(4) cierre forzado proactivo de sesión + guard defensivo (T10).
        self._enforce_session_close_and_guard(bar, day_ticks, coverage)

        # (5) nuevas entradas: solo si la cuenta no está agotada (R30).
        if not self.account.account_exhausted:
            self._process_new_entries(bar, day_ticks, coverage)

    def _manage_open_positions(
        self, bar: AnnotatedBar, day_ticks: list[TickRow], coverage: bool
    ) -> None:
        for position in list(self.account.open_positions):
            fill = _resolve_fill(position, bar, day_ticks, coverage)
            if fill is not None:
                self._close_position(position, fill)

    def _floating_pnl(self, position: OpenPosition, price: float) -> float:
        """P&L no realizado de `position` a `price` (bruto, sin costos), en dinero."""
        direction_sign = 1.0 if position.direction is Direction.LONG else -1.0
        points = (price - position.entry_price) * direction_sign
        return points * position.sizing_hint * self.figure.tick_value

    def _floating_equity(self, bar: AnnotatedBar) -> float:
        """Equity flotante intradía: balance realizado + P&L no realizado a `bar.close`."""
        unrealized = sum(
            self._floating_pnl(position, bar.close) for position in self.account.open_positions
        )
        return self.account.balance + unrealized

    def _evaluate_breaches(
        self, bar: AnnotatedBar, day_ticks: list[TickRow], coverage: bool
    ) -> None:
        """Detección de breaches DAILY/TOTAL en línea sobre equity flotante (R25, R26)."""
        del day_ticks, coverage
        floating_equity = self._floating_equity(bar)
        self._intraday_peak_equity = max(self._intraday_peak_equity, floating_equity)
        self._all_time_peak_equity = max(self._all_time_peak_equity, floating_equity)

        self._evaluate_daily_breach(bar, floating_equity)
        if not self.account.account_exhausted:
            self._evaluate_total_breach(bar, floating_equity)

    def _evaluate_daily_breach(self, bar: AnnotatedBar, floating_equity: float) -> None:
        """Breach DAILY (R25): base doble — el mayor entre pérdida vs. flotante intradía y
        pérdida vs. `clock.previous_day_close_balance`, contra `daily_loss_limit_pct`.
        """
        reference = self.clock.previous_day_close_balance
        if reference is None or reference <= 0:
            return
        loss_vs_close = reference - floating_equity
        loss_vs_peak = self._intraday_peak_equity - floating_equity
        daily_loss = max(loss_vs_close, loss_vs_peak)
        threshold = reference * (self.firm_profile.daily_loss_limit_pct / 100.0)
        if daily_loss >= threshold:
            self.ledger.append(
                BreachEvent(
                    kind=BreachKind.DAILY,
                    trading_day=bar.trading_day,
                    timestamp_utc=bar.timestamp_utc,
                    magnitude=daily_loss,
                    threshold=threshold,
                )
            )

    def _evaluate_total_breach(self, bar: AnnotatedBar, floating_equity: float) -> None:
        """Breach TOTAL (R26): pérdida vs. la referencia de `risk_profile.max_loss_limit_kind`.

        `STATIC` compara contra el balance inicial del run; `TRAILING` contra el pico de
        equity flotante alcanzado en toda la ejecución (ADR-G2). Terminal (R30/R31):
        agota la cuenta, sin lanzar excepción Python.
        """
        if self.risk_profile.max_loss_limit_kind is MaxLossLimitKind.TRAILING:
            reference = self._all_time_peak_equity
        else:
            reference = self._starting_balance
        if reference <= 0:
            return
        total_loss = reference - floating_equity
        threshold = reference * (self.risk_profile.max_loss_limit_pct / 100.0)
        if total_loss >= threshold:
            self.ledger.append(
                BreachEvent(
                    kind=BreachKind.TOTAL,
                    trading_day=bar.trading_day,
                    timestamp_utc=bar.timestamp_utc,
                    magnitude=total_loss,
                    threshold=threshold,
                    account_exhausted=True,
                )
            )
            self.account.account_exhausted = True

    def _enforce_session_close_and_guard(
        self, bar: AnnotatedBar, day_ticks: list[TickRow], coverage: bool
    ) -> None:
        """Cierre forzado proactivo de sesión (R23) + guard `SessionBoundaryError` (R24).

        El borde de sesión llega en la barra (`session_close_utc`, resuelto una vez por
        `trading_day` en `iter_bars`): recalcularlo aquí duplicaba el cómputo por barra
        (Change #46, R10).
        """
        close_utc = bar.session_close_utc

        if bar.timestamp_utc >= close_utc and bar.trading_day not in self._session_closed_days:
            if bar.trading_day.weekday() == _FRIDAY_WEEKDAY and not (
                self.risk_profile.weekend_holding_allowed
            ):
                self._register_weekend_breaches(bar)
            self._force_close_all_positions(bar, day_ticks, coverage)
            self._session_closed_days.add(bar.trading_day)

        if (
            bar.timestamp_utc > close_utc
            and bar.trading_day in self._session_closed_days
            and self.account.open_positions
        ):
            message = (
                f"Posición viva tras el cierre de sesión (close_utc={close_utc!r}) pese al "
                f"cierre forzado proactivo ya intentado para symbol={self.symbol!r}, "
                f"trading_day={bar.trading_day!r}, bar.timestamp_utc={bar.timestamp_utc!r}."
            )
            raise SessionBoundaryError(message)

    def _register_weekend_breaches(self, bar: AnnotatedBar) -> None:
        """R28: posiciones vivas al cierre del viernes con tenencia de fin de semana prohibida."""
        for position in self.account.open_positions:
            magnitude = abs(self._floating_pnl(position, bar.close))
            self.ledger.append(
                BreachEvent(
                    kind=BreachKind.WEEKEND,
                    trading_day=bar.trading_day,
                    timestamp_utc=bar.timestamp_utc,
                    magnitude=magnitude,
                    threshold=0.0,
                )
            )

    def _force_close_all_positions(
        self, bar: AnnotatedBar, day_ticks: list[TickRow], coverage: bool
    ) -> None:
        """R23/R53: cierra toda posición viva al final de sesión, con las reglas de §4.3.

        Reutiliza `_resolve_fill` (mismas reglas de fill); si no dispara (SL/TP fuera de
        rango esta vela), fuerza el cierre a `bar.close` — el flatten de fin de sesión es
        incondicional, no depende de tocar SL/TP.
        """
        for position in list(self.account.open_positions):
            fill = _resolve_fill(position, bar, day_ticks, coverage)
            if fill is None:
                fill = ResolvedFill(price=bar.close, timestamp_utc=bar.timestamp_utc)
            self._close_position(position, fill)

    def _process_new_entries(
        self, bar: AnnotatedBar, day_ticks: list[TickRow], coverage: bool
    ) -> None:
        risk_provider = cast(RiskLevelsProvider, self.candidate)
        intents = self.candidate.on_bar(bar)
        for intent in intents:
            stop_loss, take_profit = risk_provider.risk_levels(intent)
            proposed_rr = _compute_rr(intent.direction, bar.close, stop_loss, take_profit)
            verdict = inspect(
                intent,
                symbol=self.symbol,
                intent_time=bar.timestamp_utc,
                proposed_rr=proposed_rr,
                figure=self.figure,
                firm_profile=self.firm_profile,
                news_events=self.news_events,
                config=self.funnel_config,
            )
            if not verdict.authorized:
                self.ledger.append(
                    RejectionRecord(
                        candidate_id=intent.candidate_id,
                        symbol=self.symbol,
                        intent_time=bar.timestamp_utc,
                        verdict=verdict,
                    )
                )
                continue
            self._open_position(intent, bar, day_ticks, coverage, stop_loss, take_profit)

    def _open_position(
        self,
        intent: EntryIntent,
        bar: AnnotatedBar,
        day_ticks: list[TickRow],
        coverage: bool,
        stop_loss: float,
        take_profit: float,
    ) -> None:
        entry_fill = _resolve_entry_fill(intent, bar, day_ticks, coverage)
        ticks_window = ticks_in_bar_window(bar, day_ticks) if coverage else None
        spread_points = spread_for(
            self.symbol,
            entry_fill.timestamp_utc,
            self.figure,
            ticks_window,
            self.costs_config,
            stress=self.stress,
        )
        slippage_points = slippage_for(self.figure, self.costs_config, stress=self.stress)
        commission = commission_for(intent.sizing_hint, self.costs_config, stress=self.stress)
        points_total = spread_points + slippage_points
        cost_points = points_total * intent.sizing_hint * self.figure.tick_value
        entry_cost = commission + cost_points
        self.account.balance -= entry_cost

        position = OpenPosition(
            candidate_id=intent.candidate_id,
            symbol=self.symbol,
            direction=intent.direction,
            entry_time=entry_fill.timestamp_utc,
            entry_price=entry_fill.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            sizing_hint=intent.sizing_hint,
        )
        self.account.open_positions.append(position)
        self.ledger.append(
            FillRecord(
                candidate_id=intent.candidate_id,
                symbol=self.symbol,
                timestamp_utc=entry_fill.timestamp_utc,
                price=entry_fill.price,
                direction=intent.direction,
                is_exit=False,
                cost_applied=entry_cost,
                equity_after=self.account.balance,
            )
        )

        # Caso "vela única" (spec §9, pregunta abierta): si la MISMA vela ya dispara la
        # salida (SL/TP), cerrar de inmediato en vez de esperar a la siguiente barra.
        exit_fill = _resolve_fill(position, bar, day_ticks, coverage)
        if exit_fill is not None:
            self._close_position(position, exit_fill)

    def _close_position(self, position: OpenPosition, fill: ResolvedFill) -> None:
        # Mismo modelo monetario que el equity flotante, escrito una sola vez: si las dos
        # fórmulas divergieran, los breaches (que miran el flotante) dejarían de cuadrar
        # con el P&L realizado que va al ledger, y nada lo detectaría.
        pnl_gross = self._floating_pnl(position, fill.price)

        commission = commission_for(position.sizing_hint, self.costs_config, stress=self.stress)
        days_held = (fill.timestamp_utc.date() - position.entry_time.date()).days
        swap_money = 0.0
        if days_held >= 1:
            swap_rate = swap_for(
                self.symbol,
                days_held,
                self.figure,
                position.direction is Direction.LONG,
                stress=self.stress,
            )
            swap_money = abs(swap_rate) * position.sizing_hint

        total_cost = commission + swap_money
        self.account.balance += pnl_gross - total_cost

        self.ledger.append(
            FillRecord(
                candidate_id=position.candidate_id,
                symbol=self.symbol,
                timestamp_utc=fill.timestamp_utc,
                price=fill.price,
                direction=position.direction,
                is_exit=True,
                cost_applied=total_cost,
                equity_after=self.account.balance,
            )
        )
        self._register_news_breaches(position, fill)
        self.account.open_positions.remove(position)

    def _register_news_breaches(self, position: OpenPosition, fill: ResolvedFill) -> None:
        """R27/ADR-G7: un `BreachEvent(NEWS)` por cada ventana que intersecta la tenencia.

        Intersección de intervalos cerrados `[entry_time, exit_time] ∩ [w_start, w_end]`
        (`entry_time <= w_end and w_start <= exit_time`), evaluada al cierre de la
        posición (§5.1). `magnitude` = duración del solape en segundos; `threshold=0.0`
        (evento informativo y continuable, R29).
        """
        entry_time = position.entry_time
        exit_time = fill.timestamp_utc
        windows = news_windows(self.news_events, self.symbol, self.firm_profile)
        for window_start, window_end in windows:
            if entry_time <= window_end and window_start <= exit_time:
                overlap_start = max(entry_time, window_start)
                overlap_end = min(exit_time, window_end)
                magnitude = max((overlap_end - overlap_start).total_seconds(), 0.0)
                self.ledger.append(
                    BreachEvent(
                        kind=BreachKind.NEWS,
                        trading_day=exit_time.date(),
                        timestamp_utc=exit_time,
                        magnitude=magnitude,
                        threshold=0.0,
                    )
                )


def run_backtest(candidate: StrategyCandidate, frame: pd.DataFrame, **kwargs: Any) -> Ledger:
    """Wrapper funcional de conveniencia: `Simulator(candidate, **kwargs).run(frame)`."""
    return Simulator(candidate, **kwargs).run(frame)
