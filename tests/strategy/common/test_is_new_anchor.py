"""Tests de anclaje DST para `is_new_anchor` (R29).

Tabla paramétrica de 10 casos UTC para NY_MIDNIGHT con server_to_utc_offset=0, más
casos SERVER_MIDNIGHT y CUSTOM_HOUR. Portado de
`C:\\Users\\bbrav\\ABON\\vwap-smc-inspector\\python\\tests\\test_is_new_anchor.py` con
aserciones intactas (solo imports/rutas y el renombrado `InspectorConfig` ->
`VwapAnchorConfig`, `default_config` -> `default_vwap_anchor_config`).

Convención: bar_time naive UTC (convención de datasets MT5 exportados a Python).
Cubre transiciones DST EE.UU. 2024-2025.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from genesis.strategy.common.vwap_engine import (
    AnchorMode,
    default_vwap_anchor_config,
    is_new_anchor,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Config base con offset 0 (UTC directo, sin autodetección)
# ---------------------------------------------------------------------------

_CFG_NY = replace(
    default_vwap_anchor_config(),
    anchor_mode=AnchorMode.NY_MIDNIGHT,
    server_to_utc_offset=0,
)

_CFG_SERVER = replace(
    default_vwap_anchor_config(),
    anchor_mode=AnchorMode.SERVER_MIDNIGHT,
    server_to_utc_offset=-999,  # hora servidor = UTC naive del dataset
)

_CFG_CUSTOM_9 = replace(
    default_vwap_anchor_config(),
    anchor_mode=AnchorMode.CUSTOM_HOUR,
    custom_anchor_hour=9,
    server_to_utc_offset=-999,
)


def _utc(dt_str: str) -> datetime:
    """Convierte string ISO a datetime naive UTC (para simular dataset MT5)."""
    return datetime.fromisoformat(dt_str).replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Tabla — NY_MIDNIGHT con server_to_utc_offset=0
# Cubre ambos lados de las transiciones DST EE.UU. 2024-2025.
#
# DST 2024: inicio 2024-03-10 02:00 EST -> 03:00 EDT (UTC-5 -> UTC-4)
#           fin    2024-11-03 02:00 EDT -> 01:00 EST (UTC-4 -> UTC-5)
# DST 2025: inicio 2025-03-09 02:00 EST -> 03:00 EDT
#           fin    2025-11-02 02:00 EDT -> 01:00 EST
#
# Medianoche NY en invierno (EST, UTC-5): 05:00 UTC -> True
# Medianoche NY en verano  (EDT, UTC-4): 04:00 UTC -> True
# ---------------------------------------------------------------------------

_NY_CASES: list[tuple[str, bool]] = [
    ("2024-03-10 05:00", True),  # caso 1: 00:00 NY EST 2024 (UTC-5)
    ("2024-03-10 04:59", False),  # caso 2: 23:59 NY del día anterior (EST)
    ("2024-03-09 05:00", True),  # caso 3: 00:00 NY EST, día previo al DST
    ("2024-11-03 04:00", True),  # caso 4: 00:00 NY EDT, día de fin de DST
    ("2024-11-03 03:59", False),  # caso 5: 23:59 NY EDT del 2-nov
    ("2025-03-09 05:00", True),  # caso 6: 00:00 NY EST 2025, día previo al DST
    ("2025-03-10 04:00", True),  # caso 7: 00:00 NY EDT 2025
    ("2025-11-02 04:00", True),  # caso 8: 00:00 NY EST 2025, fin de DST
    ("2024-03-10 00:00", False),  # caso 9: 00:00 UTC NO es 00:00 NY
    ("2024-03-10 04:00", False),  # caso 10: 23:00 NY — no es anchor
]


@pytest.mark.parametrize("dt_str,expected", _NY_CASES)
def test_ny_midnight_dst_table(dt_str: str, expected: bool) -> None:
    """Tabla de 10 casos NY_MIDNIGHT con DST EE.UU. 2024-2025."""
    bar_time = _utc(dt_str)
    result = is_new_anchor(bar_time, _CFG_NY)
    assert result == expected, f"NY_MIDNIGHT {dt_str} UTC -> esperado {expected}, obtenido {result}"


# ---------------------------------------------------------------------------
# Casos SERVER_MIDNIGHT
# ---------------------------------------------------------------------------


def test_server_midnight_true() -> None:
    """SERVER_MIDNIGHT: 2024-03-10 00:00 UTC -> True."""
    bar_time = _utc("2024-03-10 00:00")
    assert is_new_anchor(bar_time, _CFG_SERVER) is True


def test_server_midnight_false() -> None:
    """SERVER_MIDNIGHT: 2024-03-10 01:00 UTC -> False."""
    bar_time = _utc("2024-03-10 01:00")
    assert is_new_anchor(bar_time, _CFG_SERVER) is False


def test_server_midnight_dst_independent() -> None:
    """SERVER_MIDNIGHT no depende de DST: cualquier 00:00 UTC es anchor."""
    for dt_str in ["2024-06-15 00:00", "2024-12-01 00:00", "2025-03-09 00:00"]:
        bar_time = _utc(dt_str)
        assert is_new_anchor(bar_time, _CFG_SERVER) is True, f"Falló en {dt_str}"


# ---------------------------------------------------------------------------
# Casos CUSTOM_HOUR = 9
# ---------------------------------------------------------------------------


def test_custom_hour_9_true() -> None:
    """CUSTOM_HOUR=9: 09:00 UTC -> True."""
    bar_time = _utc("2024-03-10 09:00")
    assert is_new_anchor(bar_time, _CFG_CUSTOM_9) is True


def test_custom_hour_9_false_5() -> None:
    """CUSTOM_HOUR=9: 05:00 UTC -> False."""
    bar_time = _utc("2024-03-10 05:00")
    assert is_new_anchor(bar_time, _CFG_CUSTOM_9) is False


def test_custom_hour_9_false_nonzero_minute() -> None:
    """CUSTOM_HOUR=9: 09:01 UTC -> False (solo el minuto 0 ancla)."""
    bar_time = _utc("2024-03-10 09:01")
    assert is_new_anchor(bar_time, _CFG_CUSTOM_9) is False


def test_custom_hour_no_dst() -> None:
    """CUSTOM_HOUR es UTC fijo: mismo resultado en verano e invierno."""
    cfg = replace(
        default_vwap_anchor_config(),
        anchor_mode=AnchorMode.CUSTOM_HOUR,
        custom_anchor_hour=9,
    )
    summer = _utc("2024-07-04 09:00")
    winter = _utc("2024-12-25 09:00")
    assert is_new_anchor(summer, cfg) is True
    assert is_new_anchor(winter, cfg) is True
