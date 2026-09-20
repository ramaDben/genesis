"""Tests para el compilador de genomas declarativos (T4, R3, R4, A3, A4)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from genesis.backtest.exit_geometry import ExitGeometrySource
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import StrategyCandidate
from genesis.strategy.errors import ExitGeometryConfigError
from genesis.strategy.factories import CandidateFactory, ExitGeometryProvider
from genesis.strategy.genome.compiler import compile_genome
from genesis.strategy.genome.errors import MissingAcademicProvenanceError
from genesis.validation.trial_ledger import compute_trial_id

GENOME_YAML_1 = """
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
    threshold: 1.0
    lookback_days: 10
  entry_trigger:
    kind: "opening_range_breakout"
    range_minutes: 30

risk_exit:
  kind: "chandelier_trailing"
  params:
    lookback_bars: 22
    atr_multiplier: 3.0
"""

# Mismo contenido con claves invertidas
GENOME_YAML_KEY_ORDER = """
risk_exit:
  params:
    atr_multiplier: 3.0
    lookback_bars: 22
  kind: "chandelier_trailing"

alpha:
  entry_trigger:
    range_minutes: 30
    kind: "opening_range_breakout"
  regime_filter:
    lookback_days: 10
    threshold: 1.0
    kind: "rvol"

universe:
  session: "US_EQUITY_OPEN"
  timeframe: "M1"
  symbol: "US500"

metadata:
  fidelity: "canonical"
  economic_rationale: "Desbalance de inventario institucional."
  paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"
  author: "Gao et al."
  id: "CANDIDATE-B1-ORB"
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


def test_compile_genome_returns_candidate_factory(us500_figure: SymbolFigure):
    factory = compile_genome(GENOME_YAML_1)

    # Criterio A3: Cumple el protocolo CandidateFactory
    assert isinstance(factory, CandidateFactory)
    assert hasattr(factory, "raw_config")
    assert isinstance(factory.raw_config, Mapping)

    candidate = factory(
        figure=us500_figure,
        reference_balance=100_000.0,
        params={"risk_pct": 0.01, "atr_stop_frac": 0.5},
    )

    assert isinstance(candidate, StrategyCandidate)
    assert candidate.candidate_id == "CANDIDATE-B1-ORB"
    assert hasattr(candidate, "risk_levels")


def test_compile_genome_trial_id_invariance():
    """Criterio A4: Dos compilaciones con orden de claves distinto producen idéntico trial_id."""
    factory1 = compile_genome(GENOME_YAML_1)
    factory2 = compile_genome(GENOME_YAML_KEY_ORDER)

    dummy_dataset_hash = {"US500": "abcdef123456"}
    firm_hash = "firm_hash_1"
    exit_geometry_hash = "exit_geometry_hash_1"
    house_rule_hash = "house_rule_hash_1"

    trial_id_1 = compute_trial_id(
        factory1.raw_config,
        dummy_dataset_hash,
        firm_hash,
        exit_geometry_hash,
        house_rule_hash,
    )
    trial_id_2 = compute_trial_id(
        factory2.raw_config,
        dummy_dataset_hash,
        firm_hash,
        exit_geometry_hash,
        house_rule_hash,
    )

    assert trial_id_1 == trial_id_2
    assert len(trial_id_1) == 64


def test_compile_genome_rejects_missing_provenance():
    target = 'paper_ref: "SSRN: Gao, Han, Li & Zhou (2018)"'
    bad_yaml = GENOME_YAML_1.replace(target, 'paper_ref: ""')
    with pytest.raises(MissingAcademicProvenanceError):
        compile_genome(bad_yaml)


def test_genome_candidate_factory_implementa_exit_geometry_provider():
    """C2: `GenomeCandidateFactory` es un `ExitGeometryProvider` (Protocol runtime_checkable)."""
    factory = compile_genome(GENOME_YAML_1)
    assert isinstance(factory, ExitGeometryProvider)
    assert factory.exit_geometry.trailing_lookback == 22
    assert factory.exit_geometry.trailing_atr_mult == 3.0
    assert factory.exit_geometry.source == ExitGeometrySource.GENOME


def test_exit_geometry_del_candidato_c1_real_llega_al_motor():
    """Eval C2: el caso real que hoy nunca llega al motor (`design.md` C2)."""
    factory = compile_genome(Path("candidates/specs/candidate_c1_gold_lob.yaml"))
    assert factory.exit_geometry.trailing_atr_mult == 2.5


@pytest.mark.parametrize(
    ("target", "reemplazo", "campo"),
    [
        ("atr_multiplier: 3.0", "atr_multiplier: 0.0", "trailing_atr_mult"),
        ("lookback_bars: 22", "lookback_bars: 0", "trailing_lookback"),
    ],
)
def test_genoma_con_geometria_imposible_lanza_error_de_capa_2(
    target: str, reemplazo: str, campo: str
) -> None:
    """Un genoma con geometría imposible falla con el error de capa 2, no el de capa 3.

    La fábrica vive en capa 2 y construye la `ExitGeometry` directamente, así que la
    guarda del contenedor le llega cruda: `ExitGeometryConfigError`. Antes de que el
    contenedor bajara de capa, este mismo camino dejaba escapar un
    `BacktestConfigError` —un error de capa 3 saliendo de código de capa 2—, que era
    parte del cruce de capas que el Change #109 vino a eliminar.

    `compile_genome` no valida rangos (R9, sin cotas): el genoma declara y el
    contenedor rechaza sólo lo imposible, así que el error aparece al resolver la
    propiedad, no al compilar.
    """
    factory = compile_genome(GENOME_YAML_1.replace(target, reemplazo))
    with pytest.raises(ExitGeometryConfigError, match=campo):
        _ = factory.exit_geometry
