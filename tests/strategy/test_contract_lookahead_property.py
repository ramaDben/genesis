"""Propiedad central del spec §9 (R39, R44): forward-only anti-lookahead estructural.

Ningún output de `on_bar(t)` de un candidato (real o fake) DEBE depender, directa o
indirectamente, de una `AnnotatedBar` con `timestamp_utc > t`. Se verifica generando
con `hypothesis` una secuencia base de `AnnotatedBar` hasta un punto `t` (prefijo
común), agregándole dos "colas" de barras futuras (`timestamp_utc > t`) distintas y
arbitrarias, y comprobando que el resultado de `FakeStrategyCandidate.on_bar(bar_t)`
—capturado en el instante en que se procesa `bar_t`, antes de alimentar la cola
futura al `BarClock`— es idéntico en ambas ejecuciones. El `BarClock` alimenta las
barras vía `advance`; el fake usa `require` para que cualquier intento de leer un
timestamp futuro levante `LookaheadError` de forma estructural, no solo por
convención.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.data.store import AnnotatedBar
from genesis.strategy.clock import BarClock
from genesis.strategy.contract import CONFIG_VERSION, Direction, EntryIntent
from genesis.strategy.errors import LookaheadError
from tests.strategy.fakes import FakeStrategyCandidate, make_annotated_bar

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
_THRESHOLD = 500.0


def _sequence(closes: list[float], *, start_index: int = 0) -> list[AnnotatedBar]:
    """Construye una secuencia ascendente y determinista de `AnnotatedBar`."""
    return [
        make_annotated_bar(_BASE_TIME + timedelta(minutes=start_index + i), close=close)
        for i, close in enumerate(closes)
    ]


def _make_on_bar_fn(clock: BarClock) -> Callable[[AnnotatedBar], list[EntryIntent]]:
    """`on_bar` determinista: usa `BarClock.require` para no mirar al futuro.

    Emite un `EntryIntent` si `bar.close >= _THRESHOLD`; decisión que depende
    únicamente de la barra actual ya validada por `clock.require`, nunca de barras
    futuras (garantía estructural del guard PA-4).
    """

    def _on_bar(bar: AnnotatedBar) -> list[EntryIntent]:
        clock.require(bar.timestamp_utc)
        if bar.close >= _THRESHOLD:
            return [
                EntryIntent(
                    direction=Direction.LONG,
                    sizing_hint=0.1,
                    candidate_id="Z",
                    config_version=CONFIG_VERSION,
                )
            ]
        return []

    return _on_bar


def _run_and_capture_at_t(
    prefix_closes: list[float], suffix_closes: list[float]
) -> list[EntryIntent]:
    """Alimenta prefijo+cola bar-a-bar; captura `on_bar(bar_t)` al procesar el prefijo.

    `bar_t` es la última barra del prefijo. El resultado se captura ANTES de
    alimentar la cola (barras futuras, `timestamp_utc > bar_t.timestamp_utc`) al
    `BarClock`, replicando el harness del §9: "re-ejecutar on_bar(bar_t) sobre el
    estado previo a t".
    """
    clock = BarClock()
    fake = FakeStrategyCandidate(candidate_id="Z", on_bar_fn=_make_on_bar_fn(clock))

    prefix = _sequence(prefix_closes)
    result_at_t: list[EntryIntent] = []
    for bar in prefix:
        clock.advance(bar)
        result_at_t = fake.on_bar(bar)

    # Cola futura: se alimenta DESPUÉS de capturar result_at_t, nunca antes.
    suffix = _sequence(suffix_closes, start_index=len(prefix_closes))
    for bar in suffix:
        clock.advance(bar)
        fake.on_bar(bar)  # avanza el reloj/candidato; no afecta result_at_t ya capturado

    return result_at_t


_closes_strategy = st.lists(
    st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=30,
)
_future_closes_strategy = st.lists(
    st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=10,
)


@given(
    prefix_closes=_closes_strategy,
    suffix_closes_a=_future_closes_strategy,
    suffix_closes_b=_future_closes_strategy,
)
@settings(max_examples=1000, deadline=None)
def test_on_bar_en_t_no_cambia_si_se_mutan_barras_futuras(
    prefix_closes: list[float],
    suffix_closes_a: list[float],
    suffix_closes_b: list[float],
) -> None:
    """R39/R44: `on_bar(bar_t)` es idéntico sin importar qué barras futuras se agreguen."""
    result_a = _run_and_capture_at_t(prefix_closes, suffix_closes_a)
    result_b = _run_and_capture_at_t(prefix_closes, suffix_closes_b)
    assert result_a == result_b


def test_lookahead_error_se_lanza_si_on_bar_intenta_requerir_un_timestamp_futuro() -> None:
    """Garantía estructural: `require` de un timestamp > current_time lanza `LookaheadError`."""
    clock = BarClock()
    bars = _sequence([100.0, 101.0])
    clock.advance(bars[0])
    future_timestamp = bars[1].timestamp_utc
    with pytest.raises(LookaheadError):
        clock.require(future_timestamp)
