"""Tests para CompiledGenomeCandidate: cumplimiento de protocolos y semántica forward-only."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import Direction, StrategyCandidate
from genesis.strategy.genome.candidate import CompiledGenomeCandidate
from genesis.strategy.genome.errors import CompiledCandidateStateError
from genesis.strategy.genome.schema import parse_genome

RAW_GENOME_YAML = """
metadata:
  id: "CANDIDATE-B1-ORB"
  author: "Gao et al."
  paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"
  economic_rationale: "Desbalance de inventario institucional."
  fidelity: "canonical"

universe:
  symbol: "US500"
  timeframe: "M1"
  session: "US_EQUITY_OPEN"

alpha:
  regime_filter:
    kind: "rvol"
    threshold: 0.0
    lookback_days: 20
  entry_trigger:
    kind: "opening_range_breakout"
    range_minutes: 5

risk_exit:
  kind: "chandelier_trailing"
  params:
    lookback_bars: 22
    atr_multiplier: 3.0
"""


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


def _make_bar(
    minute: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    *,
    in_session: bool = True,
    trading_day: date = date(2024, 1, 15),
    tick_volume: int = 100,
) -> AnnotatedBar:
    t = datetime(2024, 1, 15, 14, 30 + minute, tzinfo=UTC)
    return AnnotatedBar(
        timestamp_utc=t,
        open=open_,
        high=high,
        low=low,
        close=close,
        tick_volume=tick_volume,
        trading_day=trading_day,
        in_session=in_session,
        session_open_utc=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        session_close_utc=datetime(2024, 1, 15, 21, 0, tzinfo=UTC),
    )


def test_compiled_candidate_satisfies_protocols(us500_figure: SymbolFigure):
    genome = parse_genome(RAW_GENOME_YAML)
    candidate = CompiledGenomeCandidate(
        genome,
        figure=us500_figure,
        reference_balance=100_000.0,
        params={"risk_pct": 0.01, "atr_stop_frac": 0.5},
    )

    # Cumple StrategyCandidate
    assert isinstance(candidate, StrategyCandidate)
    assert candidate.candidate_id == "CANDIDATE-B1-ORB"
    assert hasattr(candidate, "on_bar")
    assert callable(candidate.on_bar)

    # Cumple RiskLevelsProvider por duck typing
    assert hasattr(candidate, "risk_levels")
    assert callable(candidate.risk_levels)


def test_compiled_candidate_forward_only_breakout(us500_figure: SymbolFigure):
    """Verifica que on_bar opera barra a barra sin mirar al futuro (A6) y emite señal en ruptura."""
    genome = parse_genome(RAW_GENOME_YAML)
    candidate = CompiledGenomeCandidate(
        genome,
        figure=us500_figure,
        reference_balance=100_000.0,
        params={"risk_pct": 0.01, "atr_stop_frac": 0.5},
    )

    # Minutos 0 a 4: Formación del rango de apertura (5 minutos)
    # Apertura en 5000, cierre alcista hacia 5010 (dirección LONG)
    bars = [
        _make_bar(0, 5000.0, 5005.0, 4995.0, 5002.0),
        _make_bar(1, 5002.0, 5006.0, 5000.0, 5004.0),
        _make_bar(2, 5004.0, 5008.0, 5002.0, 5006.0),
        _make_bar(3, 5006.0, 5009.0, 5003.0, 5007.0),
        _make_bar(4, 5007.0, 5010.0, 5005.0, 5010.0),
    ]

    for bar in bars:
        intents = candidate.on_bar(bar)
        assert len(intents) == 0, "No debe emitir intenciones durante la formación del rango"

    # Minuto 5: Barra de ruptura alcista por encima de range_high (5010.0)
    breakout_bar = _make_bar(5, 5010.0, 5020.0, 5008.0, 5015.0)
    intents = candidate.on_bar(breakout_bar)

    assert len(intents) == 1
    intent = intents[0]
    assert intent.direction == Direction.LONG
    assert intent.candidate_id == "CANDIDATE-B1-ORB"
    assert intent.sizing_hint > 0

    # Lectura de risk_levels
    stop_loss, take_profit = candidate.risk_levels(intent)
    assert stop_loss < 5015.0  # Stop por debajo de la entrada para LONG
    assert take_profit is None  # Chandelier trailing por defecto no define TP fijo

    # Pop-on-read: segunda lectura debe fallar
    with pytest.raises(CompiledCandidateStateError):
        candidate.risk_levels(intent)


def test_compiled_candidate_ignores_out_of_session_bars(us500_figure: SymbolFigure):
    genome = parse_genome(RAW_GENOME_YAML)
    candidate = CompiledGenomeCandidate(
        genome,
        figure=us500_figure,
        reference_balance=100_000.0,
        params={"risk_pct": 0.01},
    )

    out_bar = _make_bar(0, 5000.0, 5010.0, 4990.0, 5005.0, in_session=False)
    intents = candidate.on_bar(out_bar)
    assert len(intents) == 0
