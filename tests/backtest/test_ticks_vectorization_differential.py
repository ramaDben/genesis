"""Guardas de regresión de la vectorización de `iter_ticks` e indexado `bisect` (Issue #24).

Refactor invariante (R92-R114): la vectorización por chunk (R92-R102) y el indexado
`bisect` de las ventanas por evento (R103-R105) **no cambian el comportamiento
observable**; los dos property tests de este archivo son oráculos de equivalencia
contra referencias de fuerza bruta ya existentes (`_tick_in_bar_window`, filtrado
escalar `_to_utc`), no tests de una feature nueva.
"""

from datetime import UTC, datetime

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from genesis.backtest.ticks import (
    TickRow,
    _bisect_window_bounds,
    _tick_in_bar_window,
)

pytestmark = pytest.mark.unit

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
