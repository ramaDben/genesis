"""Tests de integración `run_verdict`/`record_trial_completions` + `TrialLedger` (Issue #53)."""

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from genesis.data.house_rule import HouseRule
from genesis.data.profile import FirmProfile
from genesis.validation._dsr import deflated_sharpe_ratio
from genesis.validation._returns import extract_trade_returns
from genesis.validation.errors import TrialLedgerConfigError
from genesis.validation.prop_sim import PropSimConfig, load_prop_economics_profile
from genesis.validation.trial_ledger import TrialLedger, TrialOutcomeKind, compute_trial_id
from genesis.validation.verdict import (
    _build_symbol_gate_outcome,
    _compute_t1,
    _find_go_parcial_candidate,
    _trial_id_for_bundle,
    build_candidate_gate_summary,
    record_trial_completions,
    run_verdict,
    verdict_result_to_manifest_json,
)
from tests.validation.fakes import (
    make_candidate_validation_bundle,
    make_dsr_pbo_result_fake,
    make_mc_symbol_result_fake,
    make_sensitivity_result_fake,
    make_trial_identity_context,
    make_wfa_result_fake,
)

pytestmark = pytest.mark.integration

_STARTING_BALANCE = 100_000.0
_FAST_ENSEMBLE_CONFIG = PropSimConfig(
    n_paths=20, seed=555, horizon_months=1, trading_days_per_month=5, path_horizon_trading_days=30
)
_MANIFEST_KWARGS: dict[str, Any] = {
    "config_version": "genesis-validation-j/2",
    "dataset_hash_by_symbol": {"US500": "hash-us500"},
    "firm_profile_hash": "firm-hash",
    "exit_geometry_hash": "exit-geometry-hash",
    "house_rule_hash": "house-rule-hash",
    "prop_economics_profile_hash_value": "economics-hash",
    "seeds": {"A": {"mc_seed": 1, "prop_sim_seed": 2}},
    "git_commit": "deadbeef",
}


def _run_verdict_single_bundle(
    firm_profile: FirmProfile,
    *,
    candidate_config: dict | None = None,
    ledger: TrialLedger | None = None,
):
    bundle = make_candidate_validation_bundle(candidate_id="A", candidate_config=candidate_config)
    candidates = {"A": bundle}
    return run_verdict(
        candidates,
        _STARTING_BALANCE,
        firm_profile,
        load_prop_economics_profile(),
        _FAST_ENSEMBLE_CONFIG,
        ledger=ledger,
    )


# --- T10 ---


def test_trial_id_for_bundle_coincide_con_compute_trial_id(tmp_path: Path) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    bundle = make_candidate_validation_bundle(candidate_config={"k": 1})
    expected = compute_trial_id(
        {"k": 1},
        identity.dataset_hash_by_symbol,
        identity.firm_profile_hash,
        identity.exit_geometry_hash,
        identity.house_rule_hash,
    )
    assert _trial_id_for_bundle(ledger, bundle) == expected


def test_run_verdict_candidate_config_none_con_ledger_lanza_trial_ledger_config_error(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    with pytest.raises(TrialLedgerConfigError) as exc_info:
        _run_verdict_single_bundle(firm_profile_fixture, candidate_config=None, ledger=ledger)
    assert "A" in str(exc_info.value)


# --- T11 ---


def test_a11_recompute_extra_cero_coincide_con_dsr_pbo_result(
    house_rule_fixture: HouseRule,
) -> None:
    """El cortocircuito de Q1 (extra=0 -> reutiliza dsr_pbo_result.dsr) no esconde divergencia:
    recomputar `deflated_sharpe_ratio` en el punto de llamada, con el mismo `n_trials`
    que ya usa `deflated_sharpe_ratio_gate` (dsr_pbo.py, sin tocar), da exactamente el
    mismo valor que el cortocircuito reutiliza verbatim (A11).
    """
    wfa_result = make_wfa_result_fake()
    returns = [trade.pnl_delta for trade in extract_trade_returns(wfa_result.oos_ledger_cosido)]
    real_dsr = deflated_sharpe_ratio(returns, n_trials=wfa_result.n_trials_signal_total)
    dsr_pbo_result = make_dsr_pbo_result_fake(dsr=real_dsr)

    outcome = _build_symbol_gate_outcome(
        "US500",
        wfa_result,
        dsr_pbo_result,
        make_sensitivity_result_fake(),
        make_mc_symbol_result_fake(),
        house_rule_fixture,
        ledger_extra_trials=0,
    )
    assert outcome.dsr == real_dsr
    assert outcome.dsr == dsr_pbo_result.dsr
    assert outcome.dsr_pre_ledger_deflation == dsr_pbo_result.dsr


@given(extra=st.integers(min_value=0, max_value=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_a10_monotonia_del_gate_g4(house_rule_fixture: HouseRule, extra: int) -> None:
    wfa_result = make_wfa_result_fake()
    dsr_pbo_result = make_dsr_pbo_result_fake()
    outcome_zero = _build_symbol_gate_outcome(
        "US500",
        wfa_result,
        dsr_pbo_result,
        make_sensitivity_result_fake(),
        make_mc_symbol_result_fake(),
        house_rule_fixture,
        ledger_extra_trials=0,
    )
    outcome_extra = _build_symbol_gate_outcome(
        "US500",
        wfa_result,
        dsr_pbo_result,
        make_sensitivity_result_fake(),
        make_mc_symbol_result_fake(),
        house_rule_fixture,
        ledger_extra_trials=extra,
    )
    assert outcome_extra.dsr <= outcome_zero.dsr
    assert outcome_zero.dsr == dsr_pbo_result.dsr


def test_a16_privadas_sin_default_publicas_con_default() -> None:
    for fn in (_build_symbol_gate_outcome, _compute_t1, _find_go_parcial_candidate):
        param = inspect.signature(fn).parameters["ledger_extra_trials"]
        assert param.default is inspect.Parameter.empty
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
    for fn, default in (
        (build_candidate_gate_summary, 0),
        (run_verdict, None),
    ):
        name = "ledger_extra_trials" if fn is build_candidate_gate_summary else "ledger"
        param = inspect.signature(fn).parameters[name]
        assert param.default == default


def test_dsr_pbo_py_sin_diff() -> None:
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--exit-code", "src/genesis/validation/dsr_pbo.py"],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0


# --- T13 ---


def test_a3_byte_identidad_ledger_none_vs_ledger_vacio(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    empty_ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}

    result_none = _run_verdict_single_bundle(
        firm_profile_fixture, candidate_config=cfg, ledger=None
    )
    result_empty = _run_verdict_single_bundle(
        firm_profile_fixture, candidate_config=cfg, ledger=empty_ledger
    )

    assert result_none.verdict == result_empty.verdict
    assert result_none.winning_candidate_id == result_empty.winning_candidate_id
    assert result_none.t1_dsr == result_empty.t1_dsr
    assert result_none.t1_dsr_pre_deflation == result_empty.t1_dsr_pre_deflation
    assert result_none.n_trials_deflactado == result_empty.n_trials_deflactado
    for candidate_id, summary in result_none.candidate_summaries.items():
        other = result_empty.candidate_summaries[candidate_id]
        for symbol, outcome in summary.symbol_gate_outcomes.items():
            other_outcome = other.symbol_gate_outcomes[symbol]
            assert outcome.g1_pass == other_outcome.g1_pass
            assert outcome.g2_pass == other_outcome.g2_pass
            assert outcome.g3_pass == other_outcome.g3_pass
            assert outcome.g4_pass == other_outcome.g4_pass
            assert outcome.g5_pass == other_outcome.g5_pass
            assert outcome.g6_pass == other_outcome.g6_pass
            assert outcome.g7_pass == other_outcome.g7_pass
            assert outcome.g8_pass == other_outcome.g8_pass
            assert outcome.g9_pass == other_outcome.g9_pass


def test_auto_exclusion_no_cuenta_el_propio_ensayo(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}

    own_id = ledger.trial_id_for_config(cfg)
    other_record_1 = ledger.build_record(
        "A", "US500", {"other": 1}, TrialOutcomeKind.WFA_COMPLETADO
    )
    other_record_2 = ledger.build_record(
        "A", "US500", {"other": 2}, TrialOutcomeKind.WFA_COMPLETADO
    )
    own_record = ledger.build_record("A", "US500", cfg, TrialOutcomeKind.WFA_COMPLETADO)
    assert own_record.trial_id == own_id
    ledger.record(other_record_1)
    ledger.record(other_record_2)
    ledger.record(own_record)

    result = _run_verdict_single_bundle(firm_profile_fixture, candidate_config=cfg, ledger=ledger)
    assert result.ledger_extra_trials == 2


def test_a17_run_verdict_no_escribe(firm_profile_fixture: FirmProfile, tmp_path: Path) -> None:
    identity = make_trial_identity_context()
    ledger_path = tmp_path / "trials.jsonl"
    ledger = TrialLedger(ledger_path, identity)
    ledger.record(ledger.build_record("Z", "US500", {"z": 1}, TrialOutcomeKind.WFA_COMPLETADO))

    before_bytes = ledger_path.read_bytes()
    before_mtime = ledger_path.stat().st_mtime_ns

    _run_verdict_single_bundle(firm_profile_fixture, candidate_config={"alpha": 1}, ledger=ledger)

    assert ledger_path.read_bytes() == before_bytes
    assert ledger_path.stat().st_mtime_ns == before_mtime


def test_run_verdict_idempotente_sobre_el_mismo_ledger(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    ledger.record(ledger.build_record("Z", "US500", {"z": 1}, TrialOutcomeKind.WFA_COMPLETADO))

    cfg = {"alpha": 1}
    result_1 = _run_verdict_single_bundle(firm_profile_fixture, candidate_config=cfg, ledger=ledger)
    result_2 = _run_verdict_single_bundle(firm_profile_fixture, candidate_config=cfg, ledger=ledger)
    assert result_1.verdict == result_2.verdict
    assert result_1.n_trials_deflactado == result_2.n_trials_deflactado
    assert result_1.ledger_extra_trials == result_2.ledger_extra_trials


# --- T14 ---


def test_a18_record_trial_completions_un_intento_por_candidato_symbol(tmp_path: Path) -> None:
    """A18 (R15 enmendado): `record_trial_completions` intenta un `TrialRecord` por cada
    `(candidate_id, symbol)` evaluado, en orden canónico de `candidate_id`. Con símbolos
    distintos por candidato (configuraciones distintas, caso realista) las 4 filas persisten
    tal cual.
    """
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    candidates = {
        "B": make_candidate_validation_bundle(
            candidate_id="B", symbols=("US500",), candidate_config={"b": 1}
        ),
        "A": make_candidate_validation_bundle(
            candidate_id="A", symbols=("US500",), candidate_config={"a": 1}
        ),
    }

    trial_ids = record_trial_completions(ledger, candidates)

    assert len(trial_ids) == 2
    lines = ledger.ledger_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert all(row["outcome"] == "wfa-completado" for row in rows)
    assert all(row["discard_reason"] is None for row in rows)
    candidate_ids_in_rows = [row["candidate_id"] for row in rows]
    assert candidate_ids_in_rows == sorted(candidate_ids_in_rows)
    assert trial_ids[0] == rows[0]["trial_id"]


def test_record_trial_completions_config_compartida_entre_simbolos_deduplica_por_trial_id(
    tmp_path: Path,
) -> None:
    """`trial_id` se deriva solo de `candidate_config` + identidad institucional (Q5/PR-2), no
    de `symbol`: un candidato con la MISMA config evaluada en 2 símbolos es, por definición
    (Q4: "un trial = una configuración evaluada"), UN solo ensayo -> R8 lo deduplica a una
    fila, sin perder el intento por símbolo (2 llamadas, 1 fila persistida).
    """
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    candidates = {
        "A": make_candidate_validation_bundle(
            candidate_id="A", symbols=("US500", "XAUUSD"), candidate_config={"a": 1}
        ),
    }

    trial_ids = record_trial_completions(ledger, candidates)

    assert len(trial_ids) == 2
    assert trial_ids[0] == trial_ids[1]
    lines = ledger.ledger_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1


def test_a9_idempotencia_fuerte_ciclo_completo(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    cfg = {"alpha": 1}
    bundle = make_candidate_validation_bundle(candidate_id="A", candidate_config=cfg)
    candidates = {"A": bundle}

    def _cycle():
        result = run_verdict(
            candidates,
            _STARTING_BALANCE,
            firm_profile_fixture,
            load_prop_economics_profile(),
            _FAST_ENSEMBLE_CONFIG,
            ledger=ledger,
        )
        record_trial_completions(ledger, candidates)
        return result

    result_1 = _cycle()
    n_rows_after_first = ledger.read_summary().n_rows
    result_2 = _cycle()
    n_rows_after_second = ledger.read_summary().n_rows

    assert result_1.verdict == result_2.verdict
    assert result_1.n_trials_deflactado == result_2.n_trials_deflactado
    assert n_rows_after_first == n_rows_after_second


# --- T15 ---


def test_a6_manifest_incluye_trial_ledger_con_n_y_content_hash(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    ledger.record(ledger.build_record("Z", "US500", {"z": 1}, TrialOutcomeKind.WFA_COMPLETADO))

    result = _run_verdict_single_bundle(
        firm_profile_fixture, candidate_config={"alpha": 1}, ledger=ledger
    )
    manifest_raw = verdict_result_to_manifest_json(result, **_MANIFEST_KWARGS)
    payload = json.loads(manifest_raw)

    assert "trial_ledger" in payload
    assert payload["trial_ledger"]["n_trials_total"] == result.trial_ledger_snapshot.n_trials_total
    assert payload["trial_ledger"]["content_hash"] == result.trial_ledger_snapshot.content_hash
    for key in ("config_version", "verdict", "winning_candidate_id", "candidates", "seeds"):
        assert key in payload


def test_a13_manifest_ledger_none_no_incluye_trial_ledger(
    firm_profile_fixture: FirmProfile,
) -> None:
    result_none = _run_verdict_single_bundle(
        firm_profile_fixture, candidate_config=None, ledger=None
    )
    manifest_raw = verdict_result_to_manifest_json(result_none, **_MANIFEST_KWARGS)
    payload = json.loads(manifest_raw)
    assert "trial_ledger" not in payload


def test_tearsheet_manifest_paridad_ledger(
    firm_profile_fixture: FirmProfile, tmp_path: Path
) -> None:
    from genesis.validation.verdict import render_tearsheet

    identity = make_trial_identity_context()
    ledger = TrialLedger(tmp_path / "trials.jsonl", identity)
    ledger.record(ledger.build_record("Z", "US500", {"z": 1}, TrialOutcomeKind.WFA_COMPLETADO))

    result = _run_verdict_single_bundle(
        firm_profile_fixture, candidate_config={"alpha": 1}, ledger=ledger
    )
    tearsheet = render_tearsheet(result)
    manifest_raw = verdict_result_to_manifest_json(result, **_MANIFEST_KWARGS)
    payload = json.loads(manifest_raw)

    assert str(payload["trial_ledger"]["n_trials_total"]) in tearsheet
    assert payload["trial_ledger"]["content_hash"] in tearsheet
