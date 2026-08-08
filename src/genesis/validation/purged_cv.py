"""Purged K-Fold con embargo (López de Prado, *AFML* cap. 7), Issue I (R11-R20).

Partición sobre los trades OOS individuales del `oos_ledger_cosido` de `WfaResult`
(no sobre las ventanas rolling de `wfa.py`, que ya tienen su propia frontera IS/OOS
estricta): `n_folds` folds contiguos temporalmente por orden de
`exit_timestamp`; horizonte de purga = intervalo real `[entry_timestamp,
exit_timestamp]` de cada trade; embargo posterior explícito en días de calendario.
Determinista, sin aleatoriedad (R19); no re-ejecuta ningún backtest ni instancia
motor de simulación alguno (R18): opera exclusivamente sobre trades ya extraídos,
a diferencia de `dsr_pbo.py`/`sensitivity.py` (que sí re-ejecutan backtests).
Solo trades OOS deben alimentar `run_purged_cv` (R57, responsabilidad del
llamador).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from genesis.backtest.ledger import FillRecord, Ledger
from genesis.validation._returns import TradeReturn, extract_trade_returns
from genesis.validation._shared import clip
from genesis.validation.errors import PurgedCvConfigError

_MIN_EMBARGO_DAYS = 1
_MAX_EMBARGO_DAYS = 30


@dataclass(frozen=True, slots=True)
class PurgedCvConfig:
    """Configuración del Purged K-Fold con embargo (R11).

    `embargo_days=None` calcula un default determinista (R13): `1%` del rango
    temporal total de los trades OOS, acotado a `[1, 30]` días de calendario
    (patrón análogo a `_default_block_size` de `montecarlo.py`, decisión 4 de H).
    """

    n_folds: int = 5
    embargo_days: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.n_folds, int) or isinstance(self.n_folds, bool) or self.n_folds < 2:
            message = f"PurgedCvConfig.n_folds={self.n_folds!r} debe ser un entero >= 2 (R11)."
            raise PurgedCvConfigError(message)
        if self.embargo_days is not None and (
            not isinstance(self.embargo_days, int)
            or isinstance(self.embargo_days, bool)
            or self.embargo_days < 0
        ):
            message = (
                f"PurgedCvConfig.embargo_days={self.embargo_days!r} debe ser None o un entero "
                "no negativo (R11)."
            )
            raise PurgedCvConfigError(message)


@dataclass(frozen=True, slots=True)
class PurgedFold:
    """Un fold del Purged K-Fold, ya purgado y embargado (R17).

    `purged_trade_count` son los trades removidos del train por solapamiento de
    horizonte con el fold de test o por caer dentro de la ventana de embargo
    posterior (R15).
    """

    index: int
    test_trade_count: int
    train_trade_count: int
    purged_trade_count: int
    test_period: tuple[datetime, datetime]


@dataclass(frozen=True, slots=True)
class PurgedCvResult:
    """Resultado congelado del Purged K-Fold completo para `(candidate_id, symbol)` (R17)."""

    candidate_id: str
    symbol: str
    config: PurgedCvConfig
    folds: Sequence[PurgedFold]
    total_trades: int
    embargo_days_effective: int


def _first_fill_record(ledger: Ledger, *, candidate_id: str) -> FillRecord:
    """Primer `FillRecord` del `ledger`, base del `symbol` derivado (R12)."""
    for entry in ledger.entries:
        if isinstance(entry.payload, FillRecord):
            return entry.payload
    message = (
        f"oos_ledger de candidate_id={candidate_id!r} no contiene ningún FillRecord: no hay "
        "symbol ni trades OOS extraíbles (R1d)."
    )
    raise PurgedCvConfigError(message)


def _default_embargo_days(sorted_trades: Sequence[TradeReturn]) -> int:
    """`clip(round(0.01 * span_days), 1, 30)` sobre el rango temporal total (R13)."""
    span_days = (
        max(trade.exit_timestamp for trade in sorted_trades)
        - min(trade.entry_timestamp for trade in sorted_trades)
    ).days
    return clip(round(0.01 * span_days), _MIN_EMBARGO_DAYS, _MAX_EMBARGO_DAYS)


def _contiguous_partition_bounds(n_items: int, n_parts: int) -> list[tuple[int, int]]:
    """Índices `[start, end)` de `n_parts` particiones contiguas de tamaño `±1` (R14)."""
    base, remainder = divmod(n_items, n_parts)
    bounds: list[tuple[int, int]] = []
    start = 0
    for part_index in range(n_parts):
        size = base + (1 if part_index < remainder else 0)
        bounds.append((start, start + size))
        start += size
    return bounds


def run_purged_cv(oos_ledger: Ledger, config: PurgedCvConfig | None = None) -> PurgedCvResult:
    """Purged K-Fold con embargo sobre los trades OOS de `oos_ledger` (R12).

    `candidate_id`/`symbol` se derivan del propio `oos_ledger`
    (`oos_ledger.provenance.candidate_id` y el `symbol` del primer `FillRecord`),
    evitando parámetros redundantes (mantiene la firma normativa mínima de R12).
    `config=None` usa `PurgedCvConfig()` (mismo patrón de resolución de defaults
    que `run_wfa`, evita instanciar el dataclass en la firma). Solo debe
    alimentarse con trades OOS (R57, responsabilidad del llamador: este Change no
    distingue IS/OOS dentro del `Ledger` recibido).
    """
    resolved_config = config if config is not None else PurgedCvConfig()
    candidate_id = oos_ledger.provenance.candidate_id
    first_fill = _first_fill_record(oos_ledger, candidate_id=candidate_id)
    symbol = first_fill.symbol

    trades = extract_trade_returns(oos_ledger)
    if len(trades) < resolved_config.n_folds:
        message = (
            f"oos_ledger de candidate_id={candidate_id!r} symbol={symbol!r} tiene "
            f"{len(trades)} trades OOS extraíbles, menos que n_folds={resolved_config.n_folds!r}: "
            "imposible construir folds no vacíos (R1d)."
        )
        raise PurgedCvConfigError(message)

    sorted_trades = sorted(trades, key=lambda trade: trade.exit_timestamp)
    embargo_days_effective = (
        resolved_config.embargo_days
        if resolved_config.embargo_days is not None
        else _default_embargo_days(sorted_trades)
    )

    folds: list[PurgedFold] = []
    for fold_index, (start, end) in enumerate(
        _contiguous_partition_bounds(len(sorted_trades), resolved_config.n_folds)
    ):
        test_indices = set(range(start, end))
        test_trades = sorted_trades[start:end]
        test_start = min(trade.entry_timestamp for trade in test_trades)
        test_end = max(trade.exit_timestamp for trade in test_trades)
        embargo_end = test_end + timedelta(days=embargo_days_effective)

        train_count = 0
        purged_count = 0
        for trade_index, trade in enumerate(sorted_trades):
            if trade_index in test_indices:
                continue
            overlaps = not (trade.exit_timestamp < test_start or trade.entry_timestamp > test_end)
            in_embargo = test_end < trade.entry_timestamp <= embargo_end
            if overlaps or in_embargo:
                purged_count += 1
            else:
                train_count += 1

        if not test_trades or train_count == 0:
            empty_side = "test" if not test_trades else "train"
            message = (
                f"candidate_id={candidate_id!r} symbol={symbol!r} fold_index={fold_index!r}: "
                f"fold de {empty_side} vacío tras purga+embargo "
                f"(n_folds={resolved_config.n_folds!r}, "
                f"embargo_days_effective={embargo_days_effective!r}, R16)."
            )
            raise PurgedCvConfigError(message)

        folds.append(
            PurgedFold(
                index=fold_index,
                test_trade_count=len(test_trades),
                train_trade_count=train_count,
                purged_trade_count=purged_count,
                test_period=(test_start, test_end),
            )
        )

    return PurgedCvResult(
        candidate_id=candidate_id,
        symbol=symbol,
        config=resolved_config,
        folds=folds,
        total_trades=len(sorted_trades),
        embargo_days_effective=embargo_days_effective,
    )
