"""`CandidateBConfig` + `load_candidate_b_config` (R48, R49, R72, R73).

Importa solo stdlib + `genesis.strategy.errors`: este módulo no depende de
`genesis.backtest` (capa 3) ni de `genesis.strategy.inspector`/`common` (aislamiento
del candidato, spec §2.1/§2.5). Réplica del patrón `load_inspector_funnel_config`
(`inspector.py:117-143`), leyendo el namespace `candidates.B.*` del **mismo** recurso
empaquetado `inspector_config.json` (R49).
"""

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from genesis.strategy.errors import CandidateBConfigError

_CONFIG_PACKAGE = "genesis.strategy"
_CONFIG_RESOURCE = "inspector_config.json"


@dataclass(frozen=True, slots=True)
class CandidateBConfig:
    """Punto de referencia de configuración del Candidato B (R72, R141).

    `atr_stop_frac` es el único campo nullable: `None` fuerza la regla primaria de
    stop (extremo opuesto del rango, R66) en lugar de la regla alternativa por ATR.
    `rvol_threshold` y `rvol_lookback_days` gobiernan el filtro de liquidez Gao et al. (R137).
    """

    n_minutes: int
    atr_stop_frac: float | None
    risk_pct: float
    atr_period: int
    tp_rr_multiple: float
    rvol_threshold: float = 1.50
    rvol_lookback_days: int = 20


def load_candidate_b_config(path: Path | None = None) -> CandidateBConfig:
    """Carga `CandidateBConfig` desde `payload["candidates"]["B"]` (R73, R141).

    `path=None` -> recurso empaquetado `genesis.strategy/inspector_config.json`
    (mismo recurso que `load_inspector_funnel_config`, patrón `inspector.py:117-143`,
    R49). Lanza `CandidateBConfigError` con contexto (campo faltante/inválido +
    fuente) si el namespace `candidates.B` falta o está incompleto — nunca
    degradación silenciosa (R73). No construye `CandidateB`: solo la configuración.
    """
    if path is not None:
        raw_text = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        resource = resources.files(_CONFIG_PACKAGE).joinpath(_CONFIG_RESOURCE)
        raw_text = resource.read_text(encoding="utf-8")
        source = f"{_CONFIG_PACKAGE}/{_CONFIG_RESOURCE}"

    try:
        payload = json.loads(raw_text)
        section = payload["candidates"]["B"]
        raw_frac = section["atr_stop_frac"]
        rvol_thresh = float(section.get("rvol_threshold", 1.50))
        rvol_lookback = int(section.get("rvol_lookback_days", 20))
        if rvol_thresh <= 0.0:
            raise ValueError(f"rvol_threshold debe ser positivo, vino {rvol_thresh}")
        if rvol_lookback < 1:
            raise ValueError(f"rvol_lookback_days debe ser >= 1, vino {rvol_lookback}")
        return CandidateBConfig(
            n_minutes=int(section["n_minutes"]),
            atr_stop_frac=None if raw_frac is None else float(raw_frac),
            risk_pct=float(section["risk_pct"]),
            atr_period=int(section["atr_period"]),
            tp_rr_multiple=float(section["tp_rr_multiple"]),
            rvol_threshold=rvol_thresh,
            rvol_lookback_days=rvol_lookback,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Configuración candidates.B.* inválida/incompleta en '{source}': {exc}"
        raise CandidateBConfigError(message) from exc
