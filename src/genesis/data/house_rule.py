"""Contrato de la casa (`HouseRule`), embebido en `FirmProfile` (capa 1, Change #109).

Único lugar del repo donde se decide cómo se mueve el ancla del `max_loss_limit` y
cuándo se rompe la cuenta (Invariante 4 de `proposal.md`): tanto el `Simulator`
(capa 3, equity flotante intradía exacta) como `prop_sim` (capa 4, proxy
cierre-a-cierre de ADR-J4) llaman a los mismos métodos puros de `MaxLossLimit` con
los datos que tienen, sin reimplementar su propia noción de umbral.

Solo importa stdlib: ningún módulo de capa 1 importa capa 3 ni capa 4
(`design.md` §1.2).

`equity_basis` (qué cuenta como "equity" para evaluar el breach: con o sin swaps,
comisiones pendientes, etc.) es una precisión que queda documentada acá y no como
campo: la ficha MFFU no distingue bases de equity y agregar un campo sin consumidor
sería el mismo defecto de "parámetro muerto" que R8 ataca en `risk_exit.params`
(`design.md` §9).
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class MaxLossLimitKind(StrEnum):
    """Cómo se mueve el ancla del `max_loss_limit` contra la que se mide el breach."""

    STATIC = "static"
    TRAILING_INTRADAY = "trailing_intraday"
    TRAILING_EOD = "trailing_eod"


@dataclass(frozen=True, slots=True)
class MaxLossLimit:
    """Límite máximo de pérdida total de la cuenta, en monto absoluto de su divisa.

    `amount` es siempre un monto absoluto (nunca un porcentaje, D3 de `design.md`):
    la regla de la firma es un monto fijo atado a una denominación de cuenta, no una
    fracción del capital que se decida simular.
    """

    amount: float
    kind: MaxLossLimitKind

    def initial_anchor(self, starting_balance: float) -> float:
        """Ancla inicial del `max_loss_limit`: el balance con el que arranca la cuenta."""
        return starting_balance

    def next_anchor(
        self,
        current_anchor: float,
        *,
        floating_equity: float,
        session_close_balance: float | None,
        threshold_lock_at: float | None,
    ) -> float:
        """Próximo valor del ancla, según `kind`, con congelamiento de un solo sentido.

        Si `threshold_lock_at is not None` y el ancla actual ya lo alcanzó o superó,
        el ancla no se mueve más (una vez congelada, no se descongela). Si no está
        congelada: `STATIC` nunca actualiza el ancla; `TRAILING_INTRADAY` la sigue en
        cada evaluación contra `floating_equity`; `TRAILING_EOD` solo la actualiza
        cuando `session_close_balance` está disponible (cierre de sesión).
        """
        if threshold_lock_at is not None and current_anchor >= threshold_lock_at:
            return current_anchor
        if self.kind is MaxLossLimitKind.STATIC:
            return current_anchor
        if self.kind is MaxLossLimitKind.TRAILING_INTRADAY:
            return max(current_anchor, floating_equity)
        # TRAILING_EOD: solo se mueve en la barra de cierre de sesión.
        if session_close_balance is None:
            return current_anchor
        return max(current_anchor, session_close_balance)

    def threshold_from(self, anchor: float) -> float:
        """Umbral de breach: el ancla menos el monto absoluto del límite."""
        return anchor - self.amount

    def is_breached(self, anchor: float, equity: float) -> bool:
        """`True` si `equity` cayó al umbral o por debajo, dado el `anchor` vigente."""
        return equity <= self.threshold_from(anchor)


class DailyLossLimitSemantics(StrEnum):
    """Qué pasa cuando se cruza el `daily_loss_limit`."""

    BREACH = "breach"
    PAUSE = "pause"


@dataclass(frozen=True, slots=True)
class DailyLossLimit:
    """Límite de pérdida diaria, en monto absoluto (opcional: MFFU no lo declara)."""

    amount: float
    semantics: DailyLossLimitSemantics


class ConsistencySemantics(StrEnum):
    """Qué efecto tiene incumplir la regla de consistencia de payout."""

    TERMINATE = "terminate"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ConsistencyRule:
    """Regla de consistencia: ningún día puede aportar más de `pct`% del profit total."""

    pct: float
    semantics: ConsistencySemantics


@dataclass(frozen=True, slots=True)
class HouseRule:
    """Contrato de la casa: la mitad "restricción" que antes vivía en `RiskProfile`.

    Embebido en `FirmProfile` (capa 1, D2 de `design.md`): es la firma la que decide
    estos números, con cita de fuente, nunca una capa de ejecución. `account_size` es
    la denominación de cuenta que la ficha describe (p.ej. 50_000 en MFFU 50K) y
    gobierna el balance inicial de la corrida (D3b).
    """

    max_loss_limit: MaxLossLimit
    threshold_lock_at: float | None
    daily_loss_limit: DailyLossLimit | None
    consistency_rule: ConsistencyRule | None
    weekend_holding_allowed: bool
    payout_buffer: float
    min_net_profit_between_payouts: float
    funded_starting_balance: float
    account_size: float


def house_rule_hash(house_rule: HouseRule) -> str:
    """Hash `sha256` determinista de `house_rule` sobre JSON canónico ordenado.

    **Excluye `funded_starting_balance` (DH-4, issue #112).** El campo se carga con
    fidelidad al contrato (SSoT §1.1) pero hoy no tiene ningún consumidor funcional
    (PA-106-5 sigue fuera de alcance); si entrara al hash, dos fichas cuyas
    simulaciones son mecánicamente idénticas producirían huellas distintas y sus
    ensayos dejarían de colapsar en el `TrialLedger`, ensuciando el denominador del
    DSR. `firm_profile_hash` sí lo cubre, porque ahí la procedencia de la ficha
    completa es correcta. Revertir esta exclusión cuando el issue #112 le dé
    consumidor.
    """
    canonical = {
        "max_loss_limit": {
            "amount": house_rule.max_loss_limit.amount,
            "kind": house_rule.max_loss_limit.kind.value,
        },
        "threshold_lock_at": house_rule.threshold_lock_at,
        "daily_loss_limit": (
            {
                "amount": house_rule.daily_loss_limit.amount,
                "semantics": house_rule.daily_loss_limit.semantics.value,
            }
            if house_rule.daily_loss_limit is not None
            else None
        ),
        "consistency_rule": (
            {
                "pct": house_rule.consistency_rule.pct,
                "semantics": house_rule.consistency_rule.semantics.value,
            }
            if house_rule.consistency_rule is not None
            else None
        ),
        "weekend_holding_allowed": house_rule.weekend_holding_allowed,
        "payout_buffer": house_rule.payout_buffer,
        "min_net_profit_between_payouts": house_rule.min_net_profit_between_payouts,
        "account_size": house_rule.account_size,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
