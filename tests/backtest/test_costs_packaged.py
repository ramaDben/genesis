"""El JSON de costos empaquetado trae exactamente las cinco filas firmadas (Change #135).

Único archivo de la suite, junto con `test_costs.py`, autorizado a cargar el recurso
empaquetado (E19.1). Las cifras de `round_trip_usd` y la fecha de lectura son las de
`.pulse/changes/135-.../firma-cifras.md`, firmadas por el dueño el 2026-10-05 (R23).
"""

import json
import re
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import pytest

from genesis.backtest.costs import (
    FrictionStatus,
    commission_for,
    costs_hash,
    load_costs_config,
    slippage_for,
    spread_for,
)
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.exit_geometry import load_exit_geometry
from genesis.backtest.simulator import Simulator
from genesis.data.profile import load_firm_profile
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.backtest.fakes import FakeRiskCandidate
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_URL = "https://help.myfundedfutures.com/en/articles/9735811"
_READ_ON = "2026-10-05"
_T1 = {"M6E": 1.44, "MBT": 3.50, "MCL": 1.16, "MGC": 2.20, "MNQ": 1.90}
_TS = datetime(2026, 10, 5, tzinfo=UTC)
_MNQ_FIGURE = _default_symbol_figure("MNQ", tick_value=0.5, tick_size=0.25)


def _raw_text() -> str:
    resource = resources.files("genesis.backtest").joinpath("costs_config.json")
    return resource.read_text(encoding="utf-8")


def test_load_costs_config_empaquetado_trae_exactamente_las_cinco_filas() -> None:
    config = load_costs_config()
    assert config.symbols == ("M6E", "MBT", "MCL", "MGC", "MNQ")
    for row in config.instruments:
        assert row.round_trip_usd == _T1[row.symbol]
        assert row.spread_ticks == 1.0
        assert row.slippage_ticks == 1.0
        assert row.friction_status is FrictionStatus.PROVISIONAL_HASTA_B4B
        assert row.source_url == _SOURCE_URL
        assert row.read_on == _READ_ON
    assert json.loads(_raw_text())["_nota"].strip()


def test_json_empaquetado_sin_simbolos_de_cfd_ni_de_test() -> None:
    text = _raw_text()
    assert text.count('"round_trip_usd"') == 5
    pattern = r"US500|NAS100|US30|GER40|XAUUSD|EURUSD|GBPUSD|USDJPY|BTCUSDT|SYM_|TEST"
    assert re.search(pattern, text) is None


def _python_files(*roots: str) -> list[Path]:
    return [path for root in roots for path in sorted((_REPO_ROOT / root).rglob("*.py"))]


def test_sin_campos_globales_heredados() -> None:
    """E1.1: los tres globales del modelo anterior no quedan en el código."""
    global_fields = re.compile(r"commission_per_lot|default_spread_points")
    slippage_global = re.compile(r"config\.slippage_points|\"slippage_points\"")
    for path in _python_files("src", "scripts"):
        assert global_fields.search(path.read_text(encoding="utf-8")) is None, path
    for path in [*_python_files("src"), _REPO_ROOT / "src/genesis/backtest/costs_config.json"]:
        text = path.read_text(encoding="utf-8")
        assert global_fields.search(text) is None, path
        assert slippage_global.search(text) is None, path


def test_sin_valores_heredados_de_cfd() -> None:
    """E19.3: ni el módulo de costos ni el JSON escriben los valores del modelo de CFD."""
    legacy_values = re.compile(r"1\.5|7\.0|0\.2")
    for relative in ("src/genesis/backtest/costs.py", "src/genesis/backtest/costs_config.json"):
        text = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        assert legacy_values.search(text) is None, relative


def test_clave_de_simbolo_es_exacta() -> None:
    with pytest.raises(BacktestConfigError, match="'mnq'"):
        load_costs_config().instrument("mnq")


def test_commission_for_mnq_ida_y_vuelta_es_1_90() -> None:
    config = load_costs_config()
    leg = commission_for("MNQ", 1.0, config)
    assert leg == 0.95
    assert leg + commission_for("MNQ", 1.0, config) == 1.90


def test_commission_for_mgc_ida_y_vuelta_es_2_20() -> None:
    config = load_costs_config()
    leg = commission_for("MGC", 1.0, config)
    assert leg == 1.10
    assert leg + commission_for("MGC", 1.0, config) == 2.20


@pytest.mark.parametrize("symbol", sorted(_T1))
def test_commission_for_tabla_completa_pata_mas_pata(symbol: str) -> None:
    config = load_costs_config()
    assert commission_for(symbol, 1.0, config) + commission_for(symbol, 1.0, config) == _T1[symbol]


def test_golden_mnq_spread_un_tick() -> None:
    spread = spread_for("MNQ", _TS, _MNQ_FIGURE, None, load_costs_config())
    assert spread == 0.25
    assert spread * 1.0 * _MNQ_FIGURE.value_per_point == 0.50


def test_golden_mnq_deslizamiento_un_tick() -> None:
    slippage = slippage_for("MNQ", _MNQ_FIGURE, load_costs_config())
    assert slippage == 0.25
    assert slippage * 1.0 * _MNQ_FIGURE.value_per_point == 0.50


def test_golden_mnq_costo_total_ida_y_vuelta() -> None:
    """E21.1: comisión + 1 tick de spread + 1 tick de deslizamiento por pata = $3,40."""
    config = load_costs_config()
    commission = 2 * commission_for("MNQ", 1.0, config)
    spread = spread_for("MNQ", _TS, _MNQ_FIGURE, None, config)
    slippage = slippage_for("MNQ", _MNQ_FIGURE, config)
    total = commission + (spread + 2 * slippage) * 1.0 * _MNQ_FIGURE.value_per_point
    assert total == pytest.approx(3.40)


def test_costs_hash_mnq_golden() -> None:
    assert (
        costs_hash("MNQ", load_costs_config())
        == "6b5b237b9be9f6488049b7f34240b2cce3107c80e965d51f61cce409f8c81d1b"
    )


def test_costs_config_empaquetada_es_hasheable_y_comparable() -> None:
    """E12.2 sobre el recurso empaquetado (variante literal del spec, H-1 de tasks.md)."""
    a = load_costs_config()
    b = load_costs_config()
    assert a == b
    assert hash(a) == hash(b)
    assert {a: 1}[b] == 1


@pytest.mark.parametrize("symbol", ["US500", "BTCUSDT"])
def test_json_empaquetado_no_trae_filas_de_cfd_ni_de_cripto(symbol: str) -> None:
    with pytest.raises(BacktestConfigError) as excinfo:
        Simulator(
            FakeRiskCandidate(),
            symbol=symbol,
            firm_profile=load_firm_profile(),
            exit_geometry=load_exit_geometry(),
            figure=_default_symbol_figure(symbol),
            funnel_config=InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=10.0),
            costs_config=load_costs_config(),
            news_events=[],
            tick_store=None,
            starting_balance=100_000.0,
            dataset_hash="test-dataset-hash",
        )
    assert "['M6E', 'MBT', 'MCL', 'MGC', 'MNQ']" in str(excinfo.value)
