"""Fakes deterministas reutilizables para la suite `tests/strategy/` (R38)."""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from genesis.data.store import AnnotatedBar
from genesis.strategy.contract import EntryIntent

_DEFAULT_ON_BAR: Callable[[AnnotatedBar], list[EntryIntent]] = lambda bar: []  # noqa: E731


class FakeStrategyCandidate:
    """Candidato de estrategia fake, sin lógica de trading real (R38, patrón `tests/data/fakes.py`).

    Comportamiento parametrizable e inyectable vía `on_bar_fn`: una función pura de
    `AnnotatedBar -> list[EntryIntent]` que el test controla. Determinista por
    construcción (no mira al futuro) siempre que `on_bar_fn` tampoco lo haga.
    Implementa `StrategyCandidate` (atributo `candidate_id` + método `on_bar`).
    """

    def __init__(
        self,
        candidate_id: str = "Z",
        on_bar_fn: Callable[[AnnotatedBar], list[EntryIntent]] = _DEFAULT_ON_BAR,
    ) -> None:
        self.candidate_id = candidate_id
        self._on_bar_fn = on_bar_fn
        self.on_bar_calls: list[AnnotatedBar] = []

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        self.on_bar_calls.append(bar)
        return self._on_bar_fn(bar)


def make_annotated_bar(
    timestamp_utc: datetime,
    *,
    close: float = 100.0,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    tick_volume: int = 10,
    trading_day: date | None = None,
    in_session: bool = True,
    session_open_utc: datetime | None = None,
    session_close_utc: datetime | None = None,
) -> AnnotatedBar:
    """Construye una `AnnotatedBar` determinista con defaults razonables para tests.

    Los bordes de sesión, si no se pasan, envuelven al timestamp con holgura de 12 h:
    así la barra cae dentro de sesión y nunca dispara el cierre forzado por accidente.
    Un test que pruebe el borde debe pasarlo explícitamente — es su premisa, no un
    default.
    """
    return AnnotatedBar(
        timestamp_utc=timestamp_utc,
        open=open_ if open_ is not None else close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        tick_volume=tick_volume,
        trading_day=trading_day if trading_day is not None else timestamp_utc.date(),
        in_session=in_session,
        session_open_utc=(
            session_open_utc
            if session_open_utc is not None
            else timestamp_utc - timedelta(hours=12)
        ),
        session_close_utc=(
            session_close_utc
            if session_close_utc is not None
            else timestamp_utc + timedelta(hours=12)
        ),
    )
