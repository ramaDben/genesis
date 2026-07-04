"""Test de `RealMt5Terminal` contra el SDK real, marcado `integration`+`slow` (R51).

`pytest.importorskip("MetaTrader5")` salta automáticamente este test en un entorno sin
el SDK instalado (no falla). Deliberadamente **no** se invoca `initialize()` ni ningún
otro método que conecte con un terminal MT5 real: este es un smoke test puramente
estructural (verifica que `RealMt5Terminal` se instancia e implementa la superficie de
`Mt5Terminal` sin arrastrar I/O de red), evitando cualquier interacción con una cuenta
MT5 real que pueda estar conectada en la máquina que ejecuta la suite.
"""

import pytest

pytest.importorskip("MetaTrader5")

from genesis.data.mt5_export import RealMt5Terminal

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_PROTOCOL_METHODS = (
    "initialize",
    "shutdown",
    "last_error",
    "account_info",
    "symbols_get",
    "symbol_info",
    "copy_rates_range",
    "copy_ticks_range",
)


def test_real_mt5_terminal_instantiates_and_implements_protocol_surface() -> None:
    """Instancia `RealMt5Terminal` (import perezoso del SDK) sin conectar a ningún terminal."""
    terminal = RealMt5Terminal()
    for method_name in _PROTOCOL_METHODS:
        assert callable(getattr(terminal, method_name))
