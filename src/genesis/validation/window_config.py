"""Geometría de ventanas walk-forward y presupuesto de grid IS (R6-R13).

Esquema único, rolling (no expandible), para todos los símbolos del Candidato B
(decisión 1 de `spec.md` §3): `IS_WINDOW_TRADING_DAYS = 252` (~12 meses
bursátiles), `OOS_WINDOW_TRADING_DAYS = 126` (~6 meses), `STEP_TRADING_DAYS = 126`
(= ancho OOS ⇒ ventanas OOS contiguas, sin solape ni huecos). El grid IS del
Candidato B es exhaustivo y mecánico: 27 combinaciones de ejecución agrupadas en 9
configuraciones de señal (spec §6.2); ampliarlo requiere un Change propio que
actualice el spec.
"""

import hashlib
import json
from dataclasses import dataclass

from genesis.validation.errors import WfaConfigError

IS_WINDOW_TRADING_DAYS: int = 252
"""Ancho del tramo IS en `trading_day` (~12 meses bursátiles, decisión 1 §3)."""

OOS_WINDOW_TRADING_DAYS: int = 126
"""Ancho del tramo OOS en `trading_day` (~6 meses bursátiles, decisión 1 §3)."""

STEP_TRADING_DAYS: int = 126
"""Paso entre ventanas: igual al ancho OOS ⇒ tramos OOS contiguos, sin solape/hueco."""

_MAX_EXECUTION_COMBOS = 27
"""Techo mecánico inviolable de combinaciones de ejecución por ventana (spec §6.2)."""

_MAX_SIGNAL_CONFIGS = 9
"""Techo mecánico inviolable de configuraciones de señal por ventana (spec §6.2)."""


@dataclass(frozen=True, slots=True)
class WfaWindowConfig:
    """Geometría de una ventana walk-forward rolling (R7).

    Los tres campos deben ser enteros positivos; en caso contrario, `__post_init__`
    lanza `WfaConfigError` con contexto.
    """

    is_window_trading_days: int = IS_WINDOW_TRADING_DAYS
    oos_window_trading_days: int = OOS_WINDOW_TRADING_DAYS
    step_trading_days: int = STEP_TRADING_DAYS

    def __post_init__(self) -> None:
        field_names = ("is_window_trading_days", "oos_window_trading_days", "step_trading_days")
        for field_name in field_names:
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                message = (
                    f"WfaWindowConfig.{field_name}={value!r} debe ser un entero positivo (R7)."
                )
                raise WfaConfigError(message)


@dataclass(frozen=True, slots=True)
class GridConfig:
    """Presupuesto del grid IS exhaustivo del Candidato B (R12, spec §6.2).

    `n_minutes_levels × atr_stop_frac_levels` fija las 9 configuraciones de señal;
    agregar `risk_pct_levels` fija las 27 combinaciones de ejecución (3 `risk_pct`
    por configuración de señal). `__post_init__` lanza `WfaConfigError` si se supera
    cualquiera de los dos techos mecánicos.
    """

    n_minutes_levels: tuple[int, ...] = (5, 15, 30)
    atr_stop_frac_levels: tuple[float, ...] = (0.5, 1.0, 1.5)
    risk_pct_levels: tuple[float, ...] = (0.0025, 0.00375, 0.005)

    def __post_init__(self) -> None:
        n_signal = len(self.n_minutes_levels) * len(self.atr_stop_frac_levels)
        n_execution = n_signal * len(self.risk_pct_levels)
        if n_signal > _MAX_SIGNAL_CONFIGS:
            message = (
                f"GridConfig produce n_signal={n_signal} configuraciones de señal "
                f"(n_minutes_levels={self.n_minutes_levels!r}, "
                f"atr_stop_frac_levels={self.atr_stop_frac_levels!r}), supera el techo "
                f"mecánico de {_MAX_SIGNAL_CONFIGS} (R12, spec §6.2)."
            )
            raise WfaConfigError(message)
        if n_execution > _MAX_EXECUTION_COMBOS:
            message = (
                f"GridConfig produce n_execution={n_execution} combinaciones de ejecución "
                f"(n_minutes_levels={self.n_minutes_levels!r}, "
                f"atr_stop_frac_levels={self.atr_stop_frac_levels!r}, "
                f"risk_pct_levels={self.risk_pct_levels!r}), supera el techo mecánico de "
                f"{_MAX_EXECUTION_COMBOS} (R12, spec §6.2)."
            )
            raise WfaConfigError(message)

    def signal_configs(self) -> list[tuple[int, float]]:
        """Las `N × atr_stop_frac` configuraciones de señal (len == 9 por defecto)."""
        return [
            (n_minutes, atr_stop_frac)
            for n_minutes in self.n_minutes_levels
            for atr_stop_frac in self.atr_stop_frac_levels
        ]

    def execution_combos(self) -> list[tuple[int, float, float]]:
        """Las `N × atr_stop_frac × risk_pct` combinaciones de ejecución (len == 27 por defecto)."""
        return [
            (n_minutes, atr_stop_frac, risk_pct)
            for n_minutes, atr_stop_frac in self.signal_configs()
            for risk_pct in self.risk_pct_levels
        ]


def _grid_config_hash(grid_config: GridConfig) -> str:
    """Hash `sha256` determinista de los tres tuples de niveles de `grid_config` (R13)."""
    canonical = {
        "n_minutes_levels": list(grid_config.n_minutes_levels),
        "atr_stop_frac_levels": list(grid_config.atr_stop_frac_levels),
        "risk_pct_levels": list(grid_config.risk_pct_levels),
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def window_identity_hash(
    candidate_id: str,
    symbol: str,
    dataset_hash_is: str,
    dataset_hash_oos: str,
    grid_config_hash: str,
    config_version: str,
) -> str:
    """Hash `sha256` determinista por ventana (R13, decisión 6 §3).

    Campo informativo de `WindowResult`, insumo de una extensión futura de runs
    reanudables; **no** se persiste a disco en este Change (R66).
    """
    canonical = {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "dataset_hash_is": dataset_hash_is,
        "dataset_hash_oos": dataset_hash_oos,
        "grid_config_hash": grid_config_hash,
        "config_version": config_version,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
