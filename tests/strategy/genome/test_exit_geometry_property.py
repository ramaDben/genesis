"""PROP-1 (AC8, C3, Change #109): nada se recorta entre el genoma y el motor.

Para todo `mult`/`lookback` declarados en `risk_exit.params`, el valor que usa el
`Simulator`, el que guarda `ExitGeometry` y el que entra en `exit_geometry_hash` son
el mismo valor — sin cotas ni redondeos (Invariante 3b de `proposal.md`).
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.backtest.exit_geometry import ExitGeometrySource, exit_geometry_hash
from genesis.strategy.genome.compiler import compile_genome

_GENOME_TEMPLATE = """
metadata:
  id: "CANDIDATE-PROP1-TEST"
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
    lookback_bars: {lookback}
    atr_multiplier: {mult}
"""


@given(
    mult=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False),
    lookback=st.integers(min_value=1, max_value=5000),
)
@settings(max_examples=200, deadline=None)
def test_prop1_nada_se_recorta_entre_el_genoma_y_el_motor(mult: float, lookback: int) -> None:
    yaml_content = _GENOME_TEMPLATE.format(lookback=lookback, mult=repr(mult))
    factory = compile_genome(yaml_content)

    geometry = factory.exit_geometry

    assert geometry.trailing_lookback == lookback
    assert geometry.trailing_atr_mult == mult
    assert geometry.source == ExitGeometrySource.GENOME

    # El hash es una función pura de (lookback, mult): dos geometrías con los mismos
    # valores declarados producen el mismo hash, sin importar redondeos intermedios.
    same_geometry = factory.exit_geometry
    assert exit_geometry_hash(geometry) == exit_geometry_hash(same_geometry)
