"""Tests de propiedad con hypothesis para el motor VWAP (CA6-CA9, CA11, R28).

Portado de `C:\\Users\\bbrav\\ABON\\vwap-smc-inspector\\python\\tests\\test_vwap_properties.py`
con aserciones idénticas a la fuente; solo cambian imports/rutas y el renombrado
`InspectorConfig` -> `VwapAnchorConfig`, `default_config` -> `default_vwap_anchor_config`.

Invariantes verificadas con >=1000 ejemplos:
- CA6: sigma >= 0 siempre (clamp efectivo).
- CA7: reset en is_anchor=True -> s_v==0 y bars_since_anchor==0.
- CA8: is_valid==False cuando todos los volúmenes desde anchor son 0.
- CA9: zscore==0 y bandas colapsadas cuando sigma==0 y total_v>0.
- CA11: is_warmed_up==False para bars_since_anchor < warmup; True en el umbral.
"""

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from genesis.strategy.common.vwap_engine import (
    VWAPState,
    default_vwap_anchor_config,
    update_vwap,
)

pytestmark = pytest.mark.unit

# Configuración base reutilizable en todas las propiedades
_CFG = default_vwap_anchor_config()

# Estrategias compartidas
_prices = st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
_volumes = st.integers(min_value=1, max_value=10_000)
_price_list = st.lists(_prices, min_size=2, max_size=50)
_volume_list = st.lists(_volumes, min_size=2, max_size=50)


# ---------------------------------------------------------------------------
# CA6 — sigma >= 0 siempre (clamp de la varianza)
# ---------------------------------------------------------------------------


@given(prices=_price_list, volumes=_volume_list)
@settings(max_examples=1000, deadline=None)
def test_sigma_non_negative(prices: list[float], volumes: list[int]) -> None:
    """CA6: sigma >= 0 para cualquier secuencia de precios y volúmenes positivos."""
    state = VWAPState()
    for p, v in zip(prices, volumes, strict=False):
        r = update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=v,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
        if r.is_valid:
            assert r.sigma >= 0.0, f"sigma negativo: {r.sigma} (p={p}, v={v})"


# ---------------------------------------------------------------------------
# CA7 — Reset en is_anchor=True: s_v==0 y bars_since_anchor==0
# ---------------------------------------------------------------------------


@given(prices=_price_list, volumes=_volume_list)
@settings(max_examples=1000, deadline=None)
def test_anchor_reset(prices: list[float], volumes: list[int]) -> None:
    """CA7: tras update_vwap con is_anchor=True, state.s_v==0 y bars_since_anchor==0."""
    state = VWAPState()
    for p, v in zip(prices[:-1], volumes[:-1], strict=False):
        update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=v,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
    p_last = prices[-1]
    v_last = volumes[-1]
    update_vwap(
        state,
        high=p_last,
        low=p_last,
        close=p_last,
        tick_volume=v_last,
        bar_closed=True,
        is_anchor=True,
        config=_CFG,
    )
    assert state.s_v == float(v_last), (
        f"s_v después de anchor={state.s_v}, esperado={float(v_last)}"
    )
    assert state.bars_since_anchor == 1, (
        f"bars_since_anchor después de anchor={state.bars_since_anchor}, esperado=1"
    )


@given(prices=_price_list, volumes=_volume_list)
@settings(max_examples=1000, deadline=None)
def test_anchor_reset_state_before_commit(prices: list[float], volumes: list[int]) -> None:
    """CA7 variante: is_anchor=True con bar_closed=False -> s_v==0 (no commit)."""
    state = VWAPState()
    for p, v in zip(prices[:-1], volumes[:-1], strict=False):
        update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=v,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
    p_last = prices[-1]
    v_last = volumes[-1]
    update_vwap(
        state,
        high=p_last,
        low=p_last,
        close=p_last,
        tick_volume=v_last,
        bar_closed=False,
        is_anchor=True,
        config=_CFG,
    )
    assert state.s_v == 0.0, f"s_v después de anchor sin cerrar={state.s_v}, esperado=0.0"
    assert state.bars_since_anchor == 0, (
        f"bars_since_anchor después de anchor sin cerrar={state.bars_since_anchor}"
    )


# ---------------------------------------------------------------------------
# CA8 — is_valid==False cuando todos los volúmenes desde anchor son 0
# ---------------------------------------------------------------------------


@given(prices=_price_list)
@settings(max_examples=1000, deadline=None)
def test_invalid_when_all_volumes_zero(prices: list[float]) -> None:
    """CA8: is_valid==False cuando tick_volume=0 en todas las velas desde anchor."""
    state = VWAPState()
    for p in prices:
        r = update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=0,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
        assert r.is_valid is False, (
            f"is_valid debería ser False con volumen 0 acumulado, obtenido True (p={p})"
        )


# ---------------------------------------------------------------------------
# CA9 — zscore==0 y bandas colapsadas cuando sigma==0 y total_v>0
# ---------------------------------------------------------------------------


@given(
    price=st.integers(min_value=1, max_value=10000),
    n_bars=st.integers(min_value=1, max_value=30),
    volume=_volumes,
)
@settings(max_examples=1000, deadline=None)
def test_sigma_zero_zscore_zero(price: int, n_bars: int, volume: int) -> None:
    """CA9: con precios idénticos (enteros, exactamente representables) sigma==0.

    Usa precios enteros para evitar residuos de cancelación de punto flotante.
    Con P entero: var = P^2 - P^2 = 0 exactamente en IEEE 754.
    """
    p = float(price)
    state = VWAPState()
    for _ in range(n_bars):
        r = update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=volume,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
    assert r.sigma == 0.0, f"sigma debería ser 0 con precios idénticos: {r.sigma}"
    assert r.zscore == 0.0, f"zscore debería ser 0 cuando sigma==0: {r.zscore}"
    assert r.is_valid is True, "is_valid debe ser True cuando total_v > 0"
    assert r.band_1up == r.vwap, f"band_1up={r.band_1up} != vwap={r.vwap}"
    assert r.band_1dn == r.vwap, f"band_1dn={r.band_1dn} != vwap={r.vwap}"
    assert r.band_2up == r.vwap, f"band_2up={r.band_2up} != vwap={r.vwap}"
    assert r.band_2dn == r.vwap, f"band_2dn={r.band_2dn} != vwap={r.vwap}"


# ---------------------------------------------------------------------------
# CA11 — Warm-up: is_warmed_up==False para bars_since_anchor < warmup_bars;
#         True cuando bars_since_anchor >= warmup_bars
# ---------------------------------------------------------------------------


@given(
    prices=_price_list,
    volumes=_volume_list,
    warmup=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=1000, deadline=None)
def test_warmup_threshold(prices: list[float], volumes: list[int], warmup: int) -> None:
    """CA11: is_warmed_up respeta exactamente el umbral vwap_warmup_bars."""
    cfg = replace(_CFG, vwap_warmup_bars=warmup)
    state = VWAPState()
    results_closed = []
    for p, v in zip(prices, volumes, strict=False):
        r = update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=v,
            bar_closed=True,
            is_anchor=False,
            config=cfg,
        )
        results_closed.append((state.bars_since_anchor, r.is_warmed_up))

    for bars, warmed in results_closed:
        if bars < warmup:
            assert warmed is False, (
                f"is_warmed_up=True con bars_since_anchor={bars} < warmup={warmup}"
            )
        else:
            assert warmed is True, (
                f"is_warmed_up=False con bars_since_anchor={bars} >= warmup={warmup}"
            )


# ---------------------------------------------------------------------------
# Propiedad: s_v monotónicamente no decreciente dentro de sesión
# ---------------------------------------------------------------------------


@given(prices=_price_list, volumes=_volume_list)
@settings(max_examples=1000, deadline=None)
def test_sv_non_decreasing_intra_session(prices: list[float], volumes: list[int]) -> None:
    """s_v no decrece dentro de la misma sesión (sin anchor intermedio)."""
    state = VWAPState()
    prev_sv = 0.0
    for p, v in zip(prices, volumes, strict=False):
        update_vwap(
            state,
            high=p,
            low=p,
            close=p,
            tick_volume=v,
            bar_closed=True,
            is_anchor=False,
            config=_CFG,
        )
        assert state.s_v >= prev_sv - 1e-15, f"s_v decreció: {state.s_v} < {prev_sv}"
        prev_sv = state.s_v
