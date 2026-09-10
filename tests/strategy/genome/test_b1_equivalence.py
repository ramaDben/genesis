"""Golden Test de equivalencia exacta entre Candidate B y Candidate B.1 compilado (T6, A5)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from genesis.data.profile import load_firm_profile
from genesis.data.store import AnnotatedBar, iter_bars
from genesis.data.symbols import SymbolFigure
from genesis.strategy.factories import candidate_b_factory
from genesis.strategy.genome.compiler import compile_genome


@pytest.fixture
def us500_figure() -> SymbolFigure:
    return SymbolFigure(
        symbol="US500",
        tick_value=1.0,
        tick_size=0.01,
        volume_step=0.01,
        stops_level=0,
        freeze_level=0,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.5,
        swap_rollover_day=3,
    )


def _generate_deterministic_m1_bars(
    n_days: int = 15,
    bars_per_day: int = 350,
) -> list[AnnotatedBar]:
    """Genera serie determinista de barras M1 con rupturas LONG y SHORT controladas."""
    bars: list[AnnotatedBar] = []
    base_price = 5000.0

    for d in range(n_days):
        day_date = date(2024, 2, 1 + d)
        session_open = datetime(2024, 2, 1 + d, 14, 30, tzinfo=UTC)
        session_close = datetime(2024, 2, 1 + d, 21, 0, tzinfo=UTC)

        # Alternamos días LONG (rompe arriba) y SHORT (rompe abajo)
        is_long_day = d % 2 == 0
        direction_tilt = 0.5 if is_long_day else -0.5

        range_high = base_price + 2.0
        range_low = base_price - 2.0

        for m in range(bars_per_day):
            bar_time = session_open + timedelta(minutes=m)

            if m < 30:
                # Período de apertura (30 min)
                open_ = base_price + (m * 0.02 * direction_tilt)
                close_ = base_price + ((m + 1) * 0.02 * direction_tilt)
                high_ = max(open_, close_) + 0.1
                low_ = min(open_, close_) - 0.1
            elif m == 35:
                # Ruptura alineada con el momentum del día
                if is_long_day:
                    open_ = range_high + 0.5
                    close_ = range_high + 3.0
                    high_ = close_ + 0.5
                    low_ = open_ - 0.1
                else:
                    open_ = range_low - 0.5
                    close_ = range_low - 3.0
                    high_ = open_ + 0.1
                    low_ = close_ - 0.5
            else:
                # Deriva post-ruptura
                open_ = base_price + direction_tilt * 3.0
                close_ = open_ + 0.05
                high_ = close_ + 0.1
                low_ = open_ - 0.1

            bars.append(
                AnnotatedBar(
                    timestamp_utc=bar_time,
                    open=open_,
                    high=high_,
                    low=low_,
                    close=close_,
                    tick_volume=100,
                    trading_day=day_date,
                    in_session=True,
                    session_open_utc=session_open,
                    session_close_utc=session_close,
                )
            )

    return bars


def test_b_vs_b1_synthetic_5000_bars_equivalence(us500_figure: SymbolFigure):
    """Criterio A5: 100% de equivalencia en más de 5.000 barras sintéticas deterministas."""
    spec_path = Path("candidates/specs/candidate_b1_orb.yaml")
    b1_factory = compile_genome(spec_path)

    params = {
        "n_minutes": 30.0,
        "atr_stop_frac": 0.5,
        "risk_pct": 0.01,
        "tp_rr_multiple": 3.0,
        "rvol_threshold": 0.0,
    }

    cand_b = candidate_b_factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params=params,
    )
    cand_b1 = b1_factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params=params,
    )

    bars = _generate_deterministic_m1_bars(n_days=15, bars_per_day=350)
    assert len(bars) >= 5000

    signals_seen = 0
    for bar in bars:
        intents_b = cand_b.on_bar(bar)
        intents_b1 = cand_b1.on_bar(bar)

        msg = f"Discrepancia de intenciones en {bar.timestamp_utc}"
        assert len(intents_b) == len(intents_b1), msg

        if intents_b:
            signals_seen += 1
            ib = intents_b[0]
            ib1 = intents_b1[0]

            assert ib.direction == ib1.direction
            assert ib.sizing_hint == pytest.approx(ib1.sizing_hint, rel=1e-7)

            levels_b = cast(Any, cand_b).risk_levels(ib)
            levels_b1 = cast(Any, cand_b1).risk_levels(ib1)

            assert levels_b[0] == pytest.approx(levels_b1[0], rel=1e-7), "Stop loss discrepa"
            assert levels_b[1] == pytest.approx(levels_b1[1], rel=1e-7), "Take profit discrepa"

    assert signals_seen > 0, "El test sintético debe haber gatillado señales de ruptura"


def test_b_vs_b1_real_us500_data_equivalence(us500_figure: SymbolFigure):
    """Criterio A5: 100% de equivalencia matemática sobre 5.000 barras reales de US500."""
    csv_path = Path("data/csv/US500.csv")
    if not csv_path.is_file():
        pytest.skip("data/csv/US500.csv no encontrado")

    spec_path = Path("candidates/specs/candidate_b1_orb.yaml")
    b1_factory = compile_genome(spec_path)

    params = {
        "n_minutes": 30.0,
        "atr_stop_frac": 0.5,
        "risk_pct": 0.01,
        "tp_rr_multiple": 3.0,
        "rvol_threshold": 0.0,
    }

    cand_b = candidate_b_factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params=params,
    )
    cand_b1 = b1_factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params=params,
    )

    firm_profile = load_firm_profile()
    raw_df = pd.read_csv(csv_path, nrows=5000)
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"], utc=True)
    bars = list(iter_bars(raw_df, "US500", firm_profile))
    assert len(bars) == 5000

    signals_seen = 0
    for bar in bars:
        intents_b = cand_b.on_bar(bar)
        intents_b1 = cand_b1.on_bar(bar)

        assert len(intents_b) == len(intents_b1), f"Discrepancia en {bar.timestamp_utc}"

        if intents_b:
            signals_seen += 1
            ib = intents_b[0]
            ib1 = intents_b1[0]

            assert ib.direction == ib1.direction
            assert ib.sizing_hint == pytest.approx(ib1.sizing_hint, rel=1e-7)

            levels_b = cast(Any, cand_b).risk_levels(ib)
            levels_b1 = cast(Any, cand_b1).risk_levels(ib1)

            assert levels_b[0] == pytest.approx(levels_b1[0], rel=1e-7)
            assert levels_b[1] == pytest.approx(levels_b1[1], rel=1e-7)

    assert signals_seen > 0, "El test con datos reales debe registrar señales operables"
