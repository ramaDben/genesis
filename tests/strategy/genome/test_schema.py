"""Tests unitarios para el esquema del genoma declarativo y excepciones de dominio."""

from __future__ import annotations

import pytest

from genesis.strategy.genome.errors import (
    GenomeValidationError,
    MissingAcademicProvenanceError,
    UnknownRiskExitParamError,
)
from genesis.strategy.genome.schema import (
    GenomeAlpha,
    GenomeFidelity,
    GenomeMetadata,
    GenomeRiskExit,
    GenomeUniverse,
    StrategyGenome,
    parse_genome,
)

_VALID_GENOME_YAML = """
metadata:
  id: "CANDIDATE-C1-TEST"
  author: "Gao et al."
  paper_ref: "SSRN:12345"
  economic_rationale: "Desbalance institucional de apertura."
  fidelity: "canonical"
universe:
  symbol: "US500"
  timeframe: "M15"
  session: "US_EQUITY_OPEN"
alpha:
  entry_trigger:
    kind: "opening_range_breakout"
    range_minutes: 30
risk_exit:
  kind: "chandelier_trailing"
  params:
    lookback_bars: 22
    atr_multiplier: 3.0
"""


def test_genome_fidelity_enum_values():
    assert GenomeFidelity.CANONICAL == "canonical"
    assert GenomeFidelity.INTERPRETED == "interpreted"
    assert GenomeFidelity.OPTIMIZED == "optimized"
    assert GenomeFidelity.COMBINED == "combined"


def test_strategy_genome_immutability():
    metadata = GenomeMetadata(
        id="CANDIDATE-B1",
        author="Gao et al.",
        paper_ref="SSRN:12345",
        economic_rationale="Desbalance institucional de apertura.",
        fidelity=GenomeFidelity.CANONICAL,
    )
    universe = GenomeUniverse(
        symbol="US500",
        timeframe="M15",
        session="US_EQUITY_OPEN",
    )
    alpha = GenomeAlpha(
        regime_filter={"kind": "rvol", "threshold": 1.0},
        entry_trigger={"kind": "opening_range_breakout", "range_minutes": 30},
    )
    risk_exit = GenomeRiskExit(
        kind="chandelier_trailing",
        params={"lookback_bars": 22, "atr_multiplier": 3.0},
    )
    genome = StrategyGenome(
        metadata=metadata,
        universe=universe,
        alpha=alpha,
        risk_exit=risk_exit,
        raw_config={"foo": "bar"},
    )

    assert genome.metadata.id == "CANDIDATE-B1"
    assert genome.universe.symbol == "US500"
    assert genome.metadata.fidelity == GenomeFidelity.CANONICAL

    # Inmutabilidad (frozen=True)
    with pytest.raises(AttributeError):
        setattr(genome.metadata, "id", "MUTATED")  # noqa: B010

    with pytest.raises(AttributeError):
        setattr(genome.universe, "symbol", "US100")  # noqa: B010


def test_domain_exceptions_hierarchy():
    assert issubclass(GenomeValidationError, Exception)
    assert issubclass(MissingAcademicProvenanceError, GenomeValidationError)
    assert issubclass(UnknownRiskExitParamError, GenomeValidationError)

    err = MissingAcademicProvenanceError("Falta paper_ref obligatorio")
    assert isinstance(err, GenomeValidationError)
    assert "Falta paper_ref" in str(err)


def test_unknown_risk_exit_param_rejected() -> None:
    """Eval U7 (AC7, C1): clave desconocida en `risk_exit.params` -> `UnknownRiskExitParamError`."""
    yaml_content = _VALID_GENOME_YAML.replace(
        "    atr_multiplier: 3.0", "    atr_multiplier: 3.0\n    foo_bar: 1.0"
    )
    with pytest.raises(UnknownRiskExitParamError) as excinfo:
        parse_genome(yaml_content)
    assert "foo_bar" in str(excinfo.value)


def test_chandelier_sin_atr_multiplier_falla() -> None:
    """Eval U8 (AC7, R7): `chandelier_trailing` sin `atr_multiplier` -> falla nombrando la clave."""
    yaml_content = _VALID_GENOME_YAML.replace("    atr_multiplier: 3.0\n", "")
    with pytest.raises(GenomeValidationError, match="atr_multiplier"):
        parse_genome(yaml_content)


def test_chandelier_sin_lookback_bars_falla() -> None:
    yaml_content = _VALID_GENOME_YAML.replace("    lookback_bars: 22\n", "")
    with pytest.raises(GenomeValidationError, match="lookback_bars"):
        parse_genome(yaml_content)


# --- Change #130 (B.6): sección opcional `declared_universe` ---


def _yaml_con_universo(valor: str) -> str:
    return _VALID_GENOME_YAML + f"declared_universe: {valor}\n"


def test_parse_genome_lee_declared_universe():
    """N15 (AC6): la sección opcional se parsea a tupla en el orden declarado."""
    genome = parse_genome(_yaml_con_universo('["SYM_A", "SYM_B", "SYM_C"]'))
    assert genome.declared_universe == ("SYM_A", "SYM_B", "SYM_C")


def test_genomas_existentes_sin_declared_universe_parsean_a_none():
    """N16 (AC7): los genomas reales de `candidates/specs/` siguen parseando (universo `None`)."""
    from pathlib import Path

    specs = sorted(Path(__file__).resolve().parents[3].glob("candidates/specs/*.yaml"))
    assert len(specs) >= 2
    for spec in specs:
        assert parse_genome(spec).declared_universe is None


def test_declared_universe_con_duplicados_se_rechaza():
    """N17 (AC8)."""
    with pytest.raises(GenomeValidationError, match="SYM_A"):
        parse_genome(_yaml_con_universo('["SYM_A", "SYM_A"]'))


@pytest.mark.parametrize("valor", ['"SYM_A"', "{a: 1}"])
def test_declared_universe_debe_ser_lista(valor):
    """N18 (R2): un `str` no se itera carácter por carácter; un mapa tampoco vale."""
    with pytest.raises(GenomeValidationError, match="declared_universe"):
        parse_genome(_yaml_con_universo(valor))


@pytest.mark.parametrize("valor", ['["SYM_A", ""]', '["SYM_A", 3]'])
def test_declared_universe_elemento_vacio_o_no_str_se_rechaza(valor):
    """N19 (R2)."""
    with pytest.raises(GenomeValidationError, match="declared_universe"):
        parse_genome(_yaml_con_universo(valor))


def test_raw_config_excluye_declared_universe():
    """N20 (D4, R9): el universo no entra a `raw_config` (que termina hasheado en `trial_id`)."""
    sin = parse_genome(_VALID_GENOME_YAML)
    con = parse_genome(_yaml_con_universo('["SYM_A", "SYM_B"]'))
    assert "declared_universe" not in con.raw_config
    assert dict(con.raw_config) == dict(sin.raw_config)
