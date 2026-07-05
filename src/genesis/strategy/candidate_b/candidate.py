"""`CandidateB` — rango de apertura + gatillo de ruptura por cierre (R48-R71).

Importa solo stdlib + `genesis.data.{store,symbols}` (capa 1) + `genesis.strategy.
{contract,errors}` (misma capa 2). **Nunca** importa el paquete de backtest de capa 3
(R50) ni `genesis.strategy.inspector`/`genesis.strategy.common` (aislamiento del
candidato, spec §2.1/§2.5): el sentido capa 2 -> capa 1 se preserva, nunca capa 2 ->
capa 3.
"""

from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent, register_candidate
from genesis.strategy.errors import CandidateBStateError


def _infer_direction(bar: AnnotatedBar, epsilon: float) -> Direction | None:
    """Dirección de referencia de la primera barra `in_session` del día (R56).

    `LONG` si `close - open > epsilon`; `SHORT` si `open - close > epsilon`; `None`
    (doji) si `abs(close - open) <= epsilon` (medio tick de tolerancia).
    """
    diff = bar.close - bar.open
    if diff > epsilon:
        return Direction.LONG
    if -diff > epsilon:
        return Direction.SHORT
    return None


@register_candidate("B")
class CandidateB:
    """Candidato B (ORB intradía, spec §2.3): rango de apertura + gatillo de ruptura por cierre.

    Implementa `StrategyCandidate` (`on_bar`) **y** `RiskLevelsProvider`
    (`risk_levels`) en la misma clase, satisfecho por **duck typing** (ADR-E1): no se
    importa el `Protocol` estructural de capa 3 (backtest/simulador) en este módulo (R50).

    Una instancia está ligada a un único símbolo del universo (US500/NAS100/US30/
    GER40) y a un balance de referencia fijo, ambos de construcción: **nunca** se
    comparte una instancia entre streams de más de un símbolo (`AnnotatedBar` no
    porta `symbol`; el estado incremental se corrompería silenciosamente — R53/R87,
    mismo patrón que `Simulator`: 1 orquestador por `(candidate, symbol)`).

    El cierre forzado de sesión (spec §2.3 "Salida") **no** se implementa aquí:
    `Simulator._enforce_session_close_and_guard` (Issue G, agnóstico a
    `candidate_id`) lo ejecuta de forma proactiva al alcanzar `close_utc` + guard
    `SessionBoundaryError`. Este candidato nunca emite una señal de cierre (R78/R79).

    Nota de estilo (RI-E2): `_minute_index` sigue incrementándose barra a barra tras
    la congelación del rango y tras emitir la señal del día; es intencional (R55.6),
    inocuo (solo se compara `>= n_minutes`), y siempre usado.
    """

    candidate_id: str = "B"

    def __init__(
        self,
        *,
        figure: SymbolFigure,
        reference_balance: float,
        n_minutes: int,
        risk_pct: float,
        atr_stop_frac: float | None = None,
        atr_period: int = 14,
        tp_rr_multiple: float = 3.0,
        config_version: str = CONFIG_VERSION,
    ) -> None:
        # Constantes derivadas del constructor (R53).
        self._figure = figure
        self._reference_balance = reference_balance
        self._n_minutes = n_minutes
        self._risk_pct = risk_pct
        self._atr_stop_frac = atr_stop_frac
        self._atr_period = atr_period
        self._tp_rr_multiple = tp_rr_multiple
        self._config_version = config_version
        self._epsilon = 0.5 * 10 ** (-figure.digits)  # medio tick, R56

        # Estado mutable de rango/día (R54, reseteado por R55.1).
        self._current_trading_day = None
        self._range_high: float | None = None
        self._range_low: float | None = None
        self._reference_direction: Direction | None = None
        self._signal_emitted_today: bool = False
        self._minute_index: int = 0

        # Estado ATR-Wilder-14 incremental, continuo across días (R54, NO reseteado).
        self._atr_value: float | None = None
        self._atr_bars_seen: int = 0
        self._atr_last_close: float | None = None
        self._atr_warmup_sum: float = 0.0

        # Asociación intent<->niveles, efímera, pop-on-read (R71, ADR-E4).
        self._pending_risk_levels: tuple[float, float] | None = None

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        """Procesa una barra ya cerrada; retorna cero o una `EntryIntent` (R55, orden estricto)."""
        # 1. RESET DIARIO (R55.1) — el estado ATR (paso 2) NO se resetea.
        if bar.trading_day != self._current_trading_day:
            self._current_trading_day = bar.trading_day
            self._range_high = None
            self._range_low = None
            self._reference_direction = None
            self._signal_emitted_today = False
            self._minute_index = 0

        # 2. ATR (R55.2): incondicional si in_session, incluso ya emitida la señal.
        if bar.in_session:
            self._update_atr(bar)

        # 3. FILTRO DE SESIÓN (R55.3): fuera de sesión no toca rango/dirección/flag.
        if not bar.in_session:
            return []

        # 4. DIRECCIÓN DE REFERENCIA (R55.4, R56): solo en la 1.ª barra in_session del día.
        if self._minute_index == 0:
            self._reference_direction = _infer_direction(bar, self._epsilon)

        # 5. FORMACIÓN DEL RANGO (R55.5, R57): idx en [0, n_minutes).
        if self._minute_index < self._n_minutes:
            self._range_high = (
                bar.high if self._range_high is None else max(self._range_high, bar.high)
            )
            self._range_low = bar.low if self._range_low is None else min(self._range_low, bar.low)
            self._minute_index += 1
            return []

        # 6. GATILLO (R55.6, R58): idx >= n_minutes (rango ya congelado).
        if self._signal_emitted_today or self._reference_direction is None:
            self._minute_index += 1
            return []
        intent = self._evaluate_trigger(bar)
        self._minute_index += 1
        return [intent] if intent is not None else []

    def _update_atr(self, bar: AnnotatedBar) -> None:
        """ATR-Wilder-14 incremental propio (R61-R65), llamado en `on_bar` paso 2."""
        last = self._atr_last_close
        if last is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(bar.high - bar.low, abs(bar.high - last), abs(bar.low - last))
        self._atr_last_close = bar.close  # actualizado DESPUÉS de calcular TR (cruza día, R62)

        if self._atr_bars_seen < self._atr_period:
            self._atr_bars_seen += 1
            self._atr_warmup_sum += true_range
            if self._atr_bars_seen == self._atr_period:
                self._atr_value = self._atr_warmup_sum / self._atr_period  # media simple
        else:
            current_atr = self._atr_value
            if current_atr is None:
                # Estructuralmente inalcanzable: `_atr_bars_seen >= _atr_period` implica
                # que el calentamiento ya fijó `_atr_value` (invariante R63).
                message = (
                    f"_update_atr en fase de suavizado sin _atr_value calentado "
                    f"(_atr_bars_seen={self._atr_bars_seen!r}) — invariante R63 violado."
                )
                raise CandidateBStateError(message)
            self._atr_value = (
                (current_atr * (self._atr_period - 1)) + true_range
            ) / self._atr_period

    def _evaluate_trigger(self, bar: AnnotatedBar) -> EntryIntent | None:
        """Gatillo de ruptura por cierre, estricto (R58); construye la señal si dispara."""
        direction = self._reference_direction
        range_high, range_low = self._range_high, self._range_low
        if range_high is None or range_low is None:
            # Estructuralmente inalcanzable: `on_bar` solo invoca este método cuando
            # `_minute_index >= n_minutes`, lo que implica que el rango ya fue formado.
            message = (
                f"_evaluate_trigger invocado con rango sin formar "
                f"(range_high={range_high!r}, range_low={range_low!r}) — invariante R57 violado."
            )
            raise CandidateBStateError(message)
        fired = (direction is Direction.LONG and bar.close > range_high) or (
            direction is Direction.SHORT and bar.close < range_low
        )
        if not fired:
            return None

        entry_reference = bar.close  # R66, == referencia de `_compute_rr` de G
        stop, take_profit, sizing = self._compute_risk_geometry(
            direction, entry_reference, range_high, range_low
        )
        self._pending_risk_levels = (stop, take_profit)  # R71, asociación síncrona
        self._signal_emitted_today = True  # R59
        return EntryIntent(
            direction=direction,
            sizing_hint=sizing,
            candidate_id=self.candidate_id,
            config_version=self._config_version,
        )

    def _compute_risk_geometry(
        self, direction: Direction, entry_reference: float, range_high: float, range_low: float
    ) -> tuple[float, float, float]:
        """Geometría stop/TP/sizing del gatillo (R66-R70), invocada en el instante síncrono."""
        use_atr = self._atr_stop_frac is not None and self._atr_value is not None
        if direction is Direction.LONG:
            stop = range_low - self._atr_stop_frac * self._atr_value if use_atr else range_low
        else:
            stop = range_high + self._atr_stop_frac * self._atr_value if use_atr else range_high

        distancia_stop = abs(entry_reference - stop)
        if distancia_stop <= 0:
            message = (
                f"distancia_stop<=0 (entry_reference={entry_reference!r}, stop_loss={stop!r}, "
                f"direction={direction!r}) — invariante de geometría R58/R66 violado."
            )
            raise CandidateBStateError(message)

        take_profit = (
            entry_reference + self._tp_rr_multiple * distancia_stop
            if direction is Direction.LONG
            else entry_reference - self._tp_rr_multiple * distancia_stop
        )

        sizing = (self._risk_pct * self._reference_balance) / (
            distancia_stop * self._figure.tick_value
        )
        return (stop, take_profit, sizing)

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float]:
        """Retorna `(stop_loss, take_profit)` de la señal recién emitida (R52, R71, pop-on-read)."""
        if self._pending_risk_levels is None:
            message = (
                f"risk_levels() invocado sin señal pendiente para "
                f"candidate_id={self.candidate_id!r}, intent={intent!r} — invariante R71 violado."
            )
            raise CandidateBStateError(message)
        levels = self._pending_risk_levels
        self._pending_risk_levels = None  # pop-on-read (ADR-E4)
        return levels
