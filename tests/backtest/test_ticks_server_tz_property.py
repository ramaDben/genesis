"""Property test forward-only de `iter_ticks` con `server_tz != UTC` (R80).

Para cualquier instante real `T` y cualquier huso horario de servidor (con DST y
offsets de signo opuesto), un tick persistido con su wall-clock de servidor
correspondiente a `T` es reinterpretado por `iter_ticks` con `timestamp_utc == T`
exacto, y cae en la ventana de cobertura `(T-60s, T]` del evento anclado en `T`
(mismo criterio único de `_tick_in_bar_window`, RI-G5/ADR-G8). `@example` pinneados
cubren: (i) el borde de día calendario del servidor a través de la medianoche UTC
(offset positivo y negativo); (ii) spring-forward y (iii) fall-back de cada huso
(`Europe/Athens`, `America/New_York`, `Australia/Sydney`).

Para instantes genéricos que caen en la hora local ambigua del retroceso de
horario (`fold=1`, 2.ª ocurrencia del wall-clock repetido), se descarta el ejemplo
(`hypothesis.assume`): la reinterpretación vía wall-clock naive sin `fold` (R28/R40,
ADR-21-1) es la MISMA limitación inherente de `store._to_utc` (dato real MT5 tampoco
distingue la ocurrencia) — no es un defecto introducido por este Change.
"""

import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st

from genesis.backtest.ticks import _tick_in_bar_window, iter_ticks
from genesis.data.profile import load_firm_profile
from genesis.data.store import RawParquetStore
from tests.backtest.fakes import build_server_local_tick_chunk

pytestmark = pytest.mark.unit

_SYMBOL = "US500"
_SERVER_TZS = ("Europe/Athens", "America/New_York", "Australia/Sydney")

_instant_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2029, 12, 31, 23, 59, 59),
).map(lambda naive: naive.replace(tzinfo=UTC))


@pytest.mark.timeout(180)
@given(server_tz_name=st.sampled_from(_SERVER_TZS), instant_utc=_instant_strategy)
@example(  # (i) borde de día de servidor a través de medianoche UTC, offset positivo (Athens).
    server_tz_name="Europe/Athens",
    instant_utc=datetime(2026, 6, 25, 22, 0, 0, tzinfo=UTC),
)
@example(  # (i) borde de día de servidor a través de medianoche UTC, offset negativo (NY).
    server_tz_name="America/New_York",
    instant_utc=datetime(2024, 1, 2, 2, 0, 0, tzinfo=UTC),
)
@example(  # (ii) spring-forward Europe/Athens (transición 2024-03-31 01:00 UTC).
    server_tz_name="Europe/Athens",
    instant_utc=datetime(2024, 3, 31, 0, 30, 0, tzinfo=UTC),
)
@example(  # (iii) fall-back Europe/Athens (transición 2024-10-27 01:00 UTC).
    server_tz_name="Europe/Athens",
    instant_utc=datetime(2024, 10, 27, 0, 30, 0, tzinfo=UTC),
)
@example(  # (ii) spring-forward America/New_York (transición 2024-03-10 07:00 UTC).
    server_tz_name="America/New_York",
    instant_utc=datetime(2024, 3, 10, 6, 30, 0, tzinfo=UTC),
)
@example(  # (iii) fall-back America/New_York (transición 2024-11-03 06:00 UTC).
    server_tz_name="America/New_York",
    instant_utc=datetime(2024, 11, 3, 5, 30, 0, tzinfo=UTC),
)
@example(  # (ii) spring-forward Australia/Sydney (transición 2024-10-05 16:00 UTC).
    server_tz_name="Australia/Sydney",
    instant_utc=datetime(2024, 10, 5, 15, 30, 0, tzinfo=UTC),
)
@example(  # (iii) fall-back Australia/Sydney (transición 2024-04-06 16:00 UTC).
    server_tz_name="Australia/Sydney",
    instant_utc=datetime(2024, 4, 6, 15, 30, 0, tzinfo=UTC),
)
@settings(max_examples=1000, deadline=None)
def test_iter_ticks_reinterpreta_wall_clock_server_tz_no_utc(
    server_tz_name: str, instant_utc: datetime
) -> None:
    """R80: `iter_ticks` emite `timestamp_utc == T` para cualquier `server_tz`/instante."""
    server_tz = ZoneInfo(server_tz_name)
    local = instant_utc.astimezone(server_tz)
    assume(local.fold == 0)  # excluye la 2.ª ocurrencia ambigua del retroceso de horario.
    wall_clock_naive = local.replace(tzinfo=None)
    server_date = wall_clock_naive.date()

    # Directorio temporal propio por ejemplo (no el fixture `tmp_path`, de scope de
    # función: `hypothesis` reutiliza la misma invocación de test para cada ejemplo).
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = RawParquetStore(Path(tmp_dir))
        build_server_local_tick_chunk(
            store, _SYMBOL, server_date, [(wall_clock_naive, 100.0, 100.1, 100.05)]
        )
        profile = replace(load_firm_profile(), server_tz=server_tz_name)

        ticks = list(iter_ticks(store, _SYMBOL, instant_utc.date(), profile))

    assert [tick.timestamp_utc for tick in ticks] == [instant_utc]
    assert _tick_in_bar_window(ticks[0].timestamp_utc, instant_utc)
