"""Fixtures compartidas de la suite `tests/strategy/` (capa 2: estrategia).

Los fakes concretos (`FakeStrategyCandidate`, `make_annotated_bar`) viven en
`tests/strategy/fakes.py` (T9, R38). Este módulo expone fixtures de conveniencia
(`sample_annotated_bars`, `firm_profile_fixture`, `symbol_figure_fixture`,
`sample_m1_path`, R42) reutilizadas por `common/` (T5) y por el harness de la
propiedad central del §9 (T10). No duplica la construcción de `FirmProfile`/
`SymbolFigure` ya validada en la capa 1: reutiliza `load_firm_profile()` y
`_default_symbol_figure` de `tests/data/fakes.py`.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from genesis.data.profile import FirmProfile, load_firm_profile
from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_m1_path() -> Path:
    """Ruta al fixture CSV de velas M1 sintético (`fixtures/sample_m1.csv`, R30)."""
    return _FIXTURES_DIR / "sample_m1.csv"


@pytest.fixture
def firm_profile_fixture() -> FirmProfile:
    """Ficha de firma por defecto (`load_firm_profile()`), sin duplicar su construcción."""
    return load_firm_profile()


@pytest.fixture
def symbol_figure_fixture() -> SymbolFigure:
    """Ficha extendida de símbolo por defecto, reutilizando `tests/data/fakes.py`."""
    return _default_symbol_figure("US500")


@pytest.fixture
def sample_annotated_bars() -> list[AnnotatedBar]:
    """Secuencia determinista y ascendente de `AnnotatedBar` (10 barras M1 UTC)."""
    base = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    return [
        make_annotated_bar(base.replace(minute=base.minute + i), close=100.0 + i) for i in range(10)
    ]
