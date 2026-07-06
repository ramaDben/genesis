"""Motor de Monte Carlo por símbolo y de portafolio (R38-R52).

Capa 4 (`genesis.validation`). `monte_carlo_symbol` ejecuta siempre ambos métodos
de resampleo (reshuffle + block bootstrap, R38); `monte_carlo_portfolio` combina los
`Ledger` OOS de varios símbolos por `trading_day` en una canasta indivisible antes de
resamplear en bloques temporales, preservando la correlación cruzada del mismo día
(R43). Todo generador aleatorio es una instancia explícita de
`numpy.random.Generator` (`numpy.random.default_rng(seed)`), nunca el estado global
`numpy.random` (R47) — determinismo total: misma semilla + dataset + config ⇒
resultados bit-idénticos.

`n_paths` recomendado en el punto de invocación de más alto nivel: `1000` (R49),
suficiente resolución para los percentiles de los gates G6 (MaxDD p95) y G7
(P(breach) < 5%) que evaluará Issue J — este módulo no evalúa ningún gate (R50).
"""

from genesis.backtest.ledger import FillRecord, Ledger


def _extract_exit_returns(ledger: Ledger) -> list[float]:
    """Deltas de `equity_after` de los `FillRecord` de salida del `ledger` (§2 del spec).

    Duplicado a propósito respecto a `wfa.py._extract_exit_returns` (ADR-H5): evita
    acoplar `wfa` <-> `montecarlo`. NO importa ningún símbolo privado de
    `genesis.backtest.metrics` (R61).
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
