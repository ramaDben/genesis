"""Walk-forward rolling con grid IS exhaustivo, selección DSR-IS, OOS cosido y WFE.

Capa 4 (`genesis.validation`): consume la API pública ya cerrada de `genesis.data`,
`genesis.strategy` y `genesis.backtest` (capas 1-3) en un solo sentido, sin
modificar ninguno de los tres árboles (R61). Grid exhaustivo 27 combinaciones de
ejecución / 9 configuraciones de señal (spec §6.2, Candidato B): sin muestreo, sin
paralelismo (`multiprocessing`/`concurrent.futures`, R32), loop secuencial.

Advertencia heredada del Candidato B (Rg-1, aceptada, no defecto de este Change):
cada combinación/ventana instancia un `CandidateB` **nuevo** (nunca reutilizado);
el estado ATR-Wilder-14 arranca en frío (`atr_value=None`) al inicio de cada
instancia, de modo que los primeros `atr_period` (14) días de cada ventana pueden
operar sin componente ATR del stop. Con `IS_WINDOW_TRADING_DAYS = 252` el sesgo es
despreciable (14/252).
"""

from genesis.backtest.ledger import FillRecord, Ledger


def _extract_exit_returns(ledger: Ledger) -> list[float]:
    """Deltas de `equity_after` de los `FillRecord` de salida del `ledger` (§2 del spec).

    Replica el patrón `genesis.backtest.metrics._running_equity_deltas` + filtro
    `is_exit`, duplicado a propósito en `wfa.py` y `montecarlo.py` (ADR-H5): NO
    importa ningún símbolo privado de `genesis.backtest.metrics` (R61).
    """
    deltas: list[float] = []
    previous_equity: float | None = None
    for entry in ledger.entries:
        payload = entry.payload
        if isinstance(payload, FillRecord):
            if previous_equity is not None and payload.is_exit:
                deltas.append(payload.equity_after - previous_equity)
            previous_equity = payload.equity_after
    return deltas
