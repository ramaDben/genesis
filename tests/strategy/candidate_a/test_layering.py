"""Guard de aislamiento de capas + no-registro en `CANDIDATE_REGISTRY` (T6.3, ADR-D8)."""

import pathlib
import re

import pytest

import genesis.strategy.candidate_a  # noqa: F401 (fuerza el import para poblar CANDIDATE_REGISTRY)
from genesis.strategy.contract import CANDIDATE_REGISTRY

pytestmark = pytest.mark.unit

_CANDIDATE_A_DIR = (
    pathlib.Path(__file__).parents[3] / "src" / "genesis" / "strategy" / "candidate_a"
)
_LAYER_PATTERN = re.compile(r"genesis\.backtest|genesis\.validation")


def test_candidate_a_no_importa_capa_3_ni_capa_4() -> None:
    """`rg -n "genesis\\.backtest|genesis\\.validation" src/genesis/strategy/candidate_a/` → 0."""
    offending: list[str] = []
    for path in _CANDIDATE_A_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _LAYER_PATTERN.search(line):
                offending.append(f"{path}:{line_number}: {line!r}")
    assert offending == [], "\n".join(offending)


def test_candidate_a_no_registra_la_letra_a_en_candidate_registry() -> None:
    """ADR-D8: `smc_engine`/`diagnostics.py` no llaman `register_candidate('A')`."""
    assert "A" not in CANDIDATE_REGISTRY
