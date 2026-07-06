"""Extracción compartida de trades con horizonte temporal, módulo interno (ADR-I1, R7-R10).

Compartido por `purged_cv.py`, `dsr_pbo.py` y `sensitivity.py` (Issue I): a
diferencia de `wfa._extract_exit_returns`/`montecarlo._extract_exit_returns` (H,
duplicados a propósito entre sí por ADR-H5), este Change necesita además el
**horizonte temporal** (`entry_timestamp`/`exit_timestamp`) de cada trade para el
purgado por solapamiento (López de Prado, *AFML* cap. 7). Triplicar la extracción
dentro de un único Change no tiene el beneficio de aislamiento que motivó ADR-H5
(que evitaba acoplamiento *entre* módulos preexistentes, no *dentro* de un mismo
Change nuevo) — de ahí este módulo interno compartido.

NO importado por `wfa.py`/`montecarlo.py` (R9, ADR-H5 intacto entre Changes); NO
exportado en `src/genesis/validation/__init__.py` (R10, mismo patrón que `_dsr.py`).
"""

from dataclasses import dataclass
from datetime import datetime

from genesis.backtest.ledger import FillRecord, Ledger


@dataclass(frozen=True, slots=True)
class TradeReturn:
    """Trade OOS individual con horizonte temporal completo (§2 del spec, R7).

    `pnl_delta` es el delta de `equity_after` del `exit_fill` respecto al
    `entry_fill` correspondiente — misma definición de PnL por trade que
    `genesis.backtest.metrics`/`wfa._extract_exit_returns` (equivalencia verificada
    en `tests/validation/test_returns.py`, garantiza R21).
    """

    entry_timestamp: datetime
    exit_timestamp: datetime
    pnl_delta: float


def extract_trade_returns(ledger: Ledger) -> list[TradeReturn]:
    """Pareado secuencial entrada→salida de `FillRecord` del `ledger` (R8).

    Un trade es el par `(entry_fill, exit_fill)` de dos `FillRecord` consecutivos
    del ledger, con `entry_fill.is_exit=False` seguido (sin otro `FillRecord` de
    entrada entre medias) del siguiente `is_exit=True` (§2 del spec). Ignora
    `RejectionRecord`/`BreachEvent`. Preserva el orden de aparición en `ledger`
    (append-only, forward-only por construcción): no reordena por
    `timestamp_utc`.

    Supuesto explícito (Rg-7, documentado en el spec): válido para un candidato con
    una única posición abierta por símbolo a la vez (Candidato B, spec §2.3). Un
    candidato futuro con posiciones concurrentes requeriría revisar este pareado
    antes de reutilizarlo.
    """
    trades: list[TradeReturn] = []
    pending_entry: FillRecord | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if not isinstance(payload, FillRecord):
            continue
        if not payload.is_exit:
            pending_entry = payload
        elif pending_entry is not None:
            trades.append(
                TradeReturn(
                    entry_timestamp=pending_entry.timestamp_utc,
                    exit_timestamp=payload.timestamp_utc,
                    pnl_delta=payload.equity_after - pending_entry.equity_after,
                )
            )
            pending_entry = None
    return trades
