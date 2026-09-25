"""Guardas de regresión de la vectorización de `iter_ticks` e indexado `bisect` (Issue #24).

Refactor invariante (R92-R114): la vectorización por chunk (R92-R102) y el indexado
`bisect` de las ventanas por evento (R103-R105) **no cambian el comportamiento
observable**; los dos property tests de este archivo son oráculos de equivalencia
contra referencias de fuerza bruta ya existentes (`_tick_in_bar_window`, filtrado
escalar `_to_utc`), no tests de una feature nueva.
"""

import tempfile
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from genesis.backtest.ticks import (
    TickRow,
    _bisect_window_bounds,
    _candidate_server_dates,
    _day_window,
    _has_dst_transition,
    _tick_in_bar_window,
    _to_utc,
    iter_ticks,
)
from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import Granularity, RawParquetStore
from tests.backtest.fakes import build_server_local_tick_chunk

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_SERVER_TZS = ("Europe/Athens", "America/New_York")

_instant_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2029, 12, 31, 23, 59, 59),
).map(lambda naive: naive.replace(tzinfo=UTC))


def _make_tick(timestamp_utc: datetime) -> TickRow:
    """Construye un `TickRow` sintético con precios fijos (irrelevantes para el borde)."""
    return TickRow(timestamp_utc=timestamp_utc, bid=100.0, ask=100.1, last=100.05)


@given(
    timestamps=st.lists(_instant_strategy, max_size=25),
    bar_timestamp=_instant_strategy,
)
@example(timestamps=[], bar_timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC))
@example(
    # Exactamente en bar_timestamp - 60s: EXCLUIDO (borde estricto en el extremo bajo).
    timestamps=[datetime(2024, 1, 2, 11, 59, 0, tzinfo=UTC)],
    bar_timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
)
@example(
    # Exactamente en bar_timestamp: INCLUIDO (borde cerrado en el extremo alto).
    timestamps=[datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)],
    bar_timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
)
@example(
    # Todos los ticks caen en la ventana (T-60s, T].
    timestamps=[
        datetime(2024, 1, 2, 11, 59, 30, tzinfo=UTC),
        datetime(2024, 1, 2, 11, 59, 45, tzinfo=UTC),
        datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
    ],
    bar_timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
)
@example(
    # Ningún tick cae en la ventana.
    timestamps=[
        datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 13, 0, 0, tzinfo=UTC),
    ],
    bar_timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
)
@settings(max_examples=200, deadline=None)
def test_bisect_window_bounds_equivale_al_filtrado_lineal(
    timestamps: list[datetime], bar_timestamp: datetime
) -> None:
    """R103/R104/R105/R114: `_bisect_window_bounds` == filtrado lineal con `_tick_in_bar_window`.

    `_tick_in_bar_window` es el oráculo del borde `(T-60s, T]` (ADR-24-7); este test
    fija que el índice `bisect` produce exactamente el mismo subconjunto (y en el
    mismo orden, dado `day_ticks` ascendente) que el filtrado lineal de referencia, y
    que `start < end` equivale a "existe al menos un tick en la ventana" (condición
    (b) de `has_sufficient_tick_coverage`).
    """
    day_ticks = [_make_tick(ts) for ts in sorted(timestamps)]
    ref = [tick for tick in day_ticks if _tick_in_bar_window(tick.timestamp_utc, bar_timestamp)]

    start, end = _bisect_window_bounds(day_ticks, bar_timestamp)

    assert list(day_ticks[start:end]) == ref
    assert (start < end) == bool(ref)


# --- Test 2 (R113): iter_ticks (híbrida) == referencia escalar `_to_utc` fila a fila ---

# `entries`: lista de `(day_offset, wall_clock local, precio base)`. `day_offset` in
# {0, 1} agrupa cada tick en el chunk físico del servidor `base_date + day_offset`
# días (permite ejercitar tanto un único chunk como el spillover D/D+1 de R81).
_ENTRY_STRATEGY = st.tuples(
    st.integers(min_value=0, max_value=1),
    st.times(),
    st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)

# Times repartidos a lo largo del día completo: los extremos (00:00 / 23:59:59)
# quedan a ambos lados de cualquier hora de transición DST real (siempre entre
# 01:00-04:00 locales), de modo que sirven tanto para fechas sin transición como
# para las de spring-forward/fall-back.
_SPREAD_DAY_ENTRIES: list[tuple[int, time, float]] = [
    (0, time(0, 0, 0), 100.0),
    (0, time(6, 0, 0), 101.0),
    (0, time(12, 0, 0), 102.0),
    (0, time(18, 0, 0), 103.0),
    (0, time(23, 59, 59), 104.0),
]
_SPILLOVER_ENTRIES: list[tuple[int, time, float]] = [
    (0, time(23, 0, 0), 100.0),  # wall-clock 23:00 día D (golden R81 de #21).
    (1, time(0, 30, 0), 101.0),  # wall-clock 00:30 día D+1 (mismo trading_day UTC).
]


def _scalar_iter(
    store: RawParquetStore, symbol: str, trading_day: date, profile: FirmProfile
) -> list[TickRow]:
    """Referencia escalar de `iter_ticks` (bucle sin optimizar, pre-#24): `_to_utc` fila a fila.

    Réplica de la lógica pre-vectorización de este Change (mismo criterio de
    filtro/orden que la producción, `itertuples` en vez de `iterrows` — diferencia
    irrelevante para el resultado). Oráculo de la reescritura híbrida de T4: debe
    permanecer verde contra la implementación vectorizada final, no solo contra la
    baseline escalar de T2/T3.
    """
    window = _day_window(trading_day)
    server_tz = ZoneInfo(profile.server_tz)
    rows: list[TickRow] = []
    for server_date in _candidate_server_dates(window, server_tz):
        chunk_window = _day_window(server_date)
        if not store.has_chunk(symbol, Granularity.TICK, chunk_window):
            continue
        frame = store.read_chunk(symbol, Granularity.TICK, chunk_window)
        for tick in frame.itertuples(index=False):
            # `itertuples` retorna namedtuples reales en runtime; el stub de pandas los
            # tipa como `tuple[Any, ...]` genérico (falso positivo conocido de ty).
            timestamp_utc = _to_utc(tick.timestamp, server_tz)  # ty: ignore[unresolved-attribute]
            if window.start <= timestamp_utc < window.end:
                rows.append(
                    TickRow(
                        timestamp_utc=timestamp_utc,
                        bid=float(tick.bid),  # ty: ignore[unresolved-attribute]
                        ask=float(tick.ask),  # ty: ignore[unresolved-attribute]
                        last=float(tick.last),  # ty: ignore[unresolved-attribute]
                    )
                )
    rows.sort(key=lambda tick: tick.timestamp_utc)
    return rows


@given(
    server_tz_name=st.sampled_from(_SERVER_TZS),
    base_date=st.dates(min_value=date(2020, 1, 2), max_value=date(2029, 12, 30)),
    entries=st.lists(_ENTRY_STRATEGY, min_size=1, max_size=12),
)
@example(  # Sin transición DST: 2024-01-02 (Europe/Athens), mismo valor que test_ticks.py.
    server_tz_name="Europe/Athens",
    base_date=date(2024, 1, 2),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Sin transición DST: 2024-01-02 (America/New_York).
    server_tz_name="America/New_York",
    base_date=date(2024, 1, 2),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Spring-forward Europe/Athens: 2024-03-31.
    server_tz_name="Europe/Athens",
    base_date=date(2024, 3, 31),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Spring-forward America/New_York: 2024-03-10.
    server_tz_name="America/New_York",
    base_date=date(2024, 3, 10),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Fall-back Europe/Athens: 2024-10-27.
    server_tz_name="Europe/Athens",
    base_date=date(2024, 10, 27),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Fall-back America/New_York: 2024-11-03.
    server_tz_name="America/New_York",
    base_date=date(2024, 11, 3),
    entries=_SPREAD_DAY_ENTRIES,
)
@example(  # Multi-chunk spillover D/D+1: 2026-06-26 -> 2026-06-27 (Athens, golden R81 de #21).
    server_tz_name="Europe/Athens",
    base_date=date(2026, 6, 26),
    entries=_SPILLOVER_ENTRIES,
)
@settings(max_examples=200, deadline=None)
def test_iter_ticks_vectorizado_equivale_a_escalar(
    server_tz_name: str, base_date: date, entries: list[tuple[int, time, float]]
) -> None:
    """R92-R102/R113: `iter_ticks` == referencia escalar `_to_utc` fila a fila.

    Guarda de regresión (no RED genuino): contra el baseline escalar (T2, pre-T4) la
    referencia es trivialmente igual a `iter_ticks` (misma implementación); tras la
    reescritura híbrida de T4 sigue verde únicamente si la ruta vectorizada +
    fallback DST preservan exactamente el mismo resultado, elemento a elemento
    (orden + 4 campos, incluido `timestamp_utc`).

    Belt-and-suspenders (diferido de T3, R94): por cada chunk físico (agrupado por
    `day_offset`), `_has_dst_transition` sobre los extremos del chunk debe coincidir
    con el chequeo de fuerza bruta de si *algún par* de instantes del chunk tiene
    `utcoffset()` distinto (verdadero bajo Rg-12: a lo sumo una transición por chunk).
    """
    groups: dict[int, list[tuple[int, time, float]]] = {}
    for entry in entries:
        day_offset = entry[0]
        groups.setdefault(day_offset, []).append(entry)

    server_tz = ZoneInfo(server_tz_name)
    for day_offset, group_entries in groups.items():
        server_date = base_date + timedelta(days=day_offset)
        naive_times = [
            datetime.combine(server_date, local_time) for _, local_time, _ in group_entries
        ]
        naive_min, naive_max = min(naive_times), max(naive_times)
        observed_offsets = {t.replace(tzinfo=server_tz).utcoffset() for t in naive_times}
        assert _has_dst_transition(naive_min, naive_max, server_tz) == (len(observed_offsets) > 1)

    profile = replace(load_firm_profile(), server_tz=server_tz_name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        store = RawParquetStore(Path(tmp_dir))
        for day_offset, group_entries in groups.items():
            server_date = base_date + timedelta(days=day_offset)
            rows = [
                (datetime.combine(server_date, local_time), price, price + 0.1, price + 0.05)
                for _, local_time, price in group_entries
            ]
            build_server_local_tick_chunk(store, _SYMBOL, server_date, rows)

        actual = list(iter_ticks(store, _SYMBOL, base_date, profile))
        expected = _scalar_iter(store, _SYMBOL, base_date, profile)

    assert actual == expected
