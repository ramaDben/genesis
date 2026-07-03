"""Tests unitarios de los value objects puros de `genesis.data.symbols`."""

from pathlib import Path

import pytest

from genesis.data.symbols import SymbolFigure, SymbolSpec

pytestmark = pytest.mark.unit


def _build_figure(symbol: str = "US500") -> SymbolFigure:
    return SymbolFigure(
        symbol=symbol,
        tick_value=1.0,
        volume_step=0.01,
        stops_level=10,
        freeze_level=5,
        digits=2,
        swap_long=-0.5,
        swap_short=-0.3,
        swap_rollover_day=3,
    )


def test_symbol_figure_has_the_eight_extended_fields() -> None:
    figure = _build_figure()
    assert figure.symbol == "US500"
    assert figure.tick_value == 1.0
    assert figure.volume_step == 0.01
    assert figure.stops_level == 10
    assert figure.freeze_level == 5
    assert figure.digits == 2
    assert figure.swap_long == -0.5
    assert figure.swap_short == -0.3
    assert figure.swap_rollover_day == 3


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
