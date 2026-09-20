"""Fábricas de candidatos: construcción con firma uniforme desde parámetros nombrados.

La capa 4 (validación) no debe conocer la firma del constructor de ningún candidato
concreto. Mientras la conozca, queda atada a candidatos escritos a mano y no puede
recibir algo construido en runtime —un genoma compilado— por la misma vía que usa hoy
para el torneo. Este módulo define esa costura: una firma uniforme
`(figure, reference_balance, params) -> StrategyCandidate`, más la fábrica del
Candidato B como implementación por defecto.

Relación con `CANDIDATE_REGISTRY` (`contract.py`): no lo reemplaza ni lo toca. Aquel
mapea letra → **clase**, y las clases tienen constructores de firmas distintas; sirve
al torneo A/B/C y ahí se queda. Este módulo mapea `candidate_id` → **callable de firma
uniforme**, que es lo que permite inyectar un candidato que nadie escribió a mano.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import StrategyCandidate
from genesis.strategy.errors import CandidateFactoryError
from genesis.strategy.exit_geometry import ExitGeometry


@runtime_checkable
class ExitGeometryProvider(Protocol):
    """Fábricas que declaran su propia geometría de salida (C2, Change #109, `design.md` §1.4).

    El genoma gobierna la geometría de salida por candidato, no un JSON global: una
    `CandidateFactory` que implementa este puerto expone `exit_geometry` con
    `source=GENOME`, y `run_wfa` la prioriza sobre el `exit_geometry` de config
    (§D8 del diseño). Solo `GenomeCandidateFactory` lo implementa hoy.
    """

    @property
    def exit_geometry(self) -> ExitGeometry: ...


@runtime_checkable
class CandidateFactory(Protocol):
    """Construye un `StrategyCandidate` a partir de parámetros nombrados.

    `params` son los ejes del espacio de búsqueda, con nombre y no posicionales: es
    lo que permite que quien llama (hoy la grilla del torneo, mañana un genoma) no
    tenga que coincidir con el orden de argumentos de ningún constructor concreto.
    """

    def __call__(
        self,
        *,
        figure: SymbolFigure,
        reference_balance: float,
        params: Mapping[str, float],
    ) -> StrategyCandidate: ...


def _require(params: Mapping[str, float], key: str, candidate_id: str) -> float:
    """Lee `key` de `params` o lanza `CandidateFactoryError` con contexto (fail-fast)."""
    try:
        return params[key]
    except KeyError as exc:
        message = (
            f"La fábrica del candidato {candidate_id!r} exige el parámetro {key!r}, "
            f"ausente en params. Parámetros recibidos: {sorted(params)}."
        )
        raise CandidateFactoryError(message) from exc


def candidate_b_factory(
    *,
    figure: SymbolFigure,
    reference_balance: float,
    params: Mapping[str, float],
) -> StrategyCandidate:
    """Construye un `CandidateB` desde `params` (`n_minutes`, `atr_stop_frac`, `risk_pct`).

    `n_minutes` se convierte a `int` aquí, en el único punto que conoce el tipo real
    que el constructor de B espera: `params` es numérico y uniforme por contrato de
    `CandidateFactory`, y traducir a la firma concreta es justamente el trabajo de una
    fábrica.
    """
    return CandidateB(
        figure=figure,
        reference_balance=reference_balance,
        n_minutes=int(_require(params, "n_minutes", "B")),
        atr_stop_frac=float(_require(params, "atr_stop_frac", "B")),
        risk_pct=float(_require(params, "risk_pct", "B")),
        rvol_threshold=float(params.get("rvol_threshold", 0.0)),
        rvol_lookback_days=int(params.get("rvol_lookback_days", 20)),
    )


DEFAULT_CANDIDATE_FACTORIES: Mapping[str, CandidateFactory] = {"B": candidate_b_factory}
"""Fábricas por defecto del torneo, por `candidate_id`. Solo B es ejecutable hoy."""


def default_factory_for(candidate_id: str) -> CandidateFactory:
    """Fábrica por defecto de `candidate_id`, o `CandidateFactoryError` con contexto.

    Es el fallback que permite que los llamadores existentes (que ya pasan
    `candidate_id`) sigan funcionando sin inyectar nada. Quien tenga un candidato
    construido en runtime pasa su propia `CandidateFactory` y nunca llega acá.
    """
    try:
        return DEFAULT_CANDIDATE_FACTORIES[candidate_id]
    except KeyError as exc:
        message = (
            f"No hay fábrica por defecto para candidate_id={candidate_id!r}. "
            f"Disponibles: {sorted(DEFAULT_CANDIDATE_FACTORIES)}. Para un candidato "
            f"construido en runtime, inyecte una CandidateFactory explícita."
        )
        raise CandidateFactoryError(message) from exc
