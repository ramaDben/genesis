"""`diagnostics.py`: `detect_ct_events` + `summarize_raw_edge` (T4.1/T4.2, R111-R115)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.data.store import AnnotatedBar
from genesis.strategy.candidate_a.config import CandidateAConfig, DiagnosticsConfig, SmcEngineConfig
from genesis.strategy.candidate_a.diagnostics import (
    RawEdgeSummary,
    detect_ct_events,
    summarize_raw_edge,
)
from genesis.strategy.contract import Direction
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
_SYMBOL = "XAUUSD"
_SESSION = "london_ny_overlap"


def _config(**smc_overrides: object) -> CandidateAConfig:
    smc_defaults: dict[str, object] = {
        "fractal_n": 1,
        "eq_tolerance_atr": 0.15,
        "sweep_tolerance_atr": 0.05,
        "sweep_window_k": 3,
        "sweep_validity_m": 5,
        "free_path_radius_sigma": 1.0,
        "ct_zscore_min": 2.0,
        "atr_period": 3,
    }
    smc_defaults.update(smc_overrides)
    return CandidateAConfig(
        smc=SmcEngineConfig(**smc_defaults),  # type: ignore[arg-type]
        diagnostics=DiagnosticsConfig(
            horizons_minutes=(5, 15),
            bootstrap_resamples=200,
            bootstrap_block_size=None,
            bootstrap_seed=42,
            stop_distance_atr_buffer_multiple=1.0,
        ),
    )


def _calm_bar(index: int) -> AnnotatedBar:
    return make_annotated_bar(
        _BASE + timedelta(minutes=index), open_=100.0, high=100.2, low=99.8, close=100.0
    )


def _sweep_scenario_bars() -> list[AnnotatedBar]:
    bars = [_calm_bar(0)]
    bars.append(
        make_annotated_bar(
            _BASE + timedelta(minutes=1), open_=100.0, high=102.0, low=99.8, close=100.0
        )
    )
    bars.append(_calm_bar(2))
    bars.extend(_calm_bar(i) for i in range(3, 9))
    # Bar de toque + sweep + CT: high supera el nivel EQH(102), cierra de vuelta y lejos del VWAP.
    bars.append(
        make_annotated_bar(
            _BASE + timedelta(minutes=9), open_=100.0, high=110.0, low=95.0, close=95.5
        )
    )
    # Bars adicionales para permitir el cómputo de retornos forward (horizontes 5/15).
    bars.extend(_calm_bar(i) for i in range(10, 30))
    return bars


def test_detect_ct_events_emite_un_evento_con_sweep_y_zona_ct() -> None:
    config = _config()
    bars = _sweep_scenario_bars()
    events = detect_ct_events(bars, config, _SYMBOL, _SESSION)

    assert len(events) == 1
    event = events[0]
    assert event.symbol == _SYMBOL
    assert event.session_label == _SESSION
    assert event.event_time == _BASE + timedelta(minutes=9)
    assert event.expected_reversion == Direction.SHORT  # sweep de EQH -> reversión corta
    assert event.entry_price == pytest.approx(95.5)
    assert event.stop_distance > 0.0


def test_detect_ct_events_sin_sweep_no_emite_aunque_haya_zona_ct() -> None:
    config = _config()
    bars = [_calm_bar(i) for i in range(9)]
    bars.append(
        make_annotated_bar(
            _BASE + timedelta(minutes=9), open_=100.0, high=100.2, low=95.0, close=95.5
        )
    )
    events = detect_ct_events(bars, config, _SYMBOL, _SESSION)
    assert events == []


def test_detect_ct_events_sin_zona_ct_no_emite_aunque_haya_sweep() -> None:
    # ct_zscore_min extremadamente alto: ninguna barra alcanza zona CT.
    config = _config(ct_zscore_min=1_000_000.0)
    bars = _sweep_scenario_bars()
    events = detect_ct_events(bars, config, _SYMBOL, _SESSION)
    assert events == []


def test_summarize_raw_edge_reproducible_con_semilla_fija_y_sin_veredicto_ni_coste() -> None:
    config = _config()
    bars = _sweep_scenario_bars()
    events = detect_ct_events(bars, config, _SYMBOL, _SESSION)
    assert len(events) == 1

    summary_a = summarize_raw_edge(bars, events, config)
    summary_b = summarize_raw_edge(bars, events, config)

    assert summary_a == summary_b
    assert isinstance(summary_a, RawEdgeSummary)
    assert not hasattr(summary_a, "verdict")
    assert not hasattr(summary_a, "roundtrip_cost")
    assert summary_a.n_ct_events == 1
    assert {h.horizon_minutes for h in summary_a.horizons} == {5, 15}
    for horizon in summary_a.horizons:
        assert horizon.n_events == 1


def test_summarize_raw_edge_horizontes_truncados_al_agotar_la_serie() -> None:
    config = _config()
    bars = _sweep_scenario_bars()[:15]  # solo 5 barras después del evento (índice 9)
    events = detect_ct_events(bars, config, _SYMBOL, _SESSION)
    assert len(events) == 1

    summary = summarize_raw_edge(bars, events, config)
    horizon_5 = next(h for h in summary.horizons if h.horizon_minutes == 5)
    horizon_15 = next(h for h in summary.horizons if h.horizon_minutes == 15)
    assert horizon_5.n_events == 1  # 9+5=14 < 15 barras disponibles
    assert horizon_15.n_events == 0  # 9+15=24 >= 15 barras disponibles
