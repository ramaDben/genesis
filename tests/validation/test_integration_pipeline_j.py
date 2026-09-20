"""Integración del pipeline de Issue J: `run_prop_sim` -> `run_verdict` -> escritura.

Patrón `tests/validation/test_integration_pipeline_i.py`: ejercita el flujo real
de extremo a extremo sobre fixtures sintéticas pequeñas (`oos_ledgers_by_symbol_
fixture`), sin mocks de las capas internas, en segundos. También verifica la
paridad de canasta diaria entre `prop_sim._build_daily_basket` y la lógica
interna de `verdict.py` (Rg-5): ambas comparten la misma implementación
(`_candidate_daily_basket` delega en `_build_daily_basket`), garantizando que
T1/T2 y `run_prop_sim` nunca diverjan sobre los mismos ledgers.
"""

import json
import math

import pytest

from genesis.backtest.ledger import Ledger
from genesis.data.profile import FirmProfile
from genesis.validation import (
    CandidateValidationBundle,
    VerdictResult,
    load_prop_economics_profile,
    run_prop_sim,
    run_verdict,
    write_verdict_artifacts,
)
from genesis.validation.dsr_pbo import CscvResult, DsrPboResult
from genesis.validation.montecarlo import McPathsResult, McPortfolioResult, McSymbolResult
from genesis.validation.prop_sim import PropSimConfig, _build_daily_basket
from genesis.validation.sensitivity import CostStressOutcome, PerturbationOutcome, SensitivityResult
from genesis.validation.verdict import _candidate_daily_basket
from genesis.validation.wfa import WfaResult

pytestmark = pytest.mark.integration

_FAST_CONFIG = PropSimConfig(
    n_paths=50, seed=321, horizon_months=2, trading_days_per_month=10, path_horizon_trading_days=100
)


def _synthetic_dsr_pbo_result(symbol: str) -> DsrPboResult:
    return DsrPboResult(
        candidate_id="B",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        dsr=0.98,
        n_trials_signal_total=45,
        pbo=0.1,
        cscv=CscvResult(pbo=0.1, n_splits=4, n_combinations=6, logit_by_combination=[0.1] * 6),
    )


def _synthetic_sensitivity_result(symbol: str) -> SensitivityResult:
    return SensitivityResult(
        candidate_id="B",
        symbol=symbol,
        config_version="genesis-validation-i/1",
        baseline_profit_factor=1.4,
        perturbations=[
            PerturbationOutcome(
                axis="n_minutes",
                direction=1,
                perturbed_value=10.0,
                profit_factor=1.3,
                relative_drop=0.1,
                is_cliff=False,
            )
        ],
        cost_stress=[
            CostStressOutcome(multiplier=1.5, profit_factor=1.5),
            CostStressOutcome(multiplier=2.0, profit_factor=1.4),
        ],
        has_cliff=False,
    )


def _synthetic_mc_paths_result() -> McPathsResult:
    import numpy as np

    return McPathsResult(
        max_drawdown_per_path=np.array([1_000.0]),
        breach_per_path=np.array([False]),
        max_drawdown_p95=1_000.0,
        breach_probability=0.01,
        seed=1,
        n_paths=1,
        block_size=5,
    )


def _synthetic_mc_symbol_result(symbol: str, provenance) -> McSymbolResult:
    return McSymbolResult(
        symbol=symbol,
        provenance=provenance,
        reshuffle=_synthetic_mc_paths_result(),
        block_bootstrap=_synthetic_mc_paths_result(),
    )


def _build_candidate_bundle(
    candidate_id: str,
    oos_ledgers_by_symbol: dict[str, Ledger],
    starting_balance: float,
    firm_profile: FirmProfile,
) -> CandidateValidationBundle:
    """Bundle sintético (G4/G5/G8/G9 trivialmente en verde) sobre ledgers reales de la fixture."""
    wfa_by_symbol = {
        symbol: WfaResult(
            candidate_id=candidate_id,
            symbol=symbol,
            config_version="genesis-validation/1",
            windows=[],
            oos_ledger_cosido=ledger,
            wfe=0.6,
            n_windows=5,
            n_trials_signal_total=45,
            n_trials_execution_total=135,
            seed=1,
        )
        for symbol, ledger in oos_ledgers_by_symbol.items()
    }
    prop_sim_result = run_prop_sim(
        oos_ledgers_by_symbol,
        starting_balance,
        firm_profile,
        load_prop_economics_profile(),
        _FAST_CONFIG,
        candidate_id,
    )
    provenance = next(iter(oos_ledgers_by_symbol.values())).provenance
    return CandidateValidationBundle(
        candidate_id=candidate_id,
        wfa_results_by_symbol=wfa_by_symbol,
        dsr_pbo_results_by_symbol={s: _synthetic_dsr_pbo_result(s) for s in oos_ledgers_by_symbol},
        sensitivity_results_by_symbol={
            s: _synthetic_sensitivity_result(s) for s in oos_ledgers_by_symbol
        },
        mc_symbol_results_by_symbol={
            s: _synthetic_mc_symbol_result(s, provenance) for s in oos_ledgers_by_symbol
        },
        mc_portfolio_result=McPortfolioResult(
            provenance_by_symbol={s: provenance for s in oos_ledgers_by_symbol},
            block_bootstrap=_synthetic_mc_paths_result(),
        ),
        prop_sim_result=prop_sim_result,
    )


def test_pipeline_completo_run_prop_sim_run_verdict_write_artifacts(
    firm_profile_fixture: FirmProfile,
    oos_ledgers_by_symbol_fixture: dict[str, Ledger],
    tmp_path,
) -> None:
    """R112: pipeline completo en segundos; artefactos no vacíos, métricas finitas."""
    starting_balance = 100_000.0
    bundle = _build_candidate_bundle(
        "B",
        oos_ledgers_by_symbol_fixture,
        starting_balance,
        firm_profile_fixture,
    )
    candidates = {"B": bundle}

    result = run_verdict(
        candidates,
        starting_balance,
        firm_profile_fixture,
        load_prop_economics_profile(),
        _FAST_CONFIG,
    )
    assert isinstance(result, VerdictResult)
    assert math.isfinite(result.candidate_summaries["B"].c1_fraction_passing)

    manifest_path, tearsheet_path = write_verdict_artifacts(
        result,
        tmp_path / "artifacts",
        config_version="genesis-validation-j/2",
        dataset_hash_by_symbol={"US500": "hash", "NAS100": "hash"},
        firm_profile_hash="firm-hash",
        exit_geometry_hash="exit-geometry-hash",
        house_rule_hash="house-rule-hash",
        prop_economics_profile_hash_value="econ-hash",
        seeds={"B": {"mc_seed": 1, "prop_sim_seed": _FAST_CONFIG.seed}},
        git_commit="deadbeef",
    )

    assert manifest_path.exists()
    assert tearsheet_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["verdict"] == result.verdict.value
    assert len(tearsheet_path.read_text(encoding="utf-8")) > 0


def test_paridad_canasta_prop_sim_vs_verdict(
    firm_profile_fixture: FirmProfile,
    oos_ledgers_by_symbol_fixture: dict[str, Ledger],
) -> None:
    """Rg-5: la canasta de `verdict._candidate_daily_basket` == `prop_sim._build_daily_basket`."""
    bundle = _build_candidate_bundle(
        "B", oos_ledgers_by_symbol_fixture, 100_000.0, firm_profile_fixture
    )

    basket_days_prop_sim, daily_totals_prop_sim = _build_daily_basket(oos_ledgers_by_symbol_fixture)
    basket_days_verdict, daily_totals_verdict = _candidate_daily_basket(bundle)

    assert basket_days_prop_sim == basket_days_verdict
    assert daily_totals_prop_sim == daily_totals_verdict


def _load_run_pipeline_module():
    """Carga `scripts/run_pipeline.py` como módulo, sin depender de `sys.path` (E2b, I-5).

    `scripts/` no está en `pythonpath` de pytest (solo `src`, `pyproject.toml`):
    se carga por ruta explícita, patrón estándar de `importlib.util` para
    ejercitar un script como si fuera un módulo, sin tocar la configuración de
    pytest para un único test.
    """
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_pipeline_under_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_starting_balance_debe_coincidir_con_account_size(
    firm_profile_fixture: FirmProfile,
) -> None:
    """Eval I-5 (D3b, E2b): `--starting-balance` distinto de `account_size` falla ruidoso."""
    run_pipeline = _load_run_pipeline_module()
    assert firm_profile_fixture.house_rule is not None
    account_size = firm_profile_fixture.house_rule.account_size  # the5ers: 100_000.0

    with pytest.raises(SystemExit) as excinfo:
        run_pipeline._resolve_starting_balance(account_size * 2.0, firm_profile_fixture)
    message = str(excinfo.value)
    assert str(account_size) in message
    assert str(account_size * 2.0) in message

    resolved = run_pipeline._resolve_starting_balance(account_size, firm_profile_fixture)
    assert resolved == account_size
