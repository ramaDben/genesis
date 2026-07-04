"""Fixtures compartidas de la suite `tests/data/` (capa 1: datos).

Los fakes concretos (`FakeMt5Terminal`, `FakeEconomicCalendarSource`) viven en
`tests/data/fakes.py` y se completan junto con las tareas T4.1/T6.3 del Change. Este
módulo expone fixtures de conveniencia que dependen de ellos una vez definidos.
"""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_raw_store(tmp_path: Path) -> Path:
    """Directorio temporal aislado para `RawParquetStore` (sin tocar el filesystem real)."""
    root = tmp_path / "raw_store"
    root.mkdir()
    return root
