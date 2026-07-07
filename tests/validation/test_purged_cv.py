"""Tests de `purged_cv.py`: Purged K-Fold con embargo (R11-R20, R47, R49, R50b)."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from genesis.backtest.ledger import Ledger
from genesis.validation._returns import TradeReturn, extract_trade_returns
from genesis.validation.errors import PurgedCvConfigError
from genesis.validation.purged_cv import (
    PurgedCvConfig,
    PurgedCvResult,
    run_purged_cv,
)
from tests.validation.fixtures.ledgers import build_ledger_with_trade_intervals

_BASE = datetime(2024, 1, 1, tzinfo=UTC)


def test_n_folds_menor_a_dos_lanza_purged_cv_config_error() -> None:
    with pytest.raises(PurgedCvConfigError):
        PurgedCvConfig(n_folds=1)


def test_embargo_days_negativo_lanza_purged_cv_config_error() -> None:
    with pytest.raises(PurgedCvConfigError):
        PurgedCvConfig(embargo_days=-1)


@pytest.mark.unit
def test_few_trades_raises(oos_ledger_fixture: Ledger) -> None:
    """R1d: menos trades OOS extraíbles que `n_folds` -> `PurgedCvConfigError`."""
    with pytest.raises(PurgedCvConfigError):
        run_purged_cv(oos_ledger_fixture, PurgedCvConfig(n_folds=10))


@pytest.mark.unit
def test_empty_fold_raises() -> None:
    """R16: configuración que vacía el fold de train tras purga+embargo."""
    # 4 trades muy próximos entre sí: un embargo largo purga TODO el train de la
    # primera mitad, dejando el fold de train vacío.
    intervals = [
        (_BASE + timedelta(hours=h), _BASE + timedelta(hours=h + 1), 1.0) for h in (0, 2, 4, 6)
    ]
    ledger = build_ledger_with_trade_intervals(intervals)
    with pytest.raises(PurgedCvConfigError):
        run_purged_cv(ledger, PurgedCvConfig(n_folds=2, embargo_days=30))


@pytest.mark.unit
def test_default_embargo() -> None:
    """R13: `embargo_days=None` -> `clip(round(0.01 * span_days), 1, 30)`."""
    intervals = [
        (_BASE, _BASE + timedelta(hours=1), 5.0),
        (_BASE + timedelta(days=200), _BASE + timedelta(days=200, hours=1), -2.0),
    ]
    ledger = build_ledger_with_trade_intervals(intervals)
    result = run_purged_cv(ledger, PurgedCvConfig(n_folds=2, embargo_days=None))
    assert result.embargo_days_effective == 2


@pytest.mark.statistical
def test_purge_golden(oos_ledger_fixture: Ledger) -> None:
    """R50b: caso de purga+embargo calculado a mano (López de Prado, AFML cap. 7).

    6 trades de 1 día, consecutivos, sin solape entre sí (`oos_ledger_fixture`):
    trade `k` va de `día_k 08:00` a `día_k 20:00`. Con `n_folds=3`,
    `embargo_days=1`: cada fold de test agrupa 2 trades consecutivos.

    Cálculo a mano (contiguo, sin `scipy`):
      fold0: test=[T0,T1] -> [día0 08:00, día1 20:00], embargo_end=día2 20:00.
             T2 (día2 08:00) cae en (test_end, embargo_end] -> purgado.
             T3,T4,T5 fuera de solape/embargo -> train=3, purged=1.
      fold1: test=[T2,T3] -> [día2 08:00, día3 20:00], embargo_end=día4 20:00.
             T0,T1 anteriores (exit < test_start) -> train. T4 (día4 08:00) cae en
             (test_end, embargo_end] -> purgado. T5 (día5 08:00) > embargo_end ->
             train. train=3 (T0,T1,T5), purged=1 (T4).
      fold2: test=[T4,T5] -> [día4 08:00, día5 20:00], embargo_end=día6 20:00.
             T0..T3 todos exit < test_start, ninguno en el embargo -> train=4,
             purged=0.
    """
    result = run_purged_cv(oos_ledger_fixture, PurgedCvConfig(n_folds=3, embargo_days=1))

    assert result.total_trades == 6
    assert result.embargo_days_effective == 1
    assert len(result.folds) == 3

    fold0, fold1, fold2 = result.folds
    assert (fold0.test_trade_count, fold0.train_trade_count, fold0.purged_trade_count) == (2, 3, 1)
    assert (fold1.test_trade_count, fold1.train_trade_count, fold1.purged_trade_count) == (2, 3, 1)
    assert (fold2.test_trade_count, fold2.train_trade_count, fold2.purged_trade_count) == (2, 4, 0)

    day0 = _BASE
    assert fold0.test_period == (
        day0 + timedelta(hours=8),
        day0 + timedelta(days=1, hours=20),
    )
    assert fold2.test_period == (
        day0 + timedelta(days=4, hours=8),
        day0 + timedelta(days=5, hours=20),
    )


def _reference_partition_bounds(n_items: int, n_parts: int) -> list[tuple[int, int]]:
    """Oracle independiente de la partición contigua (mismo criterio de R14, sin `purged_cv`)."""
    base, rem = divmod(n_items, n_parts)
    bounds = []
    start = 0
    for i in range(n_parts):
        size = base + (1 if i < rem else 0)
        bounds.append((start, start + size))
        start += size
    return bounds


def _reference_purge(
    sorted_trades: list[TradeReturn], n_folds: int, embargo_days: int
) -> list[tuple[list[TradeReturn], list[TradeReturn], list[TradeReturn]]]:
    """Oracle independiente de purga+embargo (R15-R16), reescrito directo del texto normativo."""
    bounds = _reference_partition_bounds(len(sorted_trades), n_folds)
    reference: list[tuple[list[TradeReturn], list[TradeReturn], list[TradeReturn]]] = []
    for start, end in bounds:
        test_indices = set(range(start, end))
        test = sorted_trades[start:end]
        test_start = min(t.entry_timestamp for t in test)
        test_end = max(t.exit_timestamp for t in test)
        embargo_end = test_end + timedelta(days=embargo_days)
        train: list[TradeReturn] = []
        purged: list[TradeReturn] = []
        for index, trade in enumerate(sorted_trades):
            if index in test_indices:
                continue
            overlaps = not (trade.exit_timestamp < test_start or trade.entry_timestamp > test_end)
            in_embargo = test_end < trade.entry_timestamp <= embargo_end
            if overlaps or in_embargo:
                purged.append(trade)
            else:
                train.append(trade)
        reference.append((test, train, purged))
    return reference


@st.composite
def _trade_intervals_strategy(draw: st.DrawFn) -> list[tuple[datetime, datetime, float]]:
    n_trades = draw(st.integers(min_value=4, max_value=10))
    intervals: list[tuple[datetime, datetime, float]] = []
    cursor_hours = 0
    for _ in range(n_trades):
        gap_hours = draw(st.integers(min_value=0, max_value=48))
        duration_hours = draw(st.integers(min_value=1, max_value=72))
        entry = _BASE + timedelta(hours=cursor_hours + gap_hours)
        exit_ = entry + timedelta(hours=duration_hours)
        delta = draw(
            st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
        )
        intervals.append((entry, exit_, delta))
        cursor_hours += gap_hours + duration_hours
    return intervals


@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(intervals=_trade_intervals_strategy(), n_folds=st.integers(min_value=2, max_value=3))
def test_no_leakage(intervals: list[tuple[datetime, datetime, float]], n_folds: int) -> None:
    """R20/R47: ningún trade de train solapa el intervalo de test tras purga+embargo.

    Verificado por consistencia de conteos contra un oráculo independiente
    (`_reference_purge`, reescrito directo de R15-R16, sin reutilizar
    `purged_cv._*`), más la propiedad estructural del oráculo (por construcción,
    ningún trade de `train` solapa `[test_start, test_end]`).
    """
    embargo_days = 1
    ledger = build_ledger_with_trade_intervals(intervals)
    try:
        result = run_purged_cv(ledger, PurgedCvConfig(n_folds=n_folds, embargo_days=embargo_days))
    except PurgedCvConfigError:
        assume(False)
        return

    trades = extract_trade_returns(ledger)
    sorted_trades = sorted(trades, key=lambda t: t.exit_timestamp)
    reference = _reference_purge(sorted_trades, n_folds, embargo_days)

    for fold, (test, train, purged) in zip(result.folds, reference, strict=True):
        assert fold.test_trade_count == len(test)
        assert fold.train_trade_count == len(train)
        assert fold.purged_trade_count == len(purged)

        test_start, test_end = fold.test_period
        for trade in train:
            overlaps = not (trade.exit_timestamp < test_start or trade.entry_timestamp > test_end)
            assert not overlaps, "anti-leakage violado: un trade de train solapa el test (R20)"


@pytest.mark.unit
def test_determinism(oos_ledger_fixture: Ledger) -> None:
    """R49: mismo `oos_ledger`/`config` -> `PurgedCvResult` bit-idéntico."""
    config = PurgedCvConfig(n_folds=3, embargo_days=1)
    result1: PurgedCvResult = run_purged_cv(oos_ledger_fixture, config)
    result2: PurgedCvResult = run_purged_cv(oos_ledger_fixture, config)
    assert result1 == result2


def test_run_purged_cv_no_reejecuta_backtest() -> None:
    """R18: `purged_cv.py` no instancia `CandidateB`/`Simulator`."""
    import genesis.validation.purged_cv as purged_cv_module

    with open(purged_cv_module.__file__, encoding="utf-8") as handle:
        content = handle.read()
    assert "CandidateB" not in content
    assert "Simulator" not in content
