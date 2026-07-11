"""Estadístico: el criterio de archivo mecánico se dispara sin ajuste manual (T5.3, R118, R125)."""

import pytest

from genesis.strategy.candidate_a.diagnostics import HorizonEdge, RawEdgeSummary
from genesis.validation.signal_diagnostic import ArchiveOrContinue, decide_verdict

pytestmark = pytest.mark.statistical


def _raw_edge(bootstrap_low: float) -> RawEdgeSummary:
    return RawEdgeSummary(
        symbol="XAUUSD",
        session_label="test",
        horizons=(
            HorizonEdge(
                horizon_minutes=5,
                conditional_mean=bootstrap_low + 0.001,
                unconditional_mean=0.0,
                bootstrap_low=bootstrap_low,
                bootstrap_high=bootstrap_low + 0.002,
                n_events=50,
            ),
        ),
        vwap_touch_rate=0.5,
        typical_stop_distance=1.0,
        n_ct_events=50,
    )


def test_edge_positivo_conocido_y_coste_bajo_produce_continue() -> None:
    raw_edge = _raw_edge(bootstrap_low=0.005)  # edge bruto 0.5%
    roundtrip_cost = 0.0005  # coste bajo, 0.05%
    assert decide_verdict(raw_edge, roundtrip_cost) == ArchiveOrContinue.CONTINUE


def test_edge_nulo_produce_archive() -> None:
    raw_edge = _raw_edge(bootstrap_low=0.0)
    roundtrip_cost = 0.0005
    assert decide_verdict(raw_edge, roundtrip_cost) == ArchiveOrContinue.ARCHIVE


def test_edge_negativo_produce_archive() -> None:
    raw_edge = _raw_edge(bootstrap_low=-0.003)
    roundtrip_cost = 0.0005
    assert decide_verdict(raw_edge, roundtrip_cost) == ArchiveOrContinue.ARCHIVE


def test_mismo_edge_positivo_con_coste_alto_produce_archive_sin_ajustar_umbral() -> None:
    """Mismo dataset (mismo edge bruto) que el caso CONTINUE, solo cambia el coste."""
    raw_edge = _raw_edge(bootstrap_low=0.005)
    roundtrip_cost = 0.01  # coste alto, supera el edge bruto
    assert decide_verdict(raw_edge, roundtrip_cost) == ArchiveOrContinue.ARCHIVE


def test_sin_horizontes_produce_archive() -> None:
    raw_edge = RawEdgeSummary(
        symbol="XAUUSD",
        session_label="test",
        horizons=(),
        vwap_touch_rate=0.0,
        typical_stop_distance=0.0,
        n_ct_events=0,
    )
    assert decide_verdict(raw_edge, 0.0) == ArchiveOrContinue.ARCHIVE
