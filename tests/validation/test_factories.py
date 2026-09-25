"""Tests de la costura de inyección de candidatos (`genesis.strategy.factories`).

La costura existe para que la capa 4 pueda ejecutar un candidato que nadie escribió a
mano —un genoma compilado en runtime— por la misma vía que usa para el torneo A/B/C.
El test que de verdad prueba eso es `test_run_wfa_usa_la_fabrica_inyectada`: construye
un candidato que no está en `CANDIDATE_REGISTRY`, no hereda de nada y no vive en
`genesis.strategy.candidate_b`, y verifica que `run_wfa` lo ejecuta.
"""

from collections.abc import Mapping

import pandas as pd
import pytest

from genesis.backtest.costs import CostsConfig
from genesis.backtest.exit_geometry import ExitGeometry
from genesis.data.profile import FirmProfile
from genesis.data.store import AnnotatedBar, RawParquetStore
from genesis.data.symbols import SymbolFigure
from genesis.strategy.candidate_b.candidate import CandidateB
from genesis.strategy.contract import CANDIDATE_REGISTRY, CONFIG_VERSION, EntryIntent
from genesis.strategy.errors import CandidateFactoryError
from genesis.strategy.factories import (
    DEFAULT_CANDIDATE_FACTORIES,
    candidate_b_factory,
    default_factory_for,
)
from genesis.strategy.inspector import InspectorFunnelConfig
from genesis.validation.wfa import run_wfa
from genesis.validation.window_config import WfaWindowConfig

pytestmark = pytest.mark.unit

_PARAMS_B = {"n_minutes": 15.0, "atr_stop_frac": 1.0, "risk_pct": 0.00375}


def test_candidate_b_factory_construye_candidate_b(symbol_figure_fixture: SymbolFigure) -> None:
    candidate = candidate_b_factory(
        figure=symbol_figure_fixture, reference_balance=100_000.0, params=_PARAMS_B
    )
    assert isinstance(candidate, CandidateB)
    assert candidate.candidate_id == "B"


def test_candidate_b_factory_convierte_n_minutes_a_int(
    symbol_figure_fixture: SymbolFigure,
) -> None:
    """`params` es numérico y uniforme por contrato; la fábrica traduce al tipo real."""
    candidate = candidate_b_factory(
        figure=symbol_figure_fixture, reference_balance=100_000.0, params=_PARAMS_B
    )
    assert isinstance(candidate, CandidateB)
    assert isinstance(candidate._n_minutes, int)


@pytest.mark.parametrize("faltante", ["n_minutes", "atr_stop_frac", "risk_pct"])
def test_candidate_b_factory_param_faltante_lanza_con_contexto(
    symbol_figure_fixture: SymbolFigure, faltante: str
) -> None:
    """Fail-fast con contexto: nunca un `KeyError` opaco aguas adentro."""
    params = {k: v for k, v in _PARAMS_B.items() if k != faltante}
    with pytest.raises(CandidateFactoryError) as exc_info:
        candidate_b_factory(
            figure=symbol_figure_fixture, reference_balance=100_000.0, params=params
        )
    mensaje = str(exc_info.value)
    assert faltante in mensaje
    assert "B" in mensaje


def test_default_factory_for_b() -> None:
    assert default_factory_for("B") is candidate_b_factory


def test_default_factory_for_desconocido_lanza_con_contexto() -> None:
    with pytest.raises(CandidateFactoryError) as exc_info:
        default_factory_for("Z")
    mensaje = str(exc_info.value)
    assert "Z" in mensaje
    assert "B" in mensaje  # nombra las disponibles


def test_solo_b_tiene_fabrica_por_defecto() -> None:
    """Refleja el estado real del torneo: A no es ejecutable, C está diferido."""
    assert sorted(DEFAULT_CANDIDATE_FACTORIES) == ["B"]


class _CandidatoSinRegistrar:
    """Candidato construido en runtime: no está en `CANDIDATE_REGISTRY` ni hereda de nada.

    Satisface `StrategyCandidate` por tipado estructural (`candidate_id` + `on_bar`).
    Nunca emite señales: el objetivo del test es probar que la costura lo **ejecuta**,
    no que opere bien.
    """

    candidate_id: str = "GENOMA-TEST"

    def __init__(self) -> None:
        self.barras_vistas = 0

    def on_bar(self, bar: AnnotatedBar) -> list[EntryIntent]:
        self.barras_vistas += 1
        return []

    def risk_levels(self, intent: EntryIntent) -> tuple[float, float]:
        raise AssertionError("nunca emite señales, no debería pedirse risk_levels")


def test_candidato_inyectado_no_esta_en_el_registro_por_letra() -> None:
    """La costura no depende de `CANDIDATE_REGISTRY`: es una vía paralela."""
    assert _CandidatoSinRegistrar.candidate_id not in CANDIDATE_REGISTRY
    assert CONFIG_VERSION  # el contrato sigue siendo el mismo


def test_run_wfa_usa_la_fabrica_inyectada(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """La capa 4 ejecuta un candidato que no escribió nadie a mano (el objetivo de la costura).

    `run_wfa` falla con `WfaConfigError` porque un candidato que nunca opera no llega a
    `MIN_TRADES_IS` — y eso es exactamente la prueba: para llegar a esa guarda, el
    motor tuvo que instanciar y **correr** el candidato inyectado sobre las barras.
    """
    construidos: list[_CandidatoSinRegistrar] = []

    def fabrica_inyectada(
        *, figure: SymbolFigure, reference_balance: float, params: Mapping[str, float]
    ) -> _CandidatoSinRegistrar:
        candidato = _CandidatoSinRegistrar()
        construidos.append(candidato)
        return candidato

    from genesis.validation.errors import WfaConfigError

    with pytest.raises(WfaConfigError):
        run_wfa(
            "GENOMA-TEST",
            "US500",
            short_wfa_frame,
            firm_profile_fixture,
            exit_geometry_fixture,
            symbol_figure_fixture,
            funnel_config_fixture,
            costs_config_fixture,
            [],
            tick_store_fixture,
            None,
            100_000.0,
            window_config=reduced_window_config,
            candidate_factory=fabrica_inyectada,
            seed=7,
        )

    assert construidos, "la costura no instanció el candidato inyectado"
    assert sum(c.barras_vistas for c in construidos) > 0, "se instanció pero nunca se corrió"


def test_run_wfa_sin_fabrica_resuelve_por_candidate_id(
    firm_profile_fixture: FirmProfile,
    exit_geometry_fixture: ExitGeometry,
    symbol_figure_fixture: SymbolFigure,
    funnel_config_fixture: InspectorFunnelConfig,
    costs_config_fixture: CostsConfig,
    tick_store_fixture: RawParquetStore,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """Sin fábrica inyectada y con un `candidate_id` sin fábrica por defecto: fail-fast."""
    with pytest.raises(CandidateFactoryError):
        run_wfa(
            "Z",
            "US500",
            short_wfa_frame,
            firm_profile_fixture,
            exit_geometry_fixture,
            symbol_figure_fixture,
            funnel_config_fixture,
            costs_config_fixture,
            [],
            tick_store_fixture,
            None,
            100_000.0,
            window_config=reduced_window_config,
            seed=7,
        )
