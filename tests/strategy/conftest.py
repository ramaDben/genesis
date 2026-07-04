"""Fixtures compartidas de la suite `tests/strategy/` (capa 2: estrategia).

Los fakes concretos (`FakeStrategyCandidate`) viven en `tests/strategy/fakes.py` (T9).
Este módulo expone fixtures de conveniencia reutilizadas por `common/` (T5) y por el
harness de la propiedad central del §9 (T9/T10).
"""

from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_m1_path() -> Path:
    """Ruta al fixture CSV de velas M1 sintético (`fixtures/sample_m1.csv`, R30)."""
    return _FIXTURES_DIR / "sample_m1.csv"
