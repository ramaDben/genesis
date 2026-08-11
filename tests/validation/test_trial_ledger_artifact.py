"""Evals estáticos de cierre del ledger de ensayos (Issue #53): A4, A5, A8, A12.

Implementados en Python puro (no shelleando `rg`/`fd`, ausentes en el WSL2 actual de
desarrollo — ver `tasks.md` Nota de ejecución N-1), salvo A5/A12 que shellean `git`
porque el binario sí está disponible.
"""

import re
import subprocess
from pathlib import Path

import pytest

from genesis.validation.verdict import VerdictKind

pytestmark = pytest.mark.unit

_TRIAL_LEDGER_SOURCE = Path("src/genesis/validation/trial_ledger.py").read_text(encoding="utf-8")
_LEDGER_TRIALS_JSONL = Path("ledger/trials.jsonl")

_FORBIDDEN_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(?:scipy|statsmodels|sqlite3)\b", flags=re.MULTILINE
)


def test_verdict_kind_conserva_exactamente_cuatro_miembros() -> None:
    """A4, R17, R91: `VerdictKind` no gana ni pierde miembros con el Change."""
    assert {member.value for member in VerdictKind} == {"go", "go-ensemble", "go-parcial", "no-go"}
    assert len(list(VerdictKind)) == 4


def test_trial_ledger_no_importa_scipy_statsmodels_ni_sqlite3() -> None:
    """A8: `trial_ledger.py` es solo stdlib + `genesis.validation.errors`."""
    assert _FORBIDDEN_IMPORT_RE.findall(_TRIAL_LEDGER_SOURCE) == []


def test_ledger_trials_jsonl_no_esta_ignorado_por_git() -> None:
    """A5, R18: la ruta queda bajo seguimiento de git desde el primer commit."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(_LEDGER_TRIALS_JSONL)],
        cwd=Path.cwd(),
        check=False,
    )
    assert result.returncode == 1
    # Legible como texto plano (UTF-8), sin excepción de decodificación.
    _LEDGER_TRIALS_JSONL.read_text(encoding="utf-8")


def test_ledger_trials_jsonl_hereda_text_auto_eol_lf_sin_regla_nueva() -> None:
    """A12, D4: `.gitattributes` ya cubre la ruta; no hace falta una regla redundante."""
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", str(_LEDGER_TRIALS_JSONL)],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout
    assert "text: auto" in output
    assert "eol: lf" in output
