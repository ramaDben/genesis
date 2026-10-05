"""Puente capa 3 -> capa 4 de la huella de costos (Change #135, R13-R15).

La huella que calcula `genesis.backtest.costs.costs_hash` llega a la procedencia del WFA y,
como mapa por símbolo, a la identidad del ensayo. La cita (`source_url`/`read_on`) y la fila
de un símbolo no evaluado no cambian el `trial_id`.
"""

import dataclasses
import inspect

import pytest

from genesis.backtest.costs import CostsConfig, costs_hash
from genesis.validation.trial_ledger import compute_trial_id
from genesis.validation.wfa import WfaResult, run_wfa
from tests.backtest.fakes import make_costs_config, make_instrument_costs

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


def _trial_id_on_mnq(config: CostsConfig) -> str:
    """`trial_id` de una corrida solo sobre `MNQ`, con la huella derivada por `costs_hash`."""
    return compute_trial_id(
        {"alpha": 1},
        {"MNQ": "dataset-h"},
        "firm-h",
        "geometry-h",
        "house-h",
        {"MNQ": costs_hash("MNQ", config)},
    )


def test_cita_distinta_no_es_otro_ensayo() -> None:
    row = make_instrument_costs("MNQ", round_trip_usd=1.9, spread_ticks=1, slippage_ticks=1)
    reread = dataclasses.replace(
        row, source_url="https://otra-fuente.invalid/x", read_on="2026-12-01"
    )
    assert _trial_id_on_mnq(make_costs_config(row)) == _trial_id_on_mnq(make_costs_config(reread))


def test_fila_de_otro_simbolo_no_cambia_el_trial_id() -> None:
    mnq = make_instrument_costs("MNQ", round_trip_usd=1.9)
    a = make_costs_config(mnq, make_instrument_costs("MGC", round_trip_usd=2.2))
    b = make_costs_config(mnq, make_instrument_costs("MGC", round_trip_usd=9.9))
    assert _trial_id_on_mnq(a) == _trial_id_on_mnq(b)
