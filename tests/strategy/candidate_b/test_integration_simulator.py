"""Integración de `CandidateB` con el `Simulator` real de Issue G (R85).

Import cruzado de fixtures/loaders de `tests/backtest/` y `genesis.data`/
`genesis.backtest` (habilitado por los `__init__.py` de test, H1): no se duplica la
construcción de `FirmProfile`/`RiskProfile`/`CostsConfig`/`SymbolFigure` ya existente
en `tests/backtest/conftest.py` (R80).
"""

from datetime import timedelta

import pandas as pd
import pytest

from genesis.backtest.costs import load_costs_config
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.risk_profile import load_risk_profile
from genesis.backtest.simulator import RiskLevelsProvider, Simulator
from genesis.data.profile import load_firm_profile
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.inspector import InspectorFunnelConfig
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.integration

_FUNNEL_CONFIG = InspectorFunnelConfig(min_rr=0.1, min_lot=0.01, max_lot=50.0)
_N_MINUTES = 3
_BASE_TIME = pd.Timestamp("2024-01-02 09:30:00")  # hora local server_tz (America/New_York)


def _synthetic_us500_frame() -> pd.DataFrame:
    """Sesión sintética US500: `_N_MINUTES` barras de rango + 1 barra de ruptura por cierre."""
    rows = [
        # (open, high, low, close) — las 3 primeras forman el rango; la 4.ª rompe por cierre.
        (4500.00, 4500.60, 4499.90, 4500.50),
        (4500.50, 4500.70, 4500.40, 4500.60),
        (4500.60, 4500.65, 4500.45, 4500.55),
        (4500.55, 4501.20, 4500.50, 4501.00),
    ]
    timestamps = [_BASE_TIME + timedelta(minutes=i) for i in range(len(rows))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "tick_volume": [100] * len(rows),
        }
    )


def _build_simulator(
    candidate: CandidateB,
    *,
    symbol_figure: SymbolFigure,
) -> Simulator:
    return Simulator(
        candidate,
        symbol="US500",
        firm_profile=load_firm_profile(),
        risk_profile=load_risk_profile(),
        figure=symbol_figure,
        funnel_config=_FUNNEL_CONFIG,
        costs_config=load_costs_config(),
        news_events=[],
        tick_store=None,
        starting_balance=100_000.0,
        dataset_hash="test-dataset-hash-candidate-b",
    )


def test_candidate_b_real_satisface_risk_levels_provider() -> None:
    """(a) `isinstance` sobre una instancia real de `CandidateB` (R85a)."""
    candidate = CandidateB(
        figure=_default_symbol_figure("US500"),
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
    )
    assert isinstance(candidate, RiskLevelsProvider) is True


def test_simulator_no_lanza_backtest_config_error_con_candidate_b() -> None:
    """(b) `Simulator(candidate=CandidateB(...), symbol="US500", ...)` construye sin error."""
    symbol_figure = _default_symbol_figure("US500")
    candidate = CandidateB(
        figure=symbol_figure,
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
    )
    try:
        simulator = _build_simulator(candidate, symbol_figure=symbol_figure)
    except BacktestConfigError as exc:  # pragma: no cover - solo si algo regresa
        pytest.fail(f"Simulator lanzó BacktestConfigError inesperadamente: {exc}")
    assert simulator is not None


def test_simulator_run_produce_ledger_con_candidate_id_b() -> None:
    """(c) `Simulator.run(frame)` produce `Ledger` con >=1 Fill/RejectionRecord de "B" (R85c).

    Tolerante por diseño (RI-E6): `sizing_hint` sin redondear (R70) puede caer fuera
    de `volume_step`/`max_lot` y producir un `RejectionRecord` en vez de un
    `FillRecord` — ambos desenlaces son válidos para este eval de integración.
    """
    symbol_figure = _default_symbol_figure("US500")
    candidate = CandidateB(
        figure=symbol_figure,
        reference_balance=100_000.0,
        n_minutes=_N_MINUTES,
        risk_pct=0.00375,
    )
    simulator = _build_simulator(candidate, symbol_figure=symbol_figure)

    ledger = simulator.run(_synthetic_us500_frame())

    candidate_b_entries = [
        entry for entry in ledger.entries if getattr(entry.payload, "candidate_id", None) == "B"
    ]
    assert len(candidate_b_entries) >= 1
