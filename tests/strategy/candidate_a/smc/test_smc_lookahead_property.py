"""Propiedad central del spec §9: ningún output de `update_smc_engine(t)` cambia si se
mutan barras posteriores a `t` (R100, R101, R123). Análogo a
`tests/strategy/test_contract_lookahead_property.py`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.strategy.candidate_a.config import SmcEngineConfig
from genesis.strategy.candidate_a.smc.engine import (
    SmcEngineResult,
    SmcEngineState,
    update_smc_engine,
)
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)
_CONFIG = SmcEngineConfig(
    fractal_n=2,
    eq_tolerance_atr=0.15,
    sweep_tolerance_atr=0.05,
    sweep_window_k=5,
    sweep_validity_m=10,
    free_path_radius_sigma=1.0,
    ct_zscore_min=2.0,
    atr_period=3,
)


def _sequence(closes: list[float], *, start_index: int = 0):
    return [
        make_annotated_bar(
            _BASE + timedelta(minutes=start_index + i),
            close=close,
            high=close + 1.0,
            low=close - 1.0,
        )
        for i, close in enumerate(closes)
    ]


def _run_and_capture_at_t(
    prefix_closes: list[float], suffix_closes: list[float]
) -> SmcEngineResult:
    state = SmcEngineState("US500", _CONFIG)
    prefix = _sequence(prefix_closes)

    result_at_t: SmcEngineResult | None = None
    for bar in prefix:
        result_at_t = update_smc_engine(state, bar, sigma_t=1.0)

    suffix = _sequence(suffix_closes, start_index=len(prefix_closes))
    for bar in suffix:
        update_smc_engine(state, bar, sigma_t=1.0)  # avanza el estado; no afecta result_at_t

    assert result_at_t is not None
    return result_at_t


_closes_strategy = st.lists(
    st.floats(min_value=90.0, max_value=110.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=15,
)
_future_closes_strategy = st.lists(
    st.floats(min_value=90.0, max_value=110.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=8,
)


@given(
    prefix_closes=_closes_strategy,
    suffix_closes_a=_future_closes_strategy,
    suffix_closes_b=_future_closes_strategy,
)
@settings(max_examples=200, deadline=None)
def test_update_smc_engine_en_t_no_cambia_si_se_mutan_barras_futuras(
    prefix_closes: list[float],
    suffix_closes_a: list[float],
    suffix_closes_b: list[float],
) -> None:
    result_a = _run_and_capture_at_t(prefix_closes, suffix_closes_a)
    result_b = _run_and_capture_at_t(prefix_closes, suffix_closes_b)
    assert result_a == result_b
