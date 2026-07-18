"""Fakes deterministas reutilizables para la suite `tests/backtest/` (R51).

Patrón `tests/strategy/fakes.py` / `tests/data/fakes.py`: sin lógica de trading real,
sin I/O de red. `FakeRiskCandidate` implementa `StrategyCandidate` **y**
`RiskLevelsProvider` (ADR-G3); `FakeCandidateNoRisk` implementa solo
`StrategyCandidate`, para ejercitar el requisito duro R21.
"""

from collections.abc import Callable, Sequence
from datetime import date, datetime

import pandas as pd

from genesis.backtest.ticks import TickRow, _day_window
from genesis.data.metadata import ArtifactMetadata
from genesis.data.mt5_export import Granularity, RawParquetStore
from genesis.data.store import AnnotatedBar
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent

_DEFAULT_ON_BAR: Callable[[AnnotatedBar], list[EntryIntent]] = lambda bar: []  # noqa: E731


class FakeRiskCandidate:
    """Candidato fake que implementa `StrategyCandidate` y `RiskLevelsProvider` (R51).

    `on_bar` es determinista: emite un único `EntryIntent` la primera vez que
    `bar.close` cruza `entry_threshold` (si se define); `risk_levels` devuelve
    siempre el par `(stop_loss, take_profit)` fijo pasado al constructor. Inyecta
    `on_bar_fn` para un comportamiento totalmente controlado por el test.
    """

    def __init__(
        self,
        candidate_id: str = "B",
        *,
        entry_threshold: float | None = None,
        direction: Direction = Direction.LONG,
        sizing_hint: float = 0.1,
        stop_loss: float = 90.0,
        take_profit: float = 120.0,
        on_bar_fn: Callable[[AnnotatedBar], list[EntryIntent]] | None = None,
    ) -> None:
        self.candidate_id = candidate_id
        self._entry_threshold = entry_threshold
        self._direction = direction
        self._sizing_hint = sizing_hint
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._on_bar_fn = on_bar_fn
        self._fired = False
        self.on_bar_calls: list[AnnotatedBar] = []
        self.risk_levels_calls: list[EntryIntent] = []

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        self.on_bar_calls.append(bar)
        if self._on_bar_fn is not None:
            return self._on_bar_fn(bar)
        if self._entry_threshold is None or self._fired or bar.close < self._entry_threshold:
            return []
        self._fired = True
        return [
            EntryIntent(
                direction=self._direction,
                sizing_hint=self._sizing_hint,
                candidate_id=self.candidate_id,
                config_version=CONFIG_VERSION,
            )
        ]

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float]:
        self.risk_levels_calls.append(intent)
        return (self._stop_loss, self._take_profit)


class FakeCandidateNoRisk:
    """Candidato que implementa solo `StrategyCandidate`, sin `risk_levels` (R21)."""

    def __init__(self, candidate_id: str = "NoRisk") -> None:
        self.candidate_id = candidate_id
        self.on_bar_calls: list[AnnotatedBar] = []

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        self.on_bar_calls.append(bar)
        return []


def build_tick_chunk(
    store: RawParquetStore,
    symbol: str,
    trading_day: date,
    ticks: Sequence[TickRow],
) -> None:
    """Escribe un chunk de ticks sintético en `store` vía `RawParquetStore.write_chunk` (R51).

    Construye el `ArtifactMetadata` requerido por `write_chunk` (`genesis.data.metadata`,
    H4) con valores de prueba deterministas; el rango temporal del chunk es el mismo
    `_day_window(trading_day)` que consume `iter_ticks`/`has_sufficient_tick_coverage`.
    """
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([tick.timestamp_utc for tick in ticks], utc=True),
            "bid": [tick.bid for tick in ticks],
            "ask": [tick.ask for tick in ticks],
            "last": [tick.last for tick in ticks],
        }
    )
    window = _day_window(trading_day)
    metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash="test-firm-profile-hash",
        time_range=(window.start, window.end),
        git_commit="test-git-commit",
    )
    store.write_chunk(frame, symbol, Granularity.TICK, window, metadata)


def build_server_local_tick_chunk(
    store: RawParquetStore,
    symbol: str,
    server_date: date,
    rows: Sequence[tuple[datetime, float, float, float]],
) -> None:
    """Escribe un chunk de ticks con timestamps NAIVE de reloj de servidor (ADR-21-7).

    Réplica del Parquet crudo mal etiquetado que produce `mt5_export.py`:
    `RawParquetStore.write_chunk -> _normalize_frame` ejecuta
    `pd.to_datetime(col, utc=True)`, que sobre timestamps *naive* **localiza a UTC
    preservando el wall-clock** (p.ej. `23:49` naive queda `23:49+00:00`) — exactamente
    el comportamiento del SDK MT5 (reloj de servidor rotulado UTC), sin necesidad de
    tocar `mt5_export.py`. El fichero se nombra por `server_date` (día calendario del
    **servidor**), no por el día UTC, igual que en producción. `rows` es una secuencia
    de `(wall_clock_naive, bid, ask, last)`. Complementa `build_tick_chunk` (semántica
    UTC-real, ruta de regresión `server_tz="UTC"`), que se conserva intacto.
    """
    frame = pd.DataFrame(
        {
            "timestamp": [wall_clock for wall_clock, *_ in rows],
            "bid": [bid for _, bid, _, _ in rows],
            "ask": [ask for _, _, ask, _ in rows],
            "last": [last for _, _, _, last in rows],
        }
    )
    window = _day_window(server_date)
    metadata = ArtifactMetadata(
        config_version=CONFIG_VERSION,
        dataset_hash=store.chunk_hash(frame),
        firm_profile_hash="test-firm-profile-hash",
        time_range=(window.start, window.end),
        git_commit="test-git-commit",
    )
    store.write_chunk(frame, symbol, Granularity.TICK, window, metadata)
