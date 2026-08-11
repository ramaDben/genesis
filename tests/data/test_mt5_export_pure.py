"""Tests unitarios + property de las funciones/puertos puros de `genesis.data.mt5_export`."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from genesis.data.errors import GenesisDataError
from genesis.data.mt5_export import (
    AccountScopeError,
    ChunkWindow,
    Granularity,
    Mt5Terminal,
    _coerce_symbol_figure,
    backoff_delay,
    plan_chunks,
    resolve_symbol_alias,
)
from genesis.data.profile import SymbolAliases, load_firm_profile

pytestmark = pytest.mark.unit

_MODULE_PATH = Path(__file__).parents[2] / "src" / "genesis" / "data" / "mt5_export.py"


def test_mt5_export_module_has_no_top_level_metatrader5_import() -> None:
    """R2/R35: import perezoso — nunca `import MetaTrader5` a nivel de módulo."""
    lines = _MODULE_PATH.read_text(encoding="utf-8").splitlines()
    top_level_imports = [line for line in lines if line.startswith(("import ", "from "))]
    assert not any("MetaTrader5" in line for line in top_level_imports)


def test_account_scope_error_is_a_genesis_data_error() -> None:
    assert issubclass(AccountScopeError, GenesisDataError)


def test_mt5_terminal_protocol_has_required_methods() -> None:
    required = {
        "initialize",
        "shutdown",
        "last_error",
        "account_info",
        "symbols_get",
        "symbol_info",
        "copy_rates_range",
        "copy_ticks_range",
    }
    assert required.issubset(set(dir(Mt5Terminal)))


# --- plan_chunks -------------------------------------------------------------------


def test_plan_chunks_m1_splits_by_calendar_month() -> None:
    start = datetime(2024, 1, 15, tzinfo=UTC)
    end = datetime(2024, 3, 10, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert len(chunks) == 3
    assert chunks[0].start == start
    assert chunks[-1].end == end


def test_plan_chunks_ticks_splits_by_day() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.TICK)
    assert len(chunks) == 3


def test_plan_chunks_covers_range_without_gaps_or_overlaps() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 6, 30, tzinfo=UTC)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert chunks[0].start == start
    assert chunks[-1].end == end
    for prev, curr in pairwise(chunks):
        assert prev.end == curr.start


@given(
    start_offset_days=st.integers(min_value=0, max_value=400),
    span_days=st.integers(min_value=1, max_value=400),
)
def test_plan_chunks_property_covers_exact_range(start_offset_days: int, span_days: int) -> None:
    base = datetime(2023, 1, 1, tzinfo=UTC)
    start = base + timedelta(days=start_offset_days)
    end = start + timedelta(days=span_days)
    chunks = plan_chunks(start, end, Granularity.M1)
    assert chunks[0].start == start
    assert chunks[-1].end == end
    for prev, curr in pairwise(chunks):
        assert prev.end == curr.start


def test_plan_chunks_start_equals_end_returns_single_empty_window() -> None:
    moment = datetime(2024, 5, 1, tzinfo=UTC)
    chunks = plan_chunks(moment, moment, Granularity.M1)
    assert chunks == [ChunkWindow(start=moment, end=moment)]


# --- backoff_delay -------------------------------------------------------------------


def test_backoff_delay_is_monotonically_increasing() -> None:
    delays = [backoff_delay(attempt) for attempt in range(6)]
    for prev, curr in pairwise(delays):
        assert curr > prev


def test_backoff_delay_respects_cap() -> None:
    assert backoff_delay(100, cap=10.0) == 10.0


@given(attempt=st.integers(min_value=0, max_value=10))
def test_backoff_delay_never_exceeds_cap(attempt: int) -> None:
    assert backoff_delay(attempt, cap=30.0) <= 30.0


# --- resolve_symbol_alias --------------------------------------------------------------


def _nas100_aliases() -> Mapping[str, SymbolAliases]:
    return load_firm_profile().symbols


def test_resolve_symbol_alias_returns_expected_when_present() -> None:
    table = _nas100_aliases()
    resolved = resolve_symbol_alias("NAS100", ["US100", "US500"], table)
    assert resolved == "US100"


def test_resolve_symbol_alias_falls_back_to_documented_alias() -> None:
    table = _nas100_aliases()
    resolved = resolve_symbol_alias("NAS100", ["NAS100", "US500"], table)
    assert resolved == "NAS100"


def test_resolve_symbol_alias_fails_noisily_with_context_when_nothing_matches() -> None:
    table = _nas100_aliases()
    with pytest.raises(GenesisDataError, match="NAS100"):
        resolve_symbol_alias("NAS100", ["EURUSD", "GBPUSD"], table)


def test_resolve_symbol_alias_unknown_conventional_symbol_fails_noisily() -> None:
    table = _nas100_aliases()
    with pytest.raises(GenesisDataError):
        resolve_symbol_alias("XAUUSD", ["XAUUSD"], table)


def test_coerce_symbol_figure_lee_trade_tick_size() -> None:
    """A3 (H6): `_coerce_symbol_figure` lee `trade_tick_size` del SDK, no solo
    `trade_tick_value`."""
    raw = SimpleNamespace(
        trade_tick_value=0.0115435,
        trade_tick_size=0.01,
        volume_step=0.01,
        trade_stops_level=10,
        trade_freeze_level=5,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.3,
        swap_rollover3days=2,
    )
    figure = _coerce_symbol_figure("GER40", raw)
    assert figure.tick_value == 0.0115435
    assert figure.tick_size == 0.01
    assert figure.value_per_point == pytest.approx(1.15435)
