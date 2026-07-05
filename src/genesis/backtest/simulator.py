"""`Simulator` — orquestador event-driven de la capa 3 (R20–R36, ADR-G3/G9).

Único módulo "tope" de `genesis.backtest`: consume todos los demás módulos de esta
capa más los puertos ya cerrados de `genesis.strategy` (capa 2) y `genesis.data`
(capa 1), sin modificar ninguno de los dos árboles (R57). `RiskLevelsProvider` es un
puerto adicional requisito duro (ADR-G3): el `Simulator` exige que el candidato lo
implemente al construirse, en vez de un `RejectionReason` nuevo o un rechazo
silencioso (R21).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from genesis.backtest.clock import SimulationClock
from genesis.backtest.costs import CostsConfig
from genesis.backtest.errors import BacktestConfigError
from genesis.backtest.ledger import CONFIG_VERSION, Ledger, RunProvenance
from genesis.backtest.risk_profile import RiskProfile, risk_profile_hash
from genesis.data.calendar import EconomicEvent
from genesis.data.mt5_export import RawParquetStore
from genesis.data.profile import FirmProfile, firm_profile_hash
from genesis.data.sessions import session_window
from genesis.data.symbols import SymbolFigure
from genesis.strategy.contract import Direction, EntryIntent, StrategyCandidate
from genesis.strategy.inspector import InspectorFunnelConfig

_SESSION_PROBE_DATE = date(2024, 1, 1)
"""Fecha arbitraria usada solo para validar `symbol in SESSIONS` al construir (R3c)."""


@runtime_checkable
class RiskLevelsProvider(Protocol):
    """Puerto adicional opcional que expone niveles de riesgo de una intención (R20, ADR-G3).

    `EntryIntent` de la capa 2 es intencionalmente mínimo (4 campos) y no porta
    geometría de niveles; los candidatos que necesiten fills SL/TP simulados
    implementan este puerto además de `StrategyCandidate`.
    """

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float]:
        """Retorna `(stop_loss, take_profit)` para `intent`, recién emitido por `on_bar`."""
        ...


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """Identidad inmutable de una posición abierta durante la simulación."""

    candidate_id: str
    symbol: str
    direction: Direction
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    sizing_hint: float


@dataclass
class AccountState:
    """Estado mutable de ejecución de la cuenta simulada (no es un value object, RI-G3)."""

    balance: float
    open_positions: list[OpenPosition]
    account_exhausted: bool = False


class Simulator:
    """Orquestador event-driven de un backtest para `(candidate, symbol)` (R22).

    Verifica al construirse, antes de procesar la primera barra: `(1)` que
    `candidate` implementa `RiskLevelsProvider` (R21); `(2)` que `costs_config` es
    válido ("sin costos no hay reporte", R40); `(3)` que `symbol` está en la tabla de
    sesiones (`session_window`, R3c). Fail-fast con `BacktestConfigError` con contexto
    ante cualquier violación.
    """

    def __init__(
        self,
        candidate: StrategyCandidate,
        *,
        symbol: str,
        firm_profile: FirmProfile,
        risk_profile: RiskProfile,
        figure: SymbolFigure,
        funnel_config: InspectorFunnelConfig,
        costs_config: CostsConfig,
        news_events: Sequence[EconomicEvent],
        tick_store: RawParquetStore | None,
        starting_balance: float,
        dataset_hash: str,
        stress: float = 1.0,
    ) -> None:
        if not isinstance(candidate, RiskLevelsProvider):
            message = (
                f"El candidato candidate_id={getattr(candidate, 'candidate_id', '?')!r} no "
                "implementa RiskLevelsProvider (risk_levels); requisito duro para simular "
                f"symbol={symbol!r} (R21, ADR-G3)."
            )
            raise BacktestConfigError(message)

        if not isinstance(costs_config, CostsConfig):
            message = (
                f"costs_config inválido para symbol={symbol!r}: se esperaba una instancia de "
                f"CostsConfig, se recibió {costs_config!r} (R40: sin costos no hay reporte)."
            )
            raise BacktestConfigError(message)

        try:
            session_window(symbol, _SESSION_PROBE_DATE)
        except KeyError as exc:
            message = (
                f"symbol={symbol!r} no está soportado por la tabla de sesiones "
                f"(genesis.data.sessions.SESSIONS): {exc} (R3c)."
            )
            raise BacktestConfigError(message) from exc

        self.candidate = candidate
        self.symbol = symbol
        self.firm_profile = firm_profile
        self.risk_profile = risk_profile
        self.figure = figure
        self.funnel_config = funnel_config
        self.costs_config = costs_config
        self.news_events = news_events
        self.tick_store = tick_store
        self.stress = stress

        candidate_id = getattr(candidate, "candidate_id", "?")
        provenance = RunProvenance(
            candidate_id=candidate_id,
            config_version=CONFIG_VERSION,
            dataset_hash=dataset_hash,
            firm_profile_hash=firm_profile_hash(firm_profile),
            risk_profile_hash=risk_profile_hash(risk_profile),
        )
        self.ledger = Ledger(provenance=provenance, entries=[])
        self.clock = SimulationClock()
        self.account = AccountState(balance=starting_balance, open_positions=[])
        self.clock.previous_day_close_balance = starting_balance

    def run(self, frame: pd.DataFrame) -> Ledger:
        """Ejecuta la simulación completa sobre `frame` y retorna el `Ledger` poblado.

        Cuerpo implementado en T9 (loop + fills) y T10 (breaches + cierre de sesión).
        """
        raise NotImplementedError


def run_backtest(candidate: StrategyCandidate, frame: pd.DataFrame, **kwargs: Any) -> Ledger:
    """Wrapper funcional de conveniencia: `Simulator(candidate, **kwargs).run(frame)`."""
    return Simulator(candidate, **kwargs).run(frame)
