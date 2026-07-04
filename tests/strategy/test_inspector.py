"""Tests unitarios del embudo de viabilidad compartido `inspector.py` (R13-R21)."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from genesis.data.calendar import EconomicEvent, ImpactLevel
from genesis.data.profile import load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.errors import InspectorConfigError
from genesis.strategy.inspector import (
    AUTHORIZED,
    InspectorFunnelConfig,
    InspectorVerdict,
    RejectionReason,
    inspect,
    load_inspector_funnel_config,
)

pytestmark = pytest.mark.unit

_SYMBOL = "US500"


def _figure(volume_step: float = 0.01) -> SymbolFigure:
    return SymbolFigure(
        symbol=_SYMBOL,
        tick_value=1.0,
        volume_step=volume_step,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-1.0,
        swap_short=-1.0,
        swap_rollover_day=3,
    )


def _config(
    min_rr: float = 2.0, min_lot: float = 0.01, max_lot: float = 50.0
) -> InspectorFunnelConfig:
    return InspectorFunnelConfig(min_rr=min_rr, min_lot=min_lot, max_lot=max_lot)


def _intent(sizing_hint: float = 0.1) -> EntryIntent:
    return EntryIntent(
        direction=Direction.LONG,
        sizing_hint=sizing_hint,
        candidate_id="Z",
        config_version=CONFIG_VERSION,
    )


def test_inspect_authorized_cuando_nada_dispara() -> None:
    profile = load_firm_profile()
    verdict = inspect(
        _intent(),
        symbol=_SYMBOL,
        intent_time=datetime(2024, 3, 1, 12, 0, tzinfo=UTC),
        proposed_rr=3.0,
        figure=_figure(),
        firm_profile=profile,
        news_events=(),
        config=_config(),
    )
    assert verdict == AUTHORIZED
    assert verdict.authorized is True
    assert verdict.rejection_reason is None


def test_inspect_news_window_rechaza() -> None:
    profile = load_firm_profile()
    event_time = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    event = EconomicEvent(
        timestamp_utc=event_time, currency="USD", impact=ImpactLevel.HIGH, title="NFP"
    )
    verdict = inspect(
        _intent(),
        symbol=_SYMBOL,
        intent_time=event_time,
        proposed_rr=3.0,
        figure=_figure(),
        firm_profile=profile,
        news_events=[event],
        config=_config(),
    )
    assert verdict.authorized is False
    assert verdict.rejection_reason == RejectionReason.NEWS_WINDOW


def test_inspect_insufficient_rr_rechaza_fuera_de_ventana() -> None:
    profile = load_firm_profile()
    verdict = inspect(
        _intent(),
        symbol=_SYMBOL,
        intent_time=datetime(2024, 3, 1, 12, 0, tzinfo=UTC),
        proposed_rr=1.0,
        figure=_figure(),
        firm_profile=profile,
        news_events=(),
        config=_config(min_rr=2.0),
    )
    assert verdict.authorized is False
    assert verdict.rejection_reason == RejectionReason.INSUFFICIENT_RR


def test_inspect_lot_size_out_of_bounds_por_debajo_del_minimo() -> None:
    profile = load_firm_profile()
    verdict = inspect(
        _intent(sizing_hint=0.001),
        symbol=_SYMBOL,
        intent_time=datetime(2024, 3, 1, 12, 0, tzinfo=UTC),
        proposed_rr=3.0,
        figure=_figure(),
        firm_profile=profile,
        news_events=(),
        config=_config(min_lot=0.01, max_lot=50.0),
    )
    assert verdict.authorized is False
    assert verdict.rejection_reason == RejectionReason.LOT_SIZE_OUT_OF_BOUNDS


def test_inspect_lot_size_out_of_bounds_no_multiplo_de_volume_step() -> None:
    profile = load_firm_profile()
    verdict = inspect(
        _intent(sizing_hint=0.015),
        symbol=_SYMBOL,
        intent_time=datetime(2024, 3, 1, 12, 0, tzinfo=UTC),
        proposed_rr=3.0,
        figure=_figure(volume_step=0.01),
        firm_profile=profile,
        news_events=(),
        config=_config(),
    )
    assert verdict.authorized is False
    assert verdict.rejection_reason == RejectionReason.LOT_SIZE_OUT_OF_BOUNDS


def test_inspect_orden_determinista_news_window_antes_que_insufficient_rr() -> None:
    profile = load_firm_profile()
    event_time = datetime(2024, 3, 1, 14, 30, tzinfo=UTC)
    event = EconomicEvent(
        timestamp_utc=event_time, currency="USD", impact=ImpactLevel.HIGH, title="NFP"
    )
    verdict = inspect(
        _intent(),
        symbol=_SYMBOL,
        intent_time=event_time,
        proposed_rr=0.1,  # también dispararía INSUFFICIENT_RR
        figure=_figure(),
        firm_profile=profile,
        news_events=[event],
        config=_config(min_rr=2.0),
    )
    assert verdict.rejection_reason == RejectionReason.NEWS_WINDOW


def test_rejection_reason_tiene_exactamente_tres_miembros() -> None:
    assert {member.value for member in RejectionReason} == {
        "insufficient_rr",
        "lot_size_out_of_bounds",
        "news_window",
    }


def test_inspector_verdict_es_dataclass_frozen() -> None:
    verdict = InspectorVerdict(authorized=True, rejection_reason=None)
    with pytest.raises(FrozenInstanceError):
        setattr(verdict, "authorized", False)  # noqa: B010


def test_load_inspector_funnel_config_default_empaquetado() -> None:
    config = load_inspector_funnel_config()
    assert isinstance(config, InspectorFunnelConfig)
    assert config.min_rr > 0
    assert config.min_lot > 0
    assert config.max_lot > config.min_lot


def test_load_inspector_funnel_config_json_incompleto_lanza_inspector_config_error(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad_inspector_config.json"
    bad.write_text('{"inspector": {"min_lot": 0.01, "max_lot": 50.0}}', encoding="utf-8")
    with pytest.raises(InspectorConfigError):
        load_inspector_funnel_config(bad)
