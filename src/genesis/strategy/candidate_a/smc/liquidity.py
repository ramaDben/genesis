"""`LiquidityLevel` (EQH/EQL) + `LiquidityMap`: agrupación por tolerancia ATR y mitigación, R102.

Módulo de dominio puro: solo stdlib + `genesis.strategy.candidate_a.smc.{fractals,timeframe}`.
"""

from dataclasses import dataclass, replace
from itertools import count

from genesis.strategy.candidate_a.smc.fractals import Swing, SwingDirection
from genesis.strategy.candidate_a.smc.timeframe import AggregatedBar, Timeframe


@dataclass(frozen=True, slots=True)
class LiquidityLevel:
    """Nivel de liquidez EQH (`HIGH`)/EQL (`LOW`): grupo de `Swing` del mismo TF (R102).

    `level_id` es un identificador interno monotónico asignado por `LiquidityMap` en la
    creación (detalle de implementación, no normativo del spec): permite correlacionar
    de forma estable un nivel con su `SweepTracker` a través de fusiones de miembros y
    actualizaciones de `mitigated`, sin depender de la identidad de objeto (el nivel se
    reemplaza — `dataclasses.replace` — en cada actualización).
    """

    level_id: int
    timeframe: Timeframe
    direction: SwingDirection
    price: float
    """Precio del nivel: máximo (EQH) o mínimo (EQL) del grupo de `member_swings`."""
    member_swings: tuple[Swing, ...]
    mitigated: bool = False
    """`True` cuando una vela posterior del TF CIERRA más allá del nivel (R102)."""


class LiquidityMap:
    """Agrupa `Swing` del mismo TF dentro de tolerancia ATR y aplica mitigación (R102).

    Dos o más `Swing` del mismo TF forman un nivel si la diferencia entre sus precios
    extremos es `<= eq_tolerance_atr * ATR(atr_period)` del TF correspondiente (ATR
    incremental, R106, provisto por el caller en cada `add_swing`).
    """

    def __init__(self, eq_tolerance_atr: float) -> None:
        self._eq_tolerance_atr = eq_tolerance_atr
        self._levels: dict[int, LiquidityLevel] = {}
        self._id_sequence = count(1)

    def add_swing(self, swing: Swing, atr_of_tf: float) -> None:
        """Agrega `swing` a un nivel existente dentro de tolerancia, o crea uno nuevo."""
        tolerance = self._eq_tolerance_atr * atr_of_tf
        for level_id, level in self._levels.items():
            if level.mitigated:
                continue
            if level.timeframe != swing.timeframe or level.direction != swing.direction:
                continue
            if abs(level.price - swing.price) <= tolerance:
                members = (*level.member_swings, swing)
                new_price = (
                    max(member.price for member in members)
                    if swing.direction == SwingDirection.HIGH
                    else min(member.price for member in members)
                )
                self._levels[level_id] = replace(level, price=new_price, member_swings=members)
                return

        new_id = next(self._id_sequence)
        self._levels[new_id] = LiquidityLevel(
            level_id=new_id,
            timeframe=swing.timeframe,
            direction=swing.direction,
            price=swing.price,
            member_swings=(swing,),
            mitigated=False,
        )

    def apply_close(self, agg_bar: AggregatedBar) -> None:
        """Marca `mitigated=True` los niveles del TF de `agg_bar` cuyo cierre los supera."""
        for level_id, level in list(self._levels.items()):
            if level.timeframe != agg_bar.timeframe or level.mitigated:
                continue
            beyond = (
                agg_bar.close > level.price
                if level.direction == SwingDirection.HIGH
                else agg_bar.close < level.price
            )
            if beyond:
                self._levels[level_id] = replace(level, mitigated=True)

    def active_levels(self, timeframe: Timeframe) -> list[LiquidityLevel]:
        """Niveles no mitigados del TF dado, en orden de creación."""
        return [
            level
            for level in self._levels.values()
            if level.timeframe == timeframe and not level.mitigated
        ]

    def get(self, level_id: int) -> LiquidityLevel:
        """Retorna el nivel vigente (posiblemente actualizado) para `level_id`."""
        return self._levels[level_id]
