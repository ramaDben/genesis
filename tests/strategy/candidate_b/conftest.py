"""Fixtures propias de sesión sintética del Candidato B (R80).

Reutiliza `make_annotated_bar` de `tests/strategy/fakes.py` y `_default_symbol_figure`
de `tests/data/fakes.py`, sin duplicarlos.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from genesis.data.store import AnnotatedBar
from genesis.data.symbols import SymbolFigure
from tests.data.fakes import _default_symbol_figure
from tests.strategy.fakes import make_annotated_bar

BASE_TRADING_DAY: date = date(2024, 1, 2)
BASE_TIME: datetime = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)


@pytest.fixture
def us500_figure() -> SymbolFigure:
    """`SymbolFigure("US500")` determinista: `digits=2` -> `epsilon=0.005`,
    `tick_value=1.0`, `tick_size=1.0` -> `value_per_point=1.0`."""
    return _default_symbol_figure("US500")


def orb_session(
    *,
    n_minutes: int,
    range_bars: list[tuple[float, float, float, float]],
    post_range_bars: list[tuple[float, float, float, float]] | None = None,
    trading_day: date = BASE_TRADING_DAY,
    base_time: datetime = BASE_TIME,
    in_session: bool = True,
) -> list[AnnotatedBar]:
    """Arma una sesión sintética: `n_minutes` barras de formación + barras posteriores.

    Cada tupla de `range_bars`/`post_range_bars` es `(open, high, low, close)`. La
    primera barra fija la dirección de referencia (R56) y participa en el rango
    (R57); las barras de `post_range_bars` llegan tras la ventana de formación
    (posibles gatillos de ruptura, R58).
    """
    if len(range_bars) != n_minutes:
        message = f"range_bars debe tener exactamente n_minutes={n_minutes} elementos."
        raise ValueError(message)

    bars: list[AnnotatedBar] = []
    all_bars = list(range_bars) + list(post_range_bars or [])
    for index, (open_, high, low, close) in enumerate(all_bars):
        bars.append(
            make_annotated_bar(
                base_time + timedelta(minutes=index),
                open_=open_,
                high=high,
                low=low,
                close=close,
                trading_day=trading_day,
                in_session=in_session,
            )
        )
    return bars
