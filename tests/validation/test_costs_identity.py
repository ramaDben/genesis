"""Puente capa 3 -> capa 4 de la huella de costos (Change #135, R13-R15).

La huella que calcula `genesis.backtest.costs.costs_hash` llega a la procedencia del WFA y,
como mapa por símbolo, a la identidad del ensayo. La cita (`source_url`/`read_on`) y la fila
de un símbolo no evaluado no cambian el `trial_id`.
"""

import inspect

import pytest

from genesis.backtest.costs import CostsConfig, costs_hash
from genesis.validation.wfa import WfaResult, run_wfa

pytestmark = pytest.mark.unit


def test_wfa_provenance_trae_costs_hash(
    wfa_result_fixture: WfaResult, costs_config_fixture: CostsConfig
) -> None:
    provenance = wfa_result_fixture.oos_ledger_cosido.provenance
    assert provenance.costs_hash == costs_hash("US500", costs_config_fixture)


def test_run_wfa_conserva_su_firma() -> None:
    assert list(inspect.signature(run_wfa).parameters) == [
        "candidate_id",
        "symbol",
        "frame",
        "firm_profile",
        "exit_geometry",
        "figure",
        "funnel_config",
        "costs_config",
        "news_events",
        "dataset_store",
        "tick_store",
        "starting_balance",
        "window_config",
        "grid_config",
        "candidate_factory",
        "seed",
    ]
