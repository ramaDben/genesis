"""Tests de la jerarquía de excepciones de `genesis.validation` (R1-R5, R64)."""

import pytest

from genesis.backtest.errors import GenesisBacktestError
from genesis.data.errors import GenesisDataError
from genesis.strategy.errors import GenesisStrategyError
from genesis.validation.errors import (
    DsrPboConfigError,
    GenesisValidationError,
    MonteCarloConfigError,
    PropSimConfigError,
    PurgedCvConfigError,
    SensitivityConfigError,
    VerdictConfigError,
    WfaConfigError,
)

pytestmark = pytest.mark.unit


def test_wfa_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(WfaConfigError, GenesisValidationError) is True


def test_montecarlo_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(MonteCarloConfigError, GenesisValidationError) is True


def test_genesis_validation_error_no_hereda_de_genesis_backtest_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisBacktestError)


def test_genesis_validation_error_no_hereda_de_genesis_strategy_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisStrategyError)


def test_genesis_validation_error_no_hereda_de_genesis_data_error() -> None:
    assert not issubclass(GenesisValidationError, GenesisDataError)


def test_mensaje_con_contexto_se_conserva_en_str_wfa() -> None:
    contexto = "candidate_id=B symbol=US500 window_index=2 valor=historia_insuficiente"
    err = WfaConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_mensaje_con_contexto_se_conserva_en_str_montecarlo() -> None:
    contexto = "candidate_id=B symbol=US500 n_paths=-1"
    err = MonteCarloConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_purged_cv_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(PurgedCvConfigError, GenesisValidationError) is True


def test_dsr_pbo_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(DsrPboConfigError, GenesisValidationError) is True


def test_sensitivity_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(SensitivityConfigError, GenesisValidationError) is True


def test_mensaje_con_contexto_se_conserva_en_str_purged_cv() -> None:
    contexto = "candidate_id=B symbol=US500 fold_index=2 n_folds=5"
    err = PurgedCvConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_mensaje_con_contexto_se_conserva_en_str_dsr_pbo() -> None:
    contexto = "candidate_id=B symbol=US500 n_windows=3"
    err = DsrPboConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_mensaje_con_contexto_se_conserva_en_str_sensitivity() -> None:
    contexto = "candidate_id=B symbol=US500 axis=risk_pct"
    err = SensitivityConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_prop_sim_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(PropSimConfigError, GenesisValidationError) is True


def test_verdict_config_error_hereda_de_genesis_validation_error() -> None:
    assert issubclass(VerdictConfigError, GenesisValidationError) is True


def test_prop_sim_config_error_no_hereda_de_excepciones_de_h_i() -> None:
    assert not issubclass(PropSimConfigError, WfaConfigError)
    assert not issubclass(PropSimConfigError, MonteCarloConfigError)
    assert not issubclass(PropSimConfigError, DsrPboConfigError)


def test_verdict_config_error_no_hereda_de_excepciones_de_h_i() -> None:
    assert not issubclass(VerdictConfigError, WfaConfigError)
    assert not issubclass(VerdictConfigError, MonteCarloConfigError)
    assert not issubclass(VerdictConfigError, DsrPboConfigError)


def test_mensaje_con_contexto_se_conserva_en_str_prop_sim() -> None:
    contexto = "candidate_id=B symbol=US500 n_paths=-1"
    err = PropSimConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)


def test_mensaje_con_contexto_se_conserva_en_str_verdict() -> None:
    contexto = "candidate_id=B symbol=US500 starting_balance=-1.0"
    err = VerdictConfigError(f"Configuración inválida: {contexto}")
    assert contexto in str(err)
