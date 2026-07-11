"""`Timeframe` + `BarAggregator` (T3.1, R97)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.strategy.candidate_a.smc.timeframe import AggregatedBar, BarAggregator, Timeframe
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)


def _bars(n: int) -> list:
    return [
        make_annotated_bar(
            _BASE + timedelta(minutes=i),
            close=100.0 + i,
            open_=100.0 + i - 0.5,
            high=100.0 + i + 1.0,
            low=100.0 + i - 1.0,
            tick_volume=10,
        )
        for i in range(n)
    ]


def test_bar_aggregator_emite_m15_solo_al_cerrar_minuto_14() -> None:
    aggregator = BarAggregator()
    bars = _bars(15)
    all_emitted: list[list[AggregatedBar]] = [aggregator.push(bar) for bar in bars]

    m15_emissions = [
        (i, [agg for agg in emitted if agg.timeframe == Timeframe.M15])
        for i, emitted in enumerate(all_emitted)
    ]
    non_empty = [(i, aggs) for i, aggs in m15_emissions if aggs]
    assert len(non_empty) == 1
    index, aggs = non_empty[0]
    assert index == 14  # minuto 14 (0-indexado) cierra la M15
    agg = aggs[0]
    assert agg.open == bars[0].open
    assert agg.close == bars[14].close
    assert agg.high == max(bar.high for bar in bars)
    assert agg.low == min(bar.low for bar in bars)
    assert agg.tick_volume == sum(bar.tick_volume for bar in bars)
    assert agg.open_time == bars[0].timestamp_utc
    assert agg.close_time == bars[14].timestamp_utc


def test_bar_aggregator_emite_h1_solo_al_cerrar_minuto_59() -> None:
    aggregator = BarAggregator()
    bars = _bars(60)
    all_emitted = [aggregator.push(bar) for bar in bars]

    h1_emissions = [
        (i, [agg for agg in emitted if agg.timeframe == Timeframe.H1])
        for i, emitted in enumerate(all_emitted)
    ]
    non_empty = [(i, aggs) for i, aggs in h1_emissions if aggs]
    assert len(non_empty) == 1
    index, aggs = non_empty[0]
    assert index == 59
    agg = aggs[0]
    assert agg.close == bars[59].close
    assert agg.open_time == bars[0].timestamp_utc


def test_bar_aggregator_nunca_emite_parcial_antes_del_ancla() -> None:
    aggregator = BarAggregator()
    bars = _bars(13)
    for bar in bars:
        emitted = aggregator.push(bar)
        assert not any(agg.timeframe == Timeframe.M15 for agg in emitted)


def test_bar_aggregator_dos_ventanas_m15_consecutivas() -> None:
    aggregator = BarAggregator()
    bars = _bars(30)
    all_emitted = [aggregator.push(bar) for bar in bars]
    m15_bars = [agg for emitted in all_emitted for agg in emitted if agg.timeframe == Timeframe.M15]
    assert len(m15_bars) == 2
    assert m15_bars[0].close_time == bars[14].timestamp_utc
    assert m15_bars[1].close_time == bars[29].timestamp_utc
    assert m15_bars[1].open_time == bars[15].timestamp_utc
