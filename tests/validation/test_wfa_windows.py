"""Tests de geometría de ventanas WFA: planificación, troceo, guarda de historia (R8-R11)."""

from itertools import pairwise

import pandas as pd
import pytest

from genesis.data.profile import FirmProfile
from genesis.validation.errors import WfaConfigError
from genesis.validation.wfa import (
    _iter_window_bounds,
    _plan_and_validate_windows,
    _plan_windows,
    _slice_frame_by_days,
)
from genesis.validation.window_config import WfaWindowConfig
from tests.validation.fixtures.long_m1_generator import generate_long_m1_frame

pytestmark = pytest.mark.unit


def test_historia_insuficiente_lanza_wfa_config_error_antes_de_backtest(
    firm_profile_fixture: FirmProfile,
    reduced_window_config: WfaWindowConfig,
) -> None:
    """R11: frame con menos trading_day que is+oos -> WfaConfigError, sin correr backtest."""
    short_frame = generate_long_m1_frame("US500", n_trading_days=3, seed=1)  # is=4+oos=2=6 > 3
    with pytest.raises(WfaConfigError):
        _plan_and_validate_windows(
            short_frame,
            "US500",
            firm_profile_fixture,
            reduced_window_config,
            candidate_id="B",
        )


def test_historia_suficiente_no_lanza(
    firm_profile_fixture: FirmProfile,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    days, row_span = _plan_and_validate_windows(
        short_wfa_frame, "US500", firm_profile_fixture, reduced_window_config, candidate_id="B"
    )
    assert len(days) == 10
    assert len(row_span) == 10


def test_ventanas_oos_contiguas_sin_solape(
    firm_profile_fixture: FirmProfile,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R9: el tramo OOS de la ventana k y el de k+1 son contiguos, sin solape ni hueco."""
    days, _row_span = _plan_and_validate_windows(
        short_wfa_frame, "US500", firm_profile_fixture, reduced_window_config, candidate_id="B"
    )
    bounds = list(_iter_window_bounds(len(days), reduced_window_config))
    assert len(bounds) >= 2  # 10 días, is=4/oos=2/step=2 -> varias ventanas resolubles

    for (_, is_start, is_end, oos_end), (_, next_is_start, _, _) in pairwise(bounds):
        # El tramo IS y OOS de la MISMA ventana no se solapan (OOS empieza donde IS termina).
        assert is_start < is_end < oos_end
        # El paso hacia la siguiente ventana es exactamente step_trading_days.
        assert next_is_start - is_start == reduced_window_config.step_trading_days

    oos_ranges = [(is_end, oos_end) for _, _, is_end, oos_end in bounds]
    for (_, end_k), (start_k1, _) in pairwise(oos_ranges):
        assert end_k == start_k1  # contiguo: sin solape ni hueco entre OOS_k y OOS_{k+1}


def test_troceo_frame_is_oos_respeta_fronteras(
    firm_profile_fixture: FirmProfile,
    reduced_window_config: WfaWindowConfig,
    short_wfa_frame: pd.DataFrame,
) -> None:
    """R10: `frame_is`/`frame_oos` no contienen filas fuera de sus fronteras de `trading_day`."""
    days, row_span = _plan_and_validate_windows(
        short_wfa_frame, "US500", firm_profile_fixture, reduced_window_config, candidate_id="B"
    )
    _k, is_start, is_end, oos_end = next(_iter_window_bounds(len(days), reduced_window_config))
    is_days = days[is_start:is_end]
    oos_days = days[is_end:oos_end]

    frame_is = _slice_frame_by_days(short_wfa_frame, row_span, is_days)
    frame_oos = _slice_frame_by_days(short_wfa_frame, row_span, oos_days)

    assert len(frame_is) > 0
    assert len(frame_oos) > 0
    # Ninguna fila de frame_is tiene timestamp posterior a la última fila de frame_oos.
    assert frame_is["timestamp"].max() < frame_oos["timestamp"].min()
    # frame_is + frame_oos son contiguos: la posición final de IS + 1 == posición inicial de OOS.
    assert frame_is.index[-1] + 1 == frame_oos.index[0]


def test_plan_windows_dias_ordenados_sin_duplicados(
    firm_profile_fixture: FirmProfile,
    short_wfa_frame: pd.DataFrame,
) -> None:
    days, _row_span = _plan_windows(short_wfa_frame, "US500", firm_profile_fixture)
    assert days == sorted(set(days))
    assert len(days) == len(set(days))
