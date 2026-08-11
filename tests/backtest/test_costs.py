"""Tests del modelo de costos con `stress` de primera clase (R37–R41)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from genesis.backtest.costs import (
    CostsConfig,
    commission_for,
    load_costs_config,
    slippage_for,
    spread_for,
    swap_for,
)
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import TickRow
from genesis.data.symbols import SymbolFigure

pytestmark = pytest.mark.unit

_FIGURE = SymbolFigure(
    symbol="US500",
    tick_value=1.0,
    tick_size=1.0,
    volume_step=0.01,
    stops_level=10,
    freeze_level=5,
    digits=2,
    swap_long=-2.0,
    swap_short=-1.5,
    swap_rollover_day=3,
)

_CONFIG = CostsConfig(default_spread_points=1.5, commission_per_lot=7.0, slippage_points=0.2)


def test_spread_for_stress_duplica_el_costo() -> None:
    base = spread_for("US500", datetime(2024, 1, 2, tzinfo=UTC), _FIGURE, None, _CONFIG)
    stressed = spread_for(
        "US500", datetime(2024, 1, 2, tzinfo=UTC), _FIGURE, None, _CONFIG, stress=2.0
    )
    assert stressed == pytest.approx(base * 2.0)


def test_spread_for_sin_ticks_usa_default_spread_points() -> None:
    value = spread_for("US500", datetime(2024, 1, 2, tzinfo=UTC), _FIGURE, None, _CONFIG)
    assert value == pytest.approx(_CONFIG.default_spread_points)


def test_spread_for_con_ticks_usa_mediana_de_ask_menos_bid() -> None:
    ticks = [
        TickRow(timestamp_utc=datetime(2024, 1, 2, tzinfo=UTC), bid=100.0, ask=100.2, last=100.1),
        TickRow(timestamp_utc=datetime(2024, 1, 2, tzinfo=UTC), bid=100.0, ask=100.4, last=100.1),
    ]
    value = spread_for("US500", datetime(2024, 1, 2, tzinfo=UTC), _FIGURE, ticks, _CONFIG)
    assert value == pytest.approx(0.3)


def test_commission_for_stress_duplica_el_costo() -> None:
    base = commission_for(1.0, _CONFIG)
    stressed = commission_for(1.0, _CONFIG, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_slippage_for_stress_duplica_el_costo() -> None:
    base = slippage_for(_FIGURE, _CONFIG)
    stressed = slippage_for(_FIGURE, _CONFIG, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_swap_for_stress_duplica_el_costo() -> None:
    base = swap_for("US500", 1, _FIGURE, is_long=True)
    stressed = swap_for("US500", 1, _FIGURE, is_long=True, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_swap_for_triple_en_dia_de_rollover_vs_dia_ordinario() -> None:
    ordinario = swap_for("US500", 1, _FIGURE, is_long=True)
    rollover = swap_for("US500", _FIGURE.swap_rollover_day, _FIGURE, is_long=True)
    assert rollover == pytest.approx(ordinario * 3.0)


def test_load_costs_config_default_empaquetado() -> None:
    config = load_costs_config()
    assert isinstance(config, CostsConfig)
    assert config.default_spread_points > 0


def test_load_costs_config_incompleta_lanza_backtest_config_error(tmp_path: Path) -> None:
    incomplete = tmp_path / "costs_config.json"
    incomplete.write_text(json.dumps({"commission_per_lot": 7.0}), encoding="utf-8")
    with pytest.raises(BacktestConfigError):
        load_costs_config(incomplete)
