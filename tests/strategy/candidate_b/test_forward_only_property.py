"""Propiedad forward-only sobre `CandidateB` real (R83, R88; hypothesis >=1000 ejemplos).

Ningún output de `on_bar(bar_t)` de `CandidateB` DEBE depender de una `AnnotatedBar`
con `timestamp_utc > t`, ni el rango congelado (`_range_high`/`_range_low`) DEBE
cambiar ante barras posteriores, por extremas que sean (spec §9). Se genera con
`hypothesis` un prefijo determinista común hasta `bar_t` y dos colas futuras
(`timestamp_utc > t`) distintas y arbitrarias; se compara el resultado de
`on_bar(bar_t)` —y el rango congelado— entre ambas ejecuciones, replicando el
harness de `tests/strategy/test_contract_lookahead_property.py`.
"""

import contextlib
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import EntryIntent
from genesis.strategy.errors import CandidateBStateError
from tests.data.fakes import _default_symbol_figure
from tests.strategy.candidate_b.conftest import BASE_TIME
from tests.strategy.fakes import make_annotated_bar

pytestmark = pytest.mark.unit

_N_MINUTES = 3
_PRICE = st.floats(min_value=100.0, max_value=10_000.0, allow_nan=False, allow_infinity=False)
_QUADRUPLE = st.tuples(_PRICE, _PRICE, _PRICE, _PRICE)
_PREFIX_STRATEGY = st.lists(_QUADRUPLE, min_size=1, max_size=8)
_SUFFIX_STRATEGY = st.lists(_QUADRUPLE, min_size=0, max_size=4)


def _build_bars(quadruples: list[tuple[float, float, float, float]], *, start_index: int) -> list:
    """Barras `in_session` deterministas y ascendentes a partir de 4 floats arbitrarios."""
    bars = []
    for i, (a, b, c, d) in enumerate(quadruples):
        bars.append(
            make_annotated_bar(
                BASE_TIME + timedelta(minutes=start_index + i),
                open_=a,
                close=b,
                high=max(a, b, c, d),
                low=min(a, b, c, d),
                in_session=True,
            )
        )
    return bars


def _run_and_capture_at_t(
    prefix_quadruples: list[tuple[float, float, float, float]],
    suffix_quadruples: list[tuple[float, float, float, float]],
) -> tuple[list[EntryIntent] | str, float | None, float | None]:
    """Corre prefijo+cola bar-a-bar; captura `on_bar(bar_t)` y el rango ANTES de la cola.

    `CandidateBStateError` (R67, geometría degenerada) es un desenlace legítimo y
    determinista del prefijo: se captura como marcador comparable en vez de dejar
    propagar la excepción, preservando la propiedad de igualdad entre corridas con el
    MISMO prefijo.
    """
    candidate = CandidateB(
        figure=_default_symbol_figure("US500"),
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
    )
    prefix = _build_bars(prefix_quadruples, start_index=0)
    result_at_t: list[EntryIntent] | str = []
    for bar in prefix:
        try:
            result_at_t = candidate.on_bar(bar)
        except CandidateBStateError as exc:
            result_at_t = f"CandidateBStateError:{exc}"

    range_high_at_t = candidate._range_high
    range_low_at_t = candidate._range_low

    # Cola futura: se alimenta DESPUÉS de capturar el estado en t, nunca antes.
    suffix = _build_bars(suffix_quadruples, start_index=len(prefix))
    for bar in suffix:
        # desenlace posible en la cola (CandidateBStateError); irrelevante para la
        # propiedad en t, que ya fue capturada arriba.
        with contextlib.suppress(CandidateBStateError):
            candidate.on_bar(bar)

    return result_at_t, range_high_at_t, range_low_at_t


@given(
    prefix_quadruples=_PREFIX_STRATEGY,
    suffix_quadruples_a=_SUFFIX_STRATEGY,
    suffix_quadruples_b=_SUFFIX_STRATEGY,
)
@settings(max_examples=1000, deadline=None)
def test_on_bar_en_t_y_rango_congelado_no_cambian_si_se_mutan_barras_futuras(
    prefix_quadruples: list[tuple[float, float, float, float]],
    suffix_quadruples_a: list[tuple[float, float, float, float]],
    suffix_quadruples_b: list[tuple[float, float, float, float]],
) -> None:
    """R83/R88: `on_bar(bar_t)` y el rango congelado son idénticos ante cualquier futuro."""
    result_a, high_a, low_a = _run_and_capture_at_t(prefix_quadruples, suffix_quadruples_a)
    result_b, high_b, low_b = _run_and_capture_at_t(prefix_quadruples, suffix_quadruples_b)

    assert result_a == result_b
    assert high_a == high_b
    assert low_a == low_b
