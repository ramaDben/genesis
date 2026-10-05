"""Tests del modelo de costos por instrumento con `stress` de primera clase (R37–R41; #135).

Ningún test de este archivo carga el recurso empaquetado: sus cifras se fijan en
`test_costs_packaged.py`. Acá se usa la tabla de test (`tests/backtest/fixtures/`) o filas
armadas con `make_costs_config`.
"""

import dataclasses
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from genesis.backtest.costs import (
    CostsConfig,
    FrictionStatus,
    InstrumentCosts,
    commission_for,
    costs_hash,
    load_costs_config,
    slippage_for,
    spread_for,
    swap_for,
)
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ticks import TickRow
from genesis.data.symbols import SymbolFigure
from tests.backtest.fakes import (
    TEST_COSTS_CONFIG_PATH,
    load_test_costs_config,
    make_costs_config,
    make_instrument_costs,
)

pytestmark = pytest.mark.unit

_FIGURE = SymbolFigure(
    symbol="US500",
    tick_value=1.0,
    tick_size=1.0,
    volume_step=0.01,
    stops_level=10,
    freeze_level=5,
    digits=2,
    swap_long=-2.0,
    swap_short=-1.5,
    swap_rollover_day=3,
)

_CONFIG = load_test_costs_config()
_TS = datetime(2024, 1, 2, tzinfo=UTC)
_TICKS = [
    TickRow(timestamp_utc=datetime(2024, 1, 2, tzinfo=UTC), bid=100.0, ask=100.2, last=100.1),
    TickRow(timestamp_utc=datetime(2024, 1, 2, tzinfo=UTC), bid=100.0, ask=100.4, last=100.1),
]


def _figure(*, tick_value: float, tick_size: float) -> SymbolFigure:
    return dataclasses.replace(_FIGURE, tick_value=tick_value, tick_size=tick_size)


def _row_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "symbol": "MNQ",
        "round_trip_usd": 1.9,
        "spread_ticks": 1.0,
        "slippage_ticks": 1.0,
        "friction_status": "provisional_hasta_b4b",
        "source_url": "https://costos-de-prueba.invalid/genesis-tests",
        "read_on": "2026-10-02",
    }
    base.update(overrides)
    return base


# --- spread_for ---------------------------------------------------------------------------


def test_spread_for_stress_duplica_el_costo() -> None:
    base = spread_for("US500", _TS, _FIGURE, None, _CONFIG)
    stressed = spread_for("US500", _TS, _FIGURE, None, _CONFIG, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_spread_for_sin_ticks_usa_spread_ticks_por_tick_size() -> None:
    config = make_costs_config(make_instrument_costs("MNQ", spread_ticks=2.0))
    figure = _figure(tick_value=0.5, tick_size=0.25)
    assert spread_for("MNQ", _TS, figure, None, config) == 0.5


def test_spread_for_con_ticks_usa_mediana_de_ask_menos_bid() -> None:
    value = spread_for("US500", _TS, _FIGURE, _TICKS, _CONFIG)
    assert value == pytest.approx(0.3)


def test_spread_for_con_ticks_escala_con_stress() -> None:
    value = spread_for("US500", _TS, _FIGURE, _TICKS, _CONFIG, stress=2.0)
    assert value == pytest.approx(0.6)


def test_spread_for_simbolo_sin_fila_falla_con_ticks() -> None:
    with pytest.raises(BacktestConfigError, match="NOPE"):
        spread_for("NOPE", _TS, _FIGURE, _TICKS, _CONFIG)


# --- commission_for -----------------------------------------------------------------------


def test_commission_for_stress_duplica_el_costo() -> None:
    base = commission_for("US500", 1.0, _CONFIG)
    stressed = commission_for("US500", 1.0, _CONFIG, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_commission_for_es_lineal_en_contratos() -> None:
    one = commission_for("US500", 1.0, _CONFIG)
    three = commission_for("US500", 3.0, _CONFIG)
    assert three == pytest.approx(3 * one)


def test_commission_for_cobra_la_mitad_por_pata() -> None:
    config = make_costs_config(make_instrument_costs("MNQ", round_trip_usd=1.9))
    leg = commission_for("MNQ", 1.0, config)
    assert leg == 0.95
    assert leg + leg == 1.9


# --- slippage_for -------------------------------------------------------------------------


def test_slippage_for_stress_duplica_el_costo() -> None:
    config = make_costs_config(make_instrument_costs("US500", slippage_ticks=1.0))
    base = slippage_for("US500", _FIGURE, config)
    stressed = slippage_for("US500", _FIGURE, config, stress=2.0)
    assert base > 0
    assert stressed == pytest.approx(base * 2.0)


# --- swap_for (sin modificación, E8.2) ----------------------------------------------------


def test_swap_for_stress_duplica_el_costo() -> None:
    base = swap_for("US500", 1, _FIGURE, is_long=True)
    stressed = swap_for("US500", 1, _FIGURE, is_long=True, stress=2.0)
    assert stressed == pytest.approx(base * 2.0)


def test_swap_for_triple_en_dia_de_rollover_vs_dia_ordinario() -> None:
    ordinario = swap_for("US500", 1, _FIGURE, is_long=True)
    rollover = swap_for("US500", _FIGURE.swap_rollover_day, _FIGURE, is_long=True)
    assert rollover == pytest.approx(ordinario * 3.0)


# --- R9: símbolo sin fila -----------------------------------------------------------------

_MNQ_MGC = make_costs_config(make_instrument_costs("MNQ"), make_instrument_costs("MGC"))

_MISSING_ROW_CALLS: dict[str, Callable[[], object]] = {
    "commission_for": lambda: commission_for("NOPE", 1.0, _MNQ_MGC),
    "spread_for": lambda: spread_for("NOPE", _TS, _FIGURE, None, _MNQ_MGC),
    "slippage_for": lambda: slippage_for("NOPE", _FIGURE, _MNQ_MGC),
    "costs_hash": lambda: costs_hash("NOPE", _MNQ_MGC),
}


@pytest.mark.parametrize("function", sorted(_MISSING_ROW_CALLS))
def test_simbolo_sin_fila_falla_con_contexto(function: str) -> None:
    with pytest.raises(BacktestConfigError) as excinfo:
        _MISSING_ROW_CALLS[function]()
    message = str(excinfo.value)
    assert "'NOPE'" in message
    assert message.index("MGC") < message.index("MNQ")
    assert "sin valor de respaldo" in message.lower()


# --- R3: carga y construcción -------------------------------------------------------------


def _fixture_payload() -> dict:
    return json.loads(TEST_COSTS_CONFIG_PATH.read_text(encoding="utf-8"))


def _mutate_row(field: str, value: object) -> Callable[[dict], None]:
    def mutate(payload: dict) -> None:
        payload["instruments"]["US500"][field] = value

    return mutate


def _drop_row_field(field: str) -> Callable[[dict], None]:
    def mutate(payload: dict) -> None:
        del payload["instruments"]["US500"][field]

    return mutate


# Cada caso: (id, mutación del payload o texto crudo, fragmentos que el mensaje debe nombrar).
_LOAD_CASES: list[tuple[str, object, tuple[str, ...]]] = [
    ("T-a-json-ilegible", "{no es json", ("JSON",)),
    ("T-b-raiz-no-objeto", "[1, 2]", ("raíz",)),
    ("T-c-falta-instruments", '{"_nota": "x"}', ("instruments",)),
    ("T-c-instruments-no-objeto", '{"instruments": [1]}', ("instruments",)),
    ("T-d-instruments-vacio", '{"instruments": {}}', ("vacío",)),
    ("T-e-clave-desconocida", '{"instruments": {}, "otra": 1}', ("otra",)),
    (
        "T-f-simbolo-duplicado",
        '{"instruments": {"US500": {}, "US500": {}}}',
        ("US500", "duplicada"),
    ),
    ("T-g-simbolo-con-espacios", None, ("' US500'", "symbol")),
    ("F-a-fila-no-objeto", None, ("US500", "fila")),
    ("F-b-falta-campo", _drop_row_field("read_on"), ("US500", "read_on")),
    ("F-c-campo-desconocido", _mutate_row("extra", 1), ("US500", "extra")),
    ("F-c-comentario-en-fila", _mutate_row("_nota", "x"), ("US500", "_nota")),
    ("F-d-cero", _mutate_row("round_trip_usd", 0), ("US500", "round_trip_usd")),
    ("F-d-negativo", _mutate_row("round_trip_usd", -1), ("US500", "round_trip_usd")),
    ("F-d-nan", _mutate_row("round_trip_usd", "<NaN>"), ("US500", "round_trip_usd")),
    ("F-d-infinito", _mutate_row("round_trip_usd", "<Infinity>"), ("US500", "round_trip_usd")),
    ("F-d-cadena", _mutate_row("round_trip_usd", "1.9"), ("US500", "round_trip_usd")),
    ("F-d-true", _mutate_row("round_trip_usd", True), ("US500", "round_trip_usd")),
    ("F-d-null", _mutate_row("round_trip_usd", None), ("US500", "round_trip_usd")),
    ("F-e-negativo", _mutate_row("spread_ticks", -1), ("US500", "spread_ticks")),
    ("F-e-nan", _mutate_row("slippage_ticks", "<NaN>"), ("US500", "slippage_ticks")),
    ("F-e-cadena", _mutate_row("slippage_ticks", "1"), ("US500", "slippage_ticks")),
    ("F-e-lista", _mutate_row("spread_ticks", [1]), ("US500", "spread_ticks")),
    ("F-f-fuera-del-conjunto", _mutate_row("friction_status", "medido"), ("friction_status",)),
    ("F-g-vacia", _mutate_row("source_url", ""), ("US500", "source_url")),
    ("F-g-espacios", _mutate_row("source_url", "  "), ("US500", "source_url")),
    ("F-g-http", _mutate_row("source_url", "http://x"), ("US500", "source_url")),
    ("F-g-sin-host", _mutate_row("source_url", "https://"), ("US500", "source_url")),
    ("F-h-formato", _mutate_row("read_on", "02-10-2026"), ("US500", "read_on")),
    ("F-h-fecha-imposible", _mutate_row("read_on", "2026-02-30"), ("US500", "read_on")),
]


def _raw_text_for(case_id: str, mutation: object) -> str:
    if isinstance(mutation, str):
        return mutation
    payload = _fixture_payload()
    if case_id == "T-g-simbolo-con-espacios":
        payload["instruments"][" US500"] = payload["instruments"].pop("US500")
    elif case_id == "F-a-fila-no-objeto":
        payload["instruments"]["US500"] = [1, 2]
    else:
        assert callable(mutation)
        mutation(payload)
    # Los literales no estándar de JSON (NaN, Infinity) se inyectan sobre un marcador.
    return json.dumps(payload).replace('"<NaN>"', "NaN").replace('"<Infinity>"', "Infinity")


@pytest.mark.parametrize(
    ("case_id", "mutation", "expected"),
    _LOAD_CASES,
    ids=[case[0] for case in _LOAD_CASES],
)
def test_load_costs_config_rechaza(
    tmp_path: Path, case_id: str, mutation: object, expected: tuple[str, ...]
) -> None:
    path = tmp_path / "costs_config.json"
    path.write_text(_raw_text_for(case_id, mutation), encoding="utf-8")
    with pytest.raises(BacktestConfigError) as excinfo:
        load_costs_config(path)
    message = str(excinfo.value)
    assert str(path) in message
    for fragment in expected:
        assert fragment in message


_CONSTRUCTION_CASES: list[tuple[str, dict[str, object], str]] = [
    ("F-d-negativo", {"round_trip_usd": -1.0}, "round_trip_usd"),
    ("F-d-cero", {"round_trip_usd": 0}, "round_trip_usd"),
    ("F-d-nan", {"round_trip_usd": float("nan")}, "round_trip_usd"),
    ("F-d-infinito", {"round_trip_usd": float("inf")}, "round_trip_usd"),
    ("F-d-bool", {"round_trip_usd": True}, "round_trip_usd"),
    ("F-d-cadena", {"round_trip_usd": "1.9"}, "round_trip_usd"),
    ("F-e-negativo", {"spread_ticks": -1}, "spread_ticks"),
    ("F-e-infinito", {"slippage_ticks": float("-inf")}, "slippage_ticks"),
    ("F-e-none", {"slippage_ticks": None}, "slippage_ticks"),
    ("F-f", {"friction_status": "medido"}, "friction_status"),
    ("F-g-http", {"source_url": "http://x"}, "source_url"),
    ("F-g-sin-host", {"source_url": "https://"}, "source_url"),
    ("F-g-espacios", {"source_url": " https://x.invalid"}, "source_url"),
    ("F-h-formato", {"read_on": "2026/10/02"}, "read_on"),
    ("F-h-fecha-imposible", {"read_on": "2026-02-30"}, "read_on"),
    ("T-g-vacio", {"symbol": ""}, "symbol"),
    ("T-g-espacios", {"symbol": "MNQ "}, "symbol"),
]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [(case[1], case[2]) for case in _CONSTRUCTION_CASES],
    ids=[case[0] for case in _CONSTRUCTION_CASES],
)
def test_fila_invalida_no_se_puede_construir(overrides: dict[str, object], field: str) -> None:
    with pytest.raises(BacktestConfigError, match=field):
        InstrumentCosts(**_row_kwargs(**overrides))  # ty: ignore[invalid-argument-type]


def test_tabla_vacia_o_duplicada_no_se_puede_construir() -> None:
    with pytest.raises(BacktestConfigError, match="vacía"):
        CostsConfig(instruments=())
    with pytest.raises(BacktestConfigError, match="US500"):
        make_costs_config(make_instrument_costs("US500"), make_instrument_costs("US500"))


def test_formato_viejo_se_rechaza_con_mensaje_claro(tmp_path: Path) -> None:
    path = tmp_path / "costs_config.json"
    path.write_text(
        '{"default_spread_points": 1.5, "commission_per_lot": 7.0, "slippage_points": 0.2}',
        encoding="utf-8",
    )
    with pytest.raises(BacktestConfigError) as excinfo:
        load_costs_config(path)
    message = str(excinfo.value)
    assert "commission_per_lot" in message
    assert "formato anterior" in message


@pytest.mark.parametrize("read_on", ["20261002", "2026-W40-5", "2026-02-30"])
def test_read_on_formatos_iso_alternativos_se_rechazan(tmp_path: Path, read_on: str) -> None:
    payload = _fixture_payload()
    payload["instruments"]["US500"]["read_on"] = read_on
    path = tmp_path / "costs_config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BacktestConfigError, match="read_on"):
        load_costs_config(path)


def test_ticks_en_cero_son_validos() -> None:
    row = make_instrument_costs("MNQ", spread_ticks=0, slippage_ticks=0)
    assert row.spread_ticks == 0.0
    assert row.slippage_ticks == 0.0


# --- R12: inmutabilidad -------------------------------------------------------------------


def test_costs_config_no_se_puede_mutar() -> None:
    config = load_test_costs_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.instruments = ()  # ty: ignore[invalid-assignment]
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.instruments[0].round_trip_usd = 1.0  # ty: ignore[invalid-assignment]


def test_costs_config_es_hasheable_y_comparable() -> None:
    a = load_test_costs_config()
    b = load_test_costs_config()
    assert a == b
    assert hash(a) == hash(b)
    assert {a: 1}[b] == 1


@given(st.permutations(["MNQ", "MGC", "MCL", "M6E", "MBT"]))
def test_costs_config_no_depende_del_orden_de_las_filas(order: list[str]) -> None:
    canonical = make_costs_config(*(make_instrument_costs(s) for s in sorted(order)))
    shuffled = make_costs_config(*(make_instrument_costs(s) for s in order))
    assert shuffled == canonical
    assert hash(shuffled) == hash(canonical)


def test_symbols_es_tupla_ordenada() -> None:
    symbols = load_test_costs_config().symbols
    assert isinstance(symbols, tuple)
    assert symbols == tuple(sorted(symbols))


def test_friction_status_se_normaliza_al_miembro_del_enum() -> None:
    row = InstrumentCosts(**_row_kwargs())  # ty: ignore[invalid-argument-type]
    assert row.friction_status is FrictionStatus.PROVISIONAL_HASTA_B4B


# --- R13: costs_hash ----------------------------------------------------------------------


def test_costs_hash_ignora_la_cita() -> None:
    a = make_costs_config(make_instrument_costs("MNQ"))
    b = make_costs_config(
        dataclasses.replace(
            make_instrument_costs("MNQ"),
            source_url="https://otra-fuente.invalid/x",
            read_on="2026-12-01",
        )
    )
    assert costs_hash("MNQ", a) == costs_hash("MNQ", b)


@pytest.mark.parametrize("field", ["round_trip_usd", "spread_ticks", "slippage_ticks"])
def test_costs_hash_cambia_con_cada_numero(field: str) -> None:
    a = make_costs_config(make_instrument_costs("MNQ"))
    b = make_costs_config(make_instrument_costs("MNQ", **{field: 3.0}))
    assert costs_hash("MNQ", a) != costs_hash("MNQ", b)


def test_costs_hash_no_depende_de_otra_fila() -> None:
    a = make_costs_config(make_instrument_costs("MNQ"), make_instrument_costs("MGC"))
    b = make_costs_config(
        make_instrument_costs("MNQ"), make_instrument_costs("MGC", round_trip_usd=2.2)
    )
    assert costs_hash("MNQ", a) == costs_hash("MNQ", b)


def test_costs_hash_normaliza_enteros() -> None:
    a = make_costs_config(make_instrument_costs("MNQ", spread_ticks=1, slippage_ticks=1))
    b = make_costs_config(make_instrument_costs("MNQ", spread_ticks=1.0, slippage_ticks=1.0))
    assert costs_hash("MNQ", a) == costs_hash("MNQ", b)


def test_costs_hash_normaliza_cero_negativo() -> None:
    a = make_costs_config(make_instrument_costs("MNQ", slippage_ticks=-0.0))
    b = make_costs_config(make_instrument_costs("MNQ", slippage_ticks=0.0))
    assert costs_hash("MNQ", a) == costs_hash("MNQ", b)


def test_costs_hash_no_incluye_el_simbolo() -> None:
    config = load_test_costs_config()
    assert costs_hash("SYM_A", config) == costs_hash("SYM_B", config)


def test_fixture_de_test_carga_y_se_marca_como_de_test() -> None:
    config = load_test_costs_config()
    assert config.symbols == ("NAS100", "SYM_A", "SYM_B", "US500")
    assert all(row.source_url.split("/")[2].endswith(".invalid") for row in config.instruments)
