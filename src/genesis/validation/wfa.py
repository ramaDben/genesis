"""Walk-forward rolling con grid IS exhaustivo, selección DSR-IS, OOS cosido y WFE.

Capa 4 (`genesis.validation`): consume la API pública ya cerrada de `genesis.data`,
`genesis.strategy` y `genesis.backtest` (capas 1-3) en un solo sentido, sin
modificar ninguno de los tres árboles (R61). Grid exhaustivo 27 combinaciones de
ejecución / 9 configuraciones de señal (spec §6.2, Candidato B): sin muestreo, sin
paralelismo de procesos ni hilos (R32), loop secuencial.

Advertencia heredada del Candidato B (Rg-1, aceptada, no defecto de este Change):
cada combinación/ventana instancia un `CandidateB` **nuevo** (nunca reutilizado);
el estado ATR-Wilder-14 arranca en frío (`atr_value=None`) al inicio de cada
instancia, de modo que los primeros `atr_period` (14) días de cada ventana pueden
operar sin componente ATR del stop. Con `IS_WINDOW_TRADING_DAYS = 252` el sesgo es
despreciable (14/252).
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

import genesis.backtest.ledger as backtest_ledger
from genesis.backtest.costs import CostsConfig
from genesis.backtest.ledger import FillRecord, Ledger, LedgerEntry, RunProvenance
from genesis.backtest.metrics import sharpe_pointwise
from genesis.backtest.risk_profile import RiskProfile, risk_profile_hash
from genesis.backtest.simulator import Simulator
from genesis.backtest.ticks import TickCache
from genesis.data.calendar import EconomicEvent
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, firm_profile_hash
from genesis.data.store import iter_bars
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation import window_config as window_config_module
from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation.errors import WfaConfigError
from genesis.validation.window_config import GridConfig, WfaWindowConfig, window_identity_hash

CONFIG_VERSION: str = "genesis-validation/1"
"""Versión del esquema de configuración de esta capa (distinta del `config_version`
de `genesis-backtest` embebido en cada `RunProvenance` de los ledgers, §2 del spec)."""

MIN_TRADES_IS: int = 10
"""Umbral mínimo de trades OOS-de-selección agregados por configuración de señal
(decisión 5, spec §3): por debajo de este umbral, la configuración recibe DSR-IS
`-inf` (excluida de la selección, sin abortar la ventana, R26)."""

_N_TRIALS_SIGNAL: int = 9
_N_TRIALS_EXECUTION: int = 27


@dataclass(frozen=True, slots=True)
class WindowResult:
    """Resultado congelado de una única ventana walk-forward (R29).

    `is_ledger_winning` es el `Ledger` IS de la combinación de ejecución ganadora
    (usado para el denominador del WFE, R31); `oos_ledger` es el run OOS de la
    ventana con los parámetros ya congelados.
    """

    index: int
    is_trading_day_range: tuple[date, date]
    oos_trading_day_range: tuple[date, date]
    dataset_hash_is: str
    dataset_hash_oos: str
    winning_combo: tuple[int, float, float]
    winning_signal_config: tuple[int, float]
    dsr_is: float
    is_ledger_winning: Ledger
    oos_ledger: Ledger
    n_trials_signal: int
    n_trials_execution: int
    window_identity_hash: str


@dataclass(frozen=True, slots=True)
class WfaResult:
    """Resultado agregado del walk-forward completo para `(candidate_id, symbol)` (R33)."""

    candidate_id: str
    symbol: str
    config_version: str
    windows: Sequence[WindowResult]
    oos_ledger_cosido: Ledger
    wfe: float
    n_windows: int
    n_trials_signal_total: int
    n_trials_execution_total: int
    seed: int


def _extract_exit_returns(ledger: Ledger) -> list[float]:
    """Deltas de `equity_after` de los `FillRecord` de salida del `ledger` (§2 del spec).

    Replica el patrón `genesis.backtest.metrics._running_equity_deltas` + filtro
    `is_exit`, duplicado a propósito en `wfa.py` y `montecarlo.py` (ADR-H5): NO
    importa ningún símbolo privado de `genesis.backtest.metrics` (R61).
    """
    deltas: list[float] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                deltas.append(payload.equity_after - previous_equity)
            previous_equity = payload.equity_after
    return deltas


def _plan_windows(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
) -> tuple[list[date], dict[date, tuple[int, int]]]:
    """Pasada única de planificación (R8, ADR-H3): `days` ordenados + `row_span` posicional.

    Recorre `iter_bars(frame, symbol, firm_profile)` una sola vez, forward-only, sin
    reposicionar cursor ni reimplementar `_trading_day`. `row_span[day]` es
    `(posición_mínima, posición_máxima)` de fila del frame crudo para ese
    `trading_day`, en el mismo orden posicional que `frame` (invariante: `frame` ya
    viene ordenado cronológicamente, impuesto por `iter_bars`).
    """
    days: list[date] = []
    row_span: dict[date, tuple[int, int]] = {}
    for position, bar in enumerate(iter_bars(frame, symbol, firm_profile)):
        trading_day = bar.trading_day
        if trading_day not in row_span:
            days.append(trading_day)
            row_span[trading_day] = (position, position)
        else:
            first_position, _ = row_span[trading_day]
            row_span[trading_day] = (first_position, position)
    return days, row_span


def _validate_history(
    days: Sequence[date],
    window_config: WfaWindowConfig,
    *,
    candidate_id: str,
    symbol: str,
) -> None:
    """Guarda de historia insuficiente (R11): fail-fast antes de cualquier backtest."""
    required = window_config.is_window_trading_days + window_config.oos_window_trading_days
    if len(days) < required:
        message = (
            f"Historia insuficiente para candidate_id={candidate_id!r} symbol={symbol!r}: "
            f"{len(days)} trading_day distintos disponibles, se requieren >= {required} "
            f"(is_window_trading_days={window_config.is_window_trading_days} + "
            f"oos_window_trading_days={window_config.oos_window_trading_days}, R11)."
        )
        raise WfaConfigError(message)


def _iter_window_bounds(
    n_days: int,
    window_config: WfaWindowConfig,
) -> Iterator[tuple[int, int, int, int]]:
    """Enumera `(k, is_start, is_end, oos_end)`, límites exclusivos sobre la lista `days` (R9).

    IS: `days[is_start:is_end]`; OOS: `days[is_end:oos_end]`. Con
    `step_trading_days == oos_window_trading_days` (default), los tramos OOS de
    ventanas consecutivas son contiguos, sin solape ni hueco.
    """
    is_window = window_config.is_window_trading_days
    oos_window = window_config.oos_window_trading_days
    step = window_config.step_trading_days
    k = 0
    while k * step + is_window + oos_window <= n_days:
        is_start = k * step
        is_end = is_start + is_window
        oos_end = is_end + oos_window
        yield k, is_start, is_end, oos_end
        k += 1


def _slice_frame_by_days(
    frame: pd.DataFrame,
    row_span: dict[date, tuple[int, int]],
    days_slice: Sequence[date],
) -> pd.DataFrame:
    """Trocea `frame` por span posicional contiguo de `days_slice` (R10, ADR-H3).

    `frame.iloc[first_position:last_position + 1]`, límites resueltos de
    `row_span` de la pasada de planificación de `_plan_windows` — nunca por
    comparación de fechas naive de la columna `timestamp` ni reejecutando
    `iter_bars` por ventana.
    """
    first_position = row_span[days_slice[0]][0]
    last_position = row_span[days_slice[-1]][1]
    return frame.iloc[first_position : last_position + 1]


def _plan_and_validate_windows(
    frame: pd.DataFrame,
    symbol: str,
    firm_profile: FirmProfile,
    window_config: WfaWindowConfig,
    *,
    candidate_id: str,
) -> tuple[list[date], dict[date, tuple[int, int]]]:
    """Planifica ventanas (R8) y aplica la guarda de historia insuficiente (R11)."""
    days, row_span = _plan_windows(frame, symbol, firm_profile)
    _validate_history(days, window_config, candidate_id=candidate_id, symbol=symbol)
    return days, row_span


def _run_execution_combo(
    combo: tuple[int, float, float],
    *,
    frame: pd.DataFrame,
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
) -> Ledger:
    """Instancia `CandidateB`/`Simulator` **nuevos** para `combo` y corre `frame` (R24).

    El `tick_cache` es del orquestador de la ventana, no de esta llamada: los combos
    comparten los mismos días y así no se relee el store por cada uno (Change #46, R30).
    """
    n_minutes, atr_stop_frac, risk_pct = combo
    candidate = CandidateB(
        figure=figure,
        reference_balance=starting_balance,
        n_minutes=n_minutes,
        atr_stop_frac=atr_stop_frac,
        risk_pct=risk_pct,
    )
    simulator = Simulator(
        candidate,
        symbol=symbol,
        firm_profile=firm_profile,
        risk_profile=risk_profile,
        figure=figure,
        funnel_config=funnel_config,
        costs_config=costs_config,
        news_events=news_events,
        tick_store=tick_store,
        starting_balance=starting_balance,
        dataset_hash=dataset_hash,
        tick_cache=tick_cache,
    )
    return simulator.run(frame)


def _select_winning_signal_config(
    combo_by_signal: Mapping[tuple[int, float], Sequence[tuple[tuple[int, float, float], Ledger]]],
    *,
    candidate_id: str,
    symbol: str,
    window_index: int,
) -> tuple[tuple[int, float], float]:
    """DSR-IS por config de señal (R26), guarda de viabilidad de ventana (R27)."""
    signal_dsr: dict[tuple[int, float], float] = {}
    for signal_config, combos in combo_by_signal.items():
        aggregated_returns: list[float] = []
        for _combo, ledger_is in combos:
            aggregated_returns.extend(_extract_exit_returns(ledger_is))
        if len(aggregated_returns) < MIN_TRADES_IS:
            signal_dsr[signal_config] = float("-inf")
        else:
            signal_dsr[signal_config] = deflated_sharpe_ratio(
                aggregated_returns, n_trials=_N_TRIALS_SIGNAL
            )

    if all(dsr == float("-inf") for dsr in signal_dsr.values()):
        message = (
            f"Ventana inviable para candidate_id={candidate_id!r} symbol={symbol!r} "
            f"window_index={window_index!r}: las {len(signal_dsr)} configuraciones de señal "
            f"quedaron por debajo de MIN_TRADES_IS={MIN_TRADES_IS} trades agregados (R27)."
        )
        raise WfaConfigError(message)

    winning_signal_config = max(signal_dsr, key=lambda key: signal_dsr[key])
    return winning_signal_config, signal_dsr[winning_signal_config]


def _select_winning_execution_combo(
    combos: Sequence[tuple[tuple[int, float, float], Ledger]],
) -> tuple[tuple[int, float, float], Ledger]:
    """Desempate de sizing dentro de la config de señal ganadora (R28): mayor Sharpe IS."""
    return max(combos, key=lambda pair: sharpe_pointwise(pair[1]))


def _run_single_window(
    *,
    index: int,
    candidate_id: str,
    symbol: str,
    frame_is: pd.DataFrame,
    frame_oos: pd.DataFrame,
    is_days: Sequence[date],
    oos_days: Sequence[date],
    dataset_hash_is: str,
    dataset_hash_oos: str,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    tick_store: RawParquetStore | None,
    starting_balance: float,
    grid_config: GridConfig,
    grid_config_hash: str,
) -> WindowResult:
    """Grid IS exhaustivo, selección DSR-IS, congelamiento y run OOS de una ventana (R24-R29)."""
    # Un solo caché de ticks para toda la ventana: los combos y el run OOS recorren los
    # mismos días, y cada `Simulator` nuevo volvería a leerlos del store (Change #46, R32).
    tick_cache = TickCache()
    combo_by_signal: dict[tuple[int, float], list[tuple[tuple[int, float, float], Ledger]]] = {}
    for combo in grid_config.execution_combos():
        n_minutes, atr_stop_frac, _risk_pct = combo
        ledger_is = _run_execution_combo(
            combo,
            frame=frame_is,
            symbol=symbol,
            firm_profile=firm_profile,
            risk_profile=risk_profile,
            figure=figure,
            funnel_config=funnel_config,
            costs_config=costs_config,
            news_events=news_events,
            tick_store=tick_store,
            starting_balance=starting_balance,
            dataset_hash=dataset_hash_is,
            tick_cache=tick_cache,
        )
        signal_config = (n_minutes, atr_stop_frac)
        combo_by_signal.setdefault(signal_config, []).append((combo, ledger_is))

    winning_signal_config, winning_dsr = _select_winning_signal_config(
        combo_by_signal, candidate_id=candidate_id, symbol=symbol, window_index=index
    )
    winning_combo, winning_ledger_is = _select_winning_execution_combo(
        combo_by_signal[winning_signal_config]
    )

    oos_ledger = _run_execution_combo(
        winning_combo,
        frame=frame_oos,
        symbol=symbol,
        firm_profile=firm_profile,
        risk_profile=risk_profile,
        figure=figure,
        funnel_config=funnel_config,
        costs_config=costs_config,
        news_events=news_events,
        tick_store=tick_store,
        starting_balance=starting_balance,
        dataset_hash=dataset_hash_oos,
        tick_cache=tick_cache,
    )

    identity_hash = window_identity_hash(
        candidate_id, symbol, dataset_hash_is, dataset_hash_oos, grid_config_hash, CONFIG_VERSION
    )

    return WindowResult(
        index=index,
        is_trading_day_range=(is_days[0], is_days[-1]),
        oos_trading_day_range=(oos_days[0], oos_days[-1]),
        dataset_hash_is=dataset_hash_is,
        dataset_hash_oos=dataset_hash_oos,
        winning_combo=winning_combo,
        winning_signal_config=winning_signal_config,
        dsr_is=winning_dsr,
        is_ledger_winning=winning_ledger_is,
        oos_ledger=oos_ledger,
        n_trials_signal=_N_TRIALS_SIGNAL,
        n_trials_execution=_N_TRIALS_EXECUTION,
        window_identity_hash=identity_hash,
    )


def _stitch_oos_ledgers(
    windows: Sequence[WindowResult],
    *,
    candidate_id: str,
    symbol: str,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    dataset_hash: str,
) -> Ledger:
    """Cose los `Ledger` OOS de todas las ventanas, en orden, bajo una única `RunProvenance` (R30).

    Sin solape entre ventanas (garantizado por R9); solo contiene trades OOS (R62).
    """
    provenance = RunProvenance(
        candidate_id=candidate_id,
        config_version=backtest_ledger.CONFIG_VERSION,
        dataset_hash=dataset_hash,
        firm_profile_hash=firm_profile_hash(firm_profile),
        risk_profile_hash=risk_profile_hash(risk_profile),
    )
    entries = [
        LedgerEntry(provenance=provenance, payload=entry.payload)
        for window in windows
        for entry in window.oos_ledger.entries
    ]
    return Ledger(provenance=provenance, entries=entries)


def _compute_wfe(oos_ledger_cosido: Ledger, windows: Sequence[WindowResult]) -> float:
    """WFE (R31): `sharpe_pointwise(oos_cosido) / mean(sharpe_pointwise(is_ganador))`.

    `0.0` (sentinel documentado) si el denominador es `0.0` — evita división por
    cero; el gate G2 lo evaluará como fallo en Issue J, no aquí.
    """
    numerator = sharpe_pointwise(oos_ledger_cosido)
    is_sharpes = [sharpe_pointwise(window.is_ledger_winning) for window in windows]
    denominator = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def run_wfa(
    candidate_id: str,
    symbol: str,
    frame: pd.DataFrame,
    firm_profile: FirmProfile,
    risk_profile: RiskProfile,
    figure: SymbolFigure,
    funnel_config: InspectorFunnelConfig,
    costs_config: CostsConfig,
    news_events: Sequence[EconomicEvent],
    dataset_store: RawParquetStore,
    tick_store: RawParquetStore | None,
    starting_balance: float,
    *,
    window_config: WfaWindowConfig | None = None,
    grid_config: GridConfig | None = None,
    seed: int,
) -> WfaResult:
    """Walk-forward rolling completo para `(candidate_id, symbol)` (R23).

    `dataset_store` (siempre requerido, distinto de `tick_store` que puede ser
    `None`) se usa exclusivamente para `chunk_hash(frame)`: el hash de dataset no
    depende de si hay cobertura de ticks disponible. `window_config`/`grid_config`
    usan los defaults normativos (`WfaWindowConfig()`/`GridConfig()`) si el llamador
    no los fija explícitamente. `seed` es requerido (kw-only, sin default) y se
    propaga a `WfaResult` por homogeneidad de firma y reproducibilidad documental;
    `wfa.py` no consume ningún generador aleatorio (grid exhaustivo, sin muestreo):
    el determinismo total (R54) es estructural.

    Advertencia heredada del Candidato B (Rg-1): cada ventana/combinación instancia
    `CandidateB` en frío (`atr_value=None` al inicio), de modo que los primeros
    `atr_period` (14) días de cada ventana pueden operar sin componente ATR del
    stop; con `IS_WINDOW_TRADING_DAYS = 252` el sesgo es despreciable.
    """
    resolved_window_config = window_config if window_config is not None else WfaWindowConfig()
    resolved_grid_config = grid_config if grid_config is not None else GridConfig()

    days, row_span = _plan_and_validate_windows(
        frame, symbol, firm_profile, resolved_window_config, candidate_id=candidate_id
    )
    grid_config_hash = window_config_module._grid_config_hash(resolved_grid_config)
    full_dataset_hash = dataset_store.chunk_hash(frame)

    windows: list[WindowResult] = []
    for k, is_start, is_end, oos_end in _iter_window_bounds(len(days), resolved_window_config):
        is_days = days[is_start:is_end]
        oos_days = days[is_end:oos_end]
        frame_is = _slice_frame_by_days(frame, row_span, is_days)
        frame_oos = _slice_frame_by_days(frame, row_span, oos_days)
        dataset_hash_is = dataset_store.chunk_hash(frame_is)
        dataset_hash_oos = dataset_store.chunk_hash(frame_oos)

        window_result = _run_single_window(
            index=k,
            candidate_id=candidate_id,
            symbol=symbol,
            frame_is=frame_is,
            frame_oos=frame_oos,
            is_days=is_days,
            oos_days=oos_days,
            dataset_hash_is=dataset_hash_is,
            dataset_hash_oos=dataset_hash_oos,
            firm_profile=firm_profile,
            risk_profile=risk_profile,
            figure=figure,
            funnel_config=funnel_config,
            costs_config=costs_config,
            news_events=news_events,
            tick_store=tick_store,
            starting_balance=starting_balance,
            grid_config=resolved_grid_config,
            grid_config_hash=grid_config_hash,
        )
        windows.append(window_result)

    oos_ledger_cosido = _stitch_oos_ledgers(
        windows,
        candidate_id=candidate_id,
        symbol=symbol,
        firm_profile=firm_profile,
        risk_profile=risk_profile,
        dataset_hash=full_dataset_hash,
    )
    wfe = _compute_wfe(oos_ledger_cosido, windows)
    n_windows = len(windows)

    return WfaResult(
        candidate_id=candidate_id,
        symbol=symbol,
        config_version=CONFIG_VERSION,
        windows=windows,
        oos_ledger_cosido=oos_ledger_cosido,
        wfe=wfe,
        n_windows=n_windows,
        n_trials_signal_total=n_windows * _N_TRIALS_SIGNAL,
        n_trials_execution_total=n_windows * _N_TRIALS_EXECUTION,
        seed=seed,
    )
