"""Estrategia compilada a partir de un genoma declarativo.

Cumple con StrategyCandidate y RiskLevelsProvider.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Mapping, Sequence

from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.genome.errors import CompiledCandidateStateError
from genesis.strategy.genome.schema import StrategyGenome


def _infer_gao_direction(
    open_price: float, close_price: float, epsilon: float = 1e-7
) -> Direction | None:
    """Dirección de referencia por retorno logarítmico acumulado Gao et al. (2018)."""
    if open_price <= 0 or close_price <= 0:
        return None
    if abs(close_price - open_price) <= epsilon:
        return None
    r_open = math.log(close_price / open_price)
    if r_open > 0:
        return Direction.LONG
    if r_open < 0:
        return Direction.SHORT
    return None


class CompiledGenomeCandidate:
    """Candidato ejecutable construido a partir de una especificación StrategyGenome pura."""

    def __init__(
        self,
        genome: StrategyGenome,
        *,
        figure: SymbolFigure,
        reference_balance: float,
        params: Mapping[str, float] | None = None,
        initial_daily_volumes: Sequence[float] | None = None,
        config_version: str = CONFIG_VERSION,
    ) -> None:
        self.genome = genome
        self.candidate_id: str = genome.metadata.id
        self._figure = figure
        self._reference_balance = reference_balance
        self._config_version = config_version
        self._params = dict(params or {})

        # 1. Trigger config (ORB)
        trigger_cfg = genome.alpha.entry_trigger
        raw_n_minutes = self._params.get("n_minutes", trigger_cfg.get("range_minutes", 30))
        self._n_minutes = int(raw_n_minutes)

        # 2. Risk / Sizing config
        self._risk_pct = float(self._params.get("risk_pct", 0.01))
        risk_params = genome.risk_exit.params
        if "atr_stop_frac" in self._params:
            self._atr_stop_frac: float | None = float(self._params["atr_stop_frac"])
        elif "atr_stop_frac" in risk_params:
            val = risk_params["atr_stop_frac"]
            self._atr_stop_frac = float(val) if val is not None else None
        else:
            self._atr_stop_frac = None

        self._atr_period = int(risk_params.get("atr_period", 14))

        # TP multiple
        self._has_explicit_tp = (
            "tp_rr_multiple" in self._params or "tp_rr_multiple" in risk_params
        )
        self._tp_rr_multiple = float(
            self._params.get("tp_rr_multiple", risk_params.get("tp_rr_multiple", 3.0))
        )

        # 3. Regime filter config (RVOL)
        regime_cfg = genome.alpha.regime_filter
        if regime_cfg is not None:
            self._rvol_threshold = float(
                self._params.get("rvol_threshold", regime_cfg.get("threshold", 0.0))
            )
            self._rvol_lookback_days = int(
                self._params.get("rvol_lookback_days", regime_cfg.get("lookback_days", 20))
            )
        else:
            self._rvol_threshold = float(self._params.get("rvol_threshold", 0.0))
            self._rvol_lookback_days = int(self._params.get("rvol_lookback_days", 20))

        self._epsilon = 0.5 * 10 ** (-figure.digits)

        # Estado mutable de sesión/día
        self._current_trading_day = None
        self._range_high: float | None = None
        self._range_low: float | None = None
        self._reference_direction: Direction | None = None
        self._signal_emitted_today: bool = False
        self._minute_index: int = 0

        # Ventana de apertura y RVOL
        self._open_window_open: float | None = None
        self._last_open_window_close: float | None = None
        self._open_window_volume: float = 0.0
        self._session_rvol: float | None = None
        self._session_rvol_passed: bool = False
        self._rvol_evaluated: bool = False
        self._daily_open_volumes: deque[float] = deque(
            initial_daily_volumes or [], maxlen=self._rvol_lookback_days
        )

        # Estado ATR continuo
        self._atr_value: float | None = None
        self._atr_bars_seen: int = 0
        self._atr_last_close: float | None = None
        self._atr_warmup_sum: float = 0.0

        # Niveles pendientes (pop-on-read)
        self._pending_risk_levels: tuple[float, float | None] | None = None

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        """Procesa una barra ya cerrada forward-only; retorna cero o una EntryIntent."""
        # 1. Reset diario
        if bar.trading_day != self._current_trading_day:
            if self._current_trading_day is not None and self._minute_index >= self._n_minutes:
                self._daily_open_volumes.append(self._open_window_volume)
            self._current_trading_day = bar.trading_day
            self._range_high = None
            self._range_low = None
            self._reference_direction = None
            self._signal_emitted_today = False
            self._minute_index = 0
            self._open_window_open = None
            self._last_open_window_close = None
            self._open_window_volume = 0.0
            self._session_rvol = None
            self._session_rvol_passed = False
            self._rvol_evaluated = False

        # 2. Actualización ATR si está en sesión
        if bar.in_session:
            self._update_atr(bar)

        # 3. Fuera de sesión no opera
        if not bar.in_session:
            return []

        # 4. Formación de rango
        if self._minute_index < self._n_minutes:
            if self._minute_index == 0:
                self._open_window_open = bar.open
            self._range_high = (
                bar.high if self._range_high is None else max(self._range_high, bar.high)
            )
            self._range_low = (
                bar.low if self._range_low is None else min(self._range_low, bar.low)
            )
            bar_vol = float(getattr(bar, "tick_volume", getattr(bar, "volume", 0.0)))
            self._open_window_volume += bar_vol
            self._last_open_window_close = bar.close
            self._minute_index += 1
            return []

        # 5. Evaluación de dirección Gao et al. y RVOL
        if not self._rvol_evaluated:
            self._rvol_evaluated = True
            if self._open_window_open is not None:
                close_ref = (
                    self._last_open_window_close
                    if self._last_open_window_close is not None
                    else bar.close
                )
                self._reference_direction = _infer_gao_direction(
                    self._open_window_open, close_ref, epsilon=self._epsilon
                )
            else:
                self._reference_direction = None

            if self._rvol_threshold <= 0.0:
                self._session_rvol_passed = True
                self._session_rvol = 1.0
            elif len(self._daily_open_volumes) < self._rvol_lookback_days:
                self._session_rvol_passed = False
                self._session_rvol = None
            else:
                baseline_vol = statistics.median(self._daily_open_volumes)
                if baseline_vol > 0:
                    self._session_rvol = self._open_window_volume / baseline_vol
                else:
                    self._session_rvol = 0.0
                self._session_rvol_passed = self._session_rvol >= self._rvol_threshold

        # 6. Evaluación de ruptura
        if (
            self._signal_emitted_today
            or self._reference_direction is None
            or not self._session_rvol_passed
        ):
            self._minute_index += 1
            return []

        intent = self._evaluate_trigger(bar)
        self._minute_index += 1
        return [intent] if intent is not None else []

    def _update_atr(self, bar: AnnotatedBar) -> None:
        """ATR-Wilder incremental."""
        last = self._atr_last_close
        if last is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(bar.high - bar.low, abs(bar.high - last), abs(bar.low - last))
        self._atr_last_close = bar.close

        if self._atr_bars_seen < self._atr_period:
            self._atr_bars_seen += 1
            self._atr_warmup_sum += true_range
            if self._atr_bars_seen == self._atr_period:
                self._atr_value = self._atr_warmup_sum / self._atr_period
        else:
            current_atr = self._atr_value
            if current_atr is None:
                msg = f"_update_atr sin atr_value calentado (seen={self._atr_bars_seen})"
                raise CompiledCandidateStateError(msg)
            self._atr_value = (
                (current_atr * (self._atr_period - 1)) + true_range
            ) / self._atr_period

    def _evaluate_trigger(self, bar: AnnotatedBar) -> EntryIntent | None:
        direction = self._reference_direction
        range_high, range_low = self._range_high, self._range_low
        if range_high is None or range_low is None:
            msg = f"_evaluate_trigger sin rango formado (high={range_high!r}, low={range_low!r})"
            raise CompiledCandidateStateError(msg)

        fired = (direction is Direction.LONG and bar.close > range_high) or (
            direction is Direction.SHORT and bar.close < range_low
        )
        if not fired:
            return None

        entry_reference = bar.close
        stop, take_profit, sizing = self._compute_risk_geometry(
            direction, entry_reference, range_high, range_low
        )
        self._pending_risk_levels = (stop, take_profit)
        self._signal_emitted_today = True
        return EntryIntent(
            direction=direction,
            sizing_hint=sizing,
            candidate_id=self.candidate_id,
            config_version=self._config_version,
        )

    def _compute_risk_geometry(
        self, direction: Direction, entry_reference: float, range_high: float, range_low: float
    ) -> tuple[float, float | None, float]:
        use_atr = self._atr_stop_frac is not None and self._atr_value is not None
        if direction is Direction.LONG:
            stop = range_low - self._atr_stop_frac * self._atr_value if use_atr else range_low
        else:
            stop = range_high + self._atr_stop_frac * self._atr_value if use_atr else range_high

        stop_distance = abs(entry_reference - stop)
        if stop_distance <= 0:
            msg = f"distancia_stop<=0 (entry={entry_reference}, stop={stop}, dir={direction})"
            raise CompiledCandidateStateError(msg)

        # TP: si es chandelier_trailing puro sin TP explicito, take_profit es None
        is_chandelier = self.genome.risk_exit.kind == "chandelier_trailing"
        if is_chandelier and not self._has_explicit_tp:
            take_profit = None
        else:
            take_profit = (
                entry_reference + self._tp_rr_multiple * stop_distance
                if direction is Direction.LONG
                else entry_reference - self._tp_rr_multiple * stop_distance
            )

        sizing = (self._risk_pct * self._reference_balance) / (
            stop_distance * self._figure.value_per_point
        )
        return (stop, take_profit, sizing)

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float | None]:
        """Retorna (stop_loss, take_profit) de la señal pendiente con semántica pop-on-read."""
        if self._pending_risk_levels is None:
            msg = f"risk_levels() sin señal pendiente para {self.candidate_id!r}"
            raise CompiledCandidateStateError(msg)
        levels = self._pending_risk_levels
        self._pending_risk_levels = None
        return levels
