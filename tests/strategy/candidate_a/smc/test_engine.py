"""`SmcEngineState` + `update_smc_engine` + `resolve_free_path` (T3.6, R101, R104, R105)."""

from datetime import UTC, datetime, timedelta

import pytest

from genesis.strategy.candidate_a.config import SmcEngineConfig
from genesis.strategy.candidate_a.smc.engine import (
    SmcEngineResult,
    SmcEngineState,
    resolve_free_path,
    update_smc_engine,
)
from genesis.strategy.candidate_a.smc.fractals import Swing, SwingDirection
from genesis.strategy.candidate_a.smc.liquidity import LiquidityMap
from genesis.strategy.candidate_a.smc.timeframe import Timeframe
from genesis.strategy.errors import LookaheadError
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_BASE = datetime(2024, 1, 2, tzinfo=UTC)


def _config(**overrides: object) -> SmcEngineConfig:
    defaults: dict[str, object] = {
        "fractal_n": 2,
        "eq_tolerance_atr": 0.15,
        "sweep_tolerance_atr": 0.05,
        "sweep_window_k": 5,
        "sweep_validity_m": 30,
        "free_path_radius_sigma": 1.0,
        "ct_zscore_min": 2.0,
        "atr_period": 3,
    }
    defaults.update(overrides)
    return SmcEngineConfig(**defaults)  # type: ignore[arg-type]


def test_require_valid_as_of_lanza_lookahead_error_para_timestamp_futuro() -> None:
    state = SmcEngineState("US500", _config())
    bar = make_annotated_bar(_BASE)
    update_smc_engine(state, bar, sigma_t=1.0)

    future = _BASE + timedelta(minutes=5)
    with pytest.raises(LookaheadError):
        state.require_valid_as_of(future)


def test_no_lanza_para_timestamp_no_posterior_al_actual() -> None:
    state = SmcEngineState("US500", _config())
    bar = make_annotated_bar(_BASE)
    update_smc_engine(state, bar, sigma_t=1.0)
    state.require_valid_as_of(_BASE)  # no lanza


def test_aislamiento_entre_dos_smc_engine_state_de_simbolos_distintos() -> None:
    state_a = SmcEngineState("US500", _config())
    state_b = SmcEngineState("NAS100", _config())
    result_a: SmcEngineResult | None = None
    result_b: SmcEngineResult | None = None

    for i in range(5):
        bar_a = make_annotated_bar(
            _BASE + timedelta(minutes=i), close=100.0 + i, high=101.0 + i, low=99.0 + i
        )
        bar_b = make_annotated_bar(
            _BASE + timedelta(minutes=i), close=200.0 - i, high=205.0 - i, low=195.0 - i
        )
        result_a = update_smc_engine(state_a, bar_a, sigma_t=1.0)
        result_b = update_smc_engine(state_b, bar_b, sigma_t=1.0)

    assert result_a is not None
    assert result_b is not None
    assert result_a.atr_by_tf[Timeframe.M1] != result_b.atr_by_tf[Timeframe.M1]
    assert state_a.symbol == "US500"
    assert state_b.symbol == "NAS100"


def test_smc_engine_result_no_expone_swing_sin_confirmar() -> None:
    config = _config(fractal_n=2)
    state = SmcEngineState("US500", config)

    highs = [100.0, 100.0, 105.0, 100.0, 100.0, 100.0, 100.0]
    for index, high in enumerate(highs):
        bar = make_annotated_bar(
            _BASE + timedelta(minutes=index), close=high - 0.5, high=high, low=high - 2.0
        )
        update_smc_engine(state, bar, sigma_t=1.0)
        if index < 4:  # pivote en índice 2 + fractal_n(2) = 4
            assert state.active_swings(Timeframe.M1) == ()

    swings = state.active_swings(Timeframe.M1)
    assert len(swings) == 1
    assert swings[0].price == 105.0


def test_resolve_free_path_elige_h1_sobre_m15_por_jerarquia() -> None:
    liquidity = LiquidityMap(eq_tolerance_atr=0.15)
    h1_swing = Swing(
        timeframe=Timeframe.H1,
        direction=SwingDirection.HIGH,
        price=100.2,
        pivot_time=_BASE,
        confirmed_time=_BASE,
    )
    m15_swing = Swing(
        timeframe=Timeframe.M15,
        direction=SwingDirection.HIGH,
        price=100.1,
        pivot_time=_BASE,
        confirmed_time=_BASE,
    )
    liquidity.add_swing(h1_swing, atr_of_tf=1.0)
    liquidity.add_swing(m15_swing, atr_of_tf=1.0)

    config = _config(free_path_radius_sigma=1.0)
    resolved = resolve_free_path(
        sweep_extreme_price=100.0,
        direction=SwingDirection.HIGH,
        sigma_t=1.0,
        liquidity=liquidity,
        config=config,
    )
    assert resolved is not None
    assert resolved.timeframe == Timeframe.H1


def test_resolve_free_path_retorna_none_sin_liquidez_macro_cercana() -> None:
    liquidity = LiquidityMap(eq_tolerance_atr=0.15)
    config = _config(free_path_radius_sigma=1.0)
    resolved = resolve_free_path(
        sweep_extreme_price=100.0,
        direction=SwingDirection.HIGH,
        sigma_t=1.0,
        liquidity=liquidity,
        config=config,
    )
    assert resolved is None


def test_layering_smc_no_importa_numpy_pandas_backtest_ni_validation() -> None:
    import pathlib
    import re

    smc_dir = (
        pathlib.Path(__file__).parents[4] / "src" / "genesis" / "strategy" / "candidate_a" / "smc"
    )
    pattern = re.compile(r"^import numpy|^import pandas|genesis\.backtest|genesis\.validation")
    for path in smc_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            assert not pattern.search(line), f"{path}: {line!r}"
