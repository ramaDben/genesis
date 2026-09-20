"""Tests unit + property de `trial_ledger.py`: identidad, lectura y escritura (Issue #53)."""

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from genesis.validation.errors import TrialLedgerConfigError
from genesis.validation.trial_ledger import (
    TrialLedger,
    TrialLedgerSummary,
    TrialOutcomeKind,
    TrialRecord,
    append_trial,
    compute_trial_id,
    read_trial_summary,
)
from tests.validation.fakes import (
    make_discarded_trial_record,
    make_trial_identity_context,
    make_trial_record,
)

pytestmark = pytest.mark.unit


# --- T2: TrialOutcomeKind + TrialRecord + __post_init__ ---


def test_trial_outcome_kind_tiene_exactamente_dos_miembros() -> None:
    members = list(TrialOutcomeKind)
    assert len(members) == 2
    assert {member.name for member in members} == {"WFA_COMPLETADO", "DESCARTADO"}


def test_trial_record_descartado_sin_razon_lanza_trial_ledger_config_error() -> None:
    with pytest.raises(TrialLedgerConfigError):
        make_trial_record(outcome=TrialOutcomeKind.DESCARTADO, discard_reason=None)


def test_trial_record_completado_con_razon_lanza_trial_ledger_config_error() -> None:
    with pytest.raises(TrialLedgerConfigError):
        make_trial_record(outcome=TrialOutcomeKind.WFA_COMPLETADO, discard_reason="x")


def test_trial_record_coherente_descartado_construye_y_es_inmutable() -> None:
    record = make_trial_record(outcome=TrialOutcomeKind.DESCARTADO, discard_reason="razón")
    assert record.outcome == TrialOutcomeKind.DESCARTADO
    with pytest.raises(FrozenInstanceError):
        record.trial_id = "otro"  # ty: ignore[invalid-assignment]


def test_trial_record_coherente_completado_construye_y_es_inmutable() -> None:
    record = make_trial_record(outcome=TrialOutcomeKind.WFA_COMPLETADO, discard_reason=None)
    assert record.outcome == TrialOutcomeKind.WFA_COMPLETADO
    with pytest.raises(FrozenInstanceError):
        record.trial_id = "otro"  # ty: ignore[invalid-assignment]


# --- T3: compute_trial_id ---


def test_compute_trial_id_invariante_al_orden_de_insercion() -> None:
    cfg_a = {"alpha": 1, "beta": 2}
    cfg_b = {"beta": 2, "alpha": 1}
    id_a = compute_trial_id(cfg_a, {"US500": "h"}, "firm-h", "geometry-h", "house-h")
    id_b = compute_trial_id(cfg_b, {"US500": "h"}, "firm-h", "geometry-h", "house-h")
    assert id_a == id_b


@given(
    base=st.dictionaries(
        st.text(min_size=1, max_size=8), st.integers(min_value=-100, max_value=100), min_size=1
    ),
    mutated_key=st.text(min_size=1, max_size=8),
    mutated_value=st.integers(min_value=-100, max_value=100),
)
def test_compute_trial_id_sensibilidad_total_a_candidate_config(
    base: dict[str, int], mutated_key: str, mutated_value: int
) -> None:
    mutated = dict(base)
    mutated[mutated_key] = mutated_value
    if mutated == base:
        return
    original_id = compute_trial_id(base, {"US500": "h"}, "firm-h", "geometry-h", "house-h")
    mutated_id = compute_trial_id(mutated, {"US500": "h"}, "firm-h", "geometry-h", "house-h")
    assert original_id != mutated_id


def test_compute_trial_id_sensibilidad_a_los_cuatro_hashes() -> None:
    cfg = {"alpha": 1}
    base_id = compute_trial_id(cfg, {"US500": "h1"}, "firm-h", "geometry-h", "house-h")
    assert base_id != compute_trial_id(cfg, {"US500": "h2"}, "firm-h", "geometry-h", "house-h")
    assert base_id != compute_trial_id(cfg, {"US500": "h1"}, "firm-h2", "geometry-h", "house-h")
    assert base_id != compute_trial_id(cfg, {"US500": "h1"}, "firm-h", "geometry-h2", "house-h")
    assert base_id != compute_trial_id(cfg, {"US500": "h1"}, "firm-h", "geometry-h", "house-h2")


def test_compute_trial_id_valor_no_serializable_lanza_trial_ledger_config_error() -> None:
    class _NoSerializable:
        pass

    with pytest.raises(TrialLedgerConfigError) as exc_info:
        compute_trial_id(
            {"cb": _NoSerializable()}, {"US500": "h"}, "firm-h", "geometry-h", "house-h"
        )
    assert "cb" in str(exc_info.value)


# --- T5: TrialLedgerSummary + read_trial_summary ---


def test_read_trial_summary_archivo_inexistente(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "trials.jsonl"
    summary = read_trial_summary(ledger_path)
    assert summary.n_trials_total == 0
    assert summary.n_rows == 0
    assert summary.n_trials_by_symbol == {}
    assert summary.n_trials_by_candidate_family == {}
    assert summary.n_trials_by_firm_profile_hash == {}
    assert summary.content_hash == hashlib.sha256(b"").hexdigest()
    assert ledger_path.exists() is False


def test_read_trial_summary_desgloses_consistentes(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    for index in range(4):
        append_trial(
            ledger_path,
            make_trial_record(trial_id=f"trial-{index}", symbol="US500" if index % 2 else "XAUUSD"),
        )
    summary = read_trial_summary(ledger_path)
    assert sum(summary.n_trials_by_symbol.values()) == summary.n_rows
    assert set(summary.n_trials_by_symbol) <= {"US500", "XAUUSD"}


def test_read_trial_summary_es_pura(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    append_trial(ledger_path, make_trial_record(trial_id="trial-1"))
    before_bytes = ledger_path.read_bytes()
    before_mtime = ledger_path.stat().st_mtime_ns
    read_trial_summary(ledger_path)
    read_trial_summary(ledger_path)
    assert ledger_path.read_bytes() == before_bytes
    assert ledger_path.stat().st_mtime_ns == before_mtime


def test_read_trial_summary_linea_malformada_lanza_con_numero_de_linea(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    append_trial(ledger_path, make_trial_record(trial_id="trial-1"))
    append_trial(ledger_path, make_trial_record(trial_id="trial-2"))
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("{no-json\n")
    with pytest.raises(TrialLedgerConfigError) as exc_info:
        read_trial_summary(ledger_path)
    message = str(exc_info.value)
    assert "3" in message
    assert str(ledger_path) in message


def test_read_trial_summary_trial_id_duplicado_no_lanza(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    record = make_trial_record(trial_id="dup")
    row = {
        "trial_id": record.trial_id,
        "candidate_id": record.candidate_id,
        "symbol": record.symbol,
        "outcome": record.outcome.value,
        "discard_reason": record.discard_reason,
        "config_version": record.config_version,
        "dataset_hash_by_symbol": dict(record.dataset_hash_by_symbol),
        "firm_profile_hash": record.firm_profile_hash,
        "exit_geometry_hash": record.exit_geometry_hash,
        "house_rule_hash": record.house_rule_hash,
        "git_commit": record.git_commit,
        "recorded_at_utc": record.recorded_at_utc,
    }
    line = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.write(line + "\n")
    summary = read_trial_summary(ledger_path)
    assert summary.n_rows == 2
    assert summary.n_trials_total == 1
    assert summary.n_duplicate_trial_ids == 1


def test_read_trial_summary_ignora_linea_en_blanco_final(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    append_trial(ledger_path, make_trial_record(trial_id="trial-1"))
    summary = read_trial_summary(ledger_path)
    assert summary.n_rows == 1


# --- T6: append_trial ---


def test_append_trial_cinco_registros_incluye_descartados_sin_wfa(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    records = [make_trial_record(trial_id=f"trial-{i}") for i in range(3)]
    records += [make_discarded_trial_record(trial_id=f"discarded-{i}") for i in range(2)]
    for record in records:
        append_trial(ledger_path, record)
    summary = read_trial_summary(ledger_path)
    assert summary.n_trials_total >= 5


def test_append_trial_idempotente_mismo_registro(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    record = make_trial_record(trial_id="fixed-id")
    append_trial(ledger_path, record)
    append_trial(ledger_path, record)
    summary = read_trial_summary(ledger_path)
    assert summary.n_trials_total == 1
    assert summary.n_rows == 1


def test_append_trial_incrementa_en_exactamente_uno(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    for i in range(5):
        append_trial(ledger_path, make_trial_record(trial_id=f"trial-{i}"))
    before = read_trial_summary(ledger_path).n_trials_total
    append_trial(ledger_path, make_trial_record(trial_id="trial-new"))
    after = read_trial_summary(ledger_path).n_trials_total
    assert after == before + 1


@given(trial_ids=st.lists(st.sampled_from(["a", "b", "c", "d"]), min_size=1, max_size=10))
def test_append_trial_property_conteo_de_unicos(
    tmp_path_factory: pytest.TempPathFactory, trial_ids: list[str]
) -> None:
    ledger_path = tmp_path_factory.mktemp("ledger") / "trials.jsonl"
    for trial_id in trial_ids:
        append_trial(ledger_path, make_trial_record(trial_id=trial_id))
    summary = read_trial_summary(ledger_path)
    assert summary.n_trials_total == len(set(trial_ids))


def test_append_trial_round_trip(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    record = make_trial_record(trial_id="round-trip")
    append_trial(ledger_path, record)
    line = ledger_path.read_text(encoding="utf-8").strip()
    raw = json.loads(line)
    reconstructed = TrialRecord(
        trial_id=raw["trial_id"],
        candidate_id=raw["candidate_id"],
        symbol=raw["symbol"],
        outcome=TrialOutcomeKind(raw["outcome"]),
        discard_reason=raw["discard_reason"],
        config_version=raw["config_version"],
        dataset_hash_by_symbol=raw["dataset_hash_by_symbol"],
        firm_profile_hash=raw["firm_profile_hash"],
        exit_geometry_hash=raw["exit_geometry_hash"],
        house_rule_hash=raw["house_rule_hash"],
        git_commit=raw["git_commit"],
        recorded_at_utc=raw["recorded_at_utc"],
    )
    assert reconstructed == record


def test_append_trial_bytes_en_disco_sin_crlf(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    for i in range(3):
        append_trial(ledger_path, make_trial_record(trial_id=f"trial-{i}"))
    raw_bytes = ledger_path.read_bytes()
    assert b"\r" not in raw_bytes
    assert raw_bytes.count(b"\n") == 3
    assert read_trial_summary(ledger_path).content_hash == hashlib.sha256(raw_bytes).hexdigest()


# --- T7: TrialIdentityContext + TrialLedger ---


def test_trial_ledger_trial_id_for_config_delega_en_compute_trial_id(tmp_path: Path) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}
    expected = compute_trial_id(
        cfg,
        identity.dataset_hash_by_symbol,
        identity.firm_profile_hash,
        identity.exit_geometry_hash,
        identity.house_rule_hash,
    )
    assert ledger.trial_id_for_config(cfg) == expected


def test_trial_ledger_record_y_read_summary_equivalen_a_funciones_libres(tmp_path: Path) -> None:
    ledger_path = tmp_path / "trials.jsonl"
    identity = make_trial_identity_context()
    ledger = TrialLedger(ledger_path, identity)
    record = make_trial_record(trial_id="via-ledger")
    ledger.record(record)
    append_trial(ledger_path, make_trial_record(trial_id="via-funcion-libre"))
    ledger_summary = ledger.read_summary()
    free_summary = read_trial_summary(ledger_path)
    assert ledger_summary == free_summary


def test_trial_ledger_build_record_determinista_con_recorded_at_fijo(tmp_path: Path) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}
    record_a = ledger.build_record(
        "A", "US500", cfg, TrialOutcomeKind.WFA_COMPLETADO, recorded_at_utc="2026-01-01T00:00:00Z"
    )
    record_b = ledger.build_record(
        "A", "US500", cfg, TrialOutcomeKind.WFA_COMPLETADO, recorded_at_utc="2026-01-01T00:00:00Z"
    )
    assert record_a == record_b


def test_trial_ledger_build_record_recorded_at_no_participa_del_trial_id(tmp_path: Path) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}
    record_a = ledger.build_record(
        "A", "US500", cfg, TrialOutcomeKind.WFA_COMPLETADO, recorded_at_utc="2026-01-01T00:00:00Z"
    )
    record_b = ledger.build_record(
        "A", "US500", cfg, TrialOutcomeKind.WFA_COMPLETADO, recorded_at_utc="2026-02-02T00:00:00Z"
    )
    assert record_a.trial_id == record_b.trial_id


def test_summary_dataclass_expone_los_campos_minimos() -> None:
    summary = TrialLedgerSummary(
        n_trials_total=0,
        n_rows=0,
        n_duplicate_trial_ids=0,
        trial_ids=frozenset(),
        n_trials_by_symbol={},
        n_trials_by_candidate_family={},
        n_trials_by_firm_profile_hash={},
        content_hash=hashlib.sha256(b"").hexdigest(),
    )
    assert summary.n_trials_total == 0
