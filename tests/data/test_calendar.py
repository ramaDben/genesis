"""Tests unitarios de `genesis.data.calendar` (puerto + normalización pura de noticias)."""

from datetime import UTC, datetime

import pytest

from genesis.data.calendar import (
    CalendarError,
    CsvCalendarSource,
    EconomicCalendarSource,
    EconomicEvent,
    ImpactLevel,
    news_windows,
)
from genesis.data.profile import load_firm_profile
from tests.data.fakes import FakeEconomicCalendarSource

pytestmark = pytest.mark.unit


def test_economic_calendar_source_is_a_runtime_protocol() -> None:
    fake = FakeEconomicCalendarSource()
    assert isinstance(fake, EconomicCalendarSource)


def test_news_windows_high_impact_event_generates_window() -> None:
    profile = load_firm_profile()
    event_time = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    event = EconomicEvent(
        timestamp_utc=event_time, currency="USD", impact=ImpactLevel.HIGH, title="NFP"
    )
    windows = news_windows([event], "US500", profile)
    assert len(windows) == 1
    start, end = windows[0]
    assert start == event_time - profile.news_bracket_before
    assert end == event_time + profile.news_bracket_after


def test_news_windows_low_impact_event_generates_no_window() -> None:
    profile = load_firm_profile()
    event = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 14, 30, tzinfo=UTC),
        currency="USD",
        impact=ImpactLevel.LOW,
        title="Consumer Sentiment",
    )
    assert news_windows([event], "US500", profile) == []


def test_news_windows_high_impact_wrong_currency_generates_no_window() -> None:
    profile = load_firm_profile()
    event = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 8, 0, tzinfo=UTC),
        currency="EUR",
        impact=ImpactLevel.HIGH,
        title="ECB Rate Decision",
    )
    # EUR no afecta a US500 (solo a GER40).
    assert news_windows([event], "US500", profile) == []


def test_news_windows_mixed_events_only_high_generates_window() -> None:
    profile = load_firm_profile()
    high = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 14, 30, tzinfo=UTC),
        currency="USD",
        impact=ImpactLevel.HIGH,
        title="NFP",
    )
    low = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 16, 0, tzinfo=UTC),
        currency="USD",
        impact=ImpactLevel.LOW,
        title="Ruido",
    )
    windows = news_windows([high, low], "US500", profile)
    assert len(windows) == 1


def test_news_windows_ger40_uses_eur_currency() -> None:
    profile = load_firm_profile()
    event = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 8, 0, tzinfo=UTC),
        currency="EUR",
        impact=ImpactLevel.HIGH,
        title="ECB Rate Decision",
    )
    windows = news_windows([event], "GER40", profile)
    assert len(windows) == 1


def test_news_windows_is_pure_no_io() -> None:
    """news_windows no debe requerir ninguna fuente inyectada, solo la lista ya obtenida."""
    profile = load_firm_profile()
    assert news_windows([], "US500", profile) == []


def test_fetch_events_error_propagates_as_calendar_error() -> None:
    source = FakeEconomicCalendarSource(error=CalendarError("fuente caída"))
    with pytest.raises(CalendarError):
        source.fetch_events(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC))


def test_news_windows_naive_timestamp_raises_calendar_error() -> None:
    profile = load_firm_profile()
    naive_event = EconomicEvent(
        timestamp_utc=datetime(2024, 3, 1, 14, 30),  # naive intencional para probar CalendarError
        currency="USD",
        impact=ImpactLevel.HIGH,
        title="NFP",
    )
    with pytest.raises(CalendarError):
        news_windows([naive_event], "US500", profile)


def test_csv_calendar_source_reads_events_in_range(tmp_path) -> None:
    csv_path = tmp_path / "calendario.csv"
    csv_path.write_text(
        "timestamp_utc,currency,impact,title\n"
        "2024-03-01T14:30:00+00:00,USD,high,NFP\n"
        "2024-03-05T08:00:00+00:00,EUR,high,ECB Rate Decision\n",
        encoding="utf-8",
    )
    source = CsvCalendarSource(csv_path)
    events = source.fetch_events(datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 2, tzinfo=UTC))
    assert len(events) == 1
    assert events[0].title == "NFP"
    assert events[0].impact == ImpactLevel.HIGH


def test_csv_calendar_source_missing_file_raises_calendar_error(tmp_path) -> None:
    source = CsvCalendarSource(tmp_path / "no_existe.csv")
    with pytest.raises(CalendarError):
        source.fetch_events(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC))


def test_csv_calendar_source_invalid_row_raises_calendar_error(tmp_path) -> None:
    csv_path = tmp_path / "calendario.csv"
    csv_path.write_text(
        "timestamp_utc,currency,impact,title\nno-es-una-fecha,USD,high,NFP\n", encoding="utf-8"
    )
    source = CsvCalendarSource(csv_path)
    with pytest.raises(CalendarError):
        source.fetch_events(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
