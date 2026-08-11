"""Tests unitarios de los value objects puros de `genesis.data.symbols`."""

import re
from dataclasses import fields
from pathlib import Path

import pytest

from genesis.data.symbols import SymbolFigure, SymbolSpec

pytestmark = pytest.mark.unit


def _build_figure(symbol: str = "US500") -> SymbolFigure:
    return SymbolFigure(
        symbol=symbol,
        tick_value=1.0,
        tick_size=1.0,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.3,
        swap_rollover_day=3,
    )


def test_symbol_figure_has_the_nine_extended_fields() -> None:
    figure = _build_figure()
    assert figure.symbol == "US500"
    assert figure.tick_value == 1.0
    assert figure.tick_size == 1.0
    assert figure.volume_step == 0.01
    assert figure.stops_level == 10
    assert figure.freeze_level == 5
    assert figure.digits == 2
    assert figure.swap_long == -0.5
    assert figure.swap_short == -0.3
    assert figure.swap_rollover_day == 3
    assert len(fields(SymbolFigure)) == 10


def test_symbol_figure_sin_tick_size_lanza_type_error() -> None:
    payload = {
        "symbol": "US500",
        "tick_value": 1.0,
        "volume_step": 0.01,
        "stops_level": 10,
        "freeze_level": 5,
        "digits": 2,
        "swap_long": -0.5,
        "swap_short": -0.3,
        "swap_rollover_day": 3,
    }
    with pytest.raises(TypeError):
        SymbolFigure(**payload)  # ty: ignore[invalid-argument-type]


def test_value_per_point_es_el_cociente_crudo() -> None:
    figure = SymbolFigure(
        symbol="GER40",
        tick_value=0.0115435,
        tick_size=0.01,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.3,
        swap_rollover_day=3,
    )
    assert figure.value_per_point == pytest.approx(1.15435)
    assert _build_figure().value_per_point == 1.0


def test_value_per_point_con_tick_size_no_positivo_lanza_value_error() -> None:
    figure = SymbolFigure(
        symbol="US500",
        tick_value=1.0,
        tick_size=0.0,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.3,
        swap_rollover_day=3,
    )
    with pytest.raises(ValueError, match="US500"):
        _ = figure.value_per_point


def test_ningun_consumidor_multiplica_tick_value_crudo() -> None:
    """Eval estático A8: ningún consumidor de capa 3 debe multiplicar por `tick_value` crudo."""
    repo_root = Path(__file__).parents[2]
    candidate_path = repo_root / "src" / "genesis" / "strategy" / "candidate_b" / "candidate.py"
    simulator_path = repo_root / "src" / "genesis" / "backtest" / "simulator.py"
    pattern = re.compile(r"\.tick_value\b")
    assert not pattern.search(candidate_path.read_text(encoding="utf-8"))
    assert not pattern.search(simulator_path.read_text(encoding="utf-8"))


def test_spec_data_r10_incluye_tick_size() -> None:
    """Eval estático A9: el delta de R10 en el spec normativo de datos incluye `tick_size`."""
    repo_root = Path(__file__).parents[2]
    spec_path = repo_root / ".pulse" / "specs" / "data" / "spec.md"
    text = spec_path.read_text(encoding="utf-8")
    match = re.search(r"\*\*R10\*\*.*?(?=\n- \*\*R\d)", text, re.DOTALL)
    assert match is not None
    assert "tick_size" in match.group(0)


def test_symbol_figure_is_frozen() -> None:
    figure = _build_figure()
    with pytest.raises(AttributeError):
        figure.tick_value = 2.0  # ty: ignore[invalid-assignment]


def test_symbol_spec_with_min_full_sessions() -> None:
    figure = _build_figure()
    spec = SymbolSpec(symbol="US500", figure=figure, min_full_sessions=60)
    assert spec.symbol == "US500"
    assert spec.figure is figure
    assert spec.min_full_sessions == 60


def test_symbol_spec_allows_missing_figure() -> None:
    spec = SymbolSpec(symbol="US500", figure=None, min_full_sessions=60)
    assert spec.figure is None


def test_symbols_module_does_not_import_metatrader5() -> None:
    """symbols.py debe ser puro: quality.py lo usa sin arrastrar el SDK (R10, R24)."""
    module_path = Path(__file__).parents[2] / "src" / "genesis" / "data" / "symbols.py"
    lines = module_path.read_text(encoding="utf-8").splitlines()
    import_lines = [line for line in lines if line.startswith(("import ", "from "))]
    assert not any("MetaTrader5" in line for line in import_lines)
