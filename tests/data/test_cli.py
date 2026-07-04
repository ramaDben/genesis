"""Tests unitarios del CLI `mt5-export` (subcomandos `export`, `confirm-firm-profile`).

Ninguno de estos tests conecta con un terminal MT5 real: `_connect_real_terminal` se
reemplaza vía `monkeypatch` para simular tanto la ausencia del SDK como la ausencia de
un terminal conectado, sin depender del entorno de la máquina que ejecuta la suite.
"""

import pytest

from genesis.data import mt5_export
from genesis.data.mt5_export import main
from tests.data.fakes import (
    ACCOUNT_TRADE_MODE_DEMO,
    ACCOUNT_TRADE_MODE_REAL,
    FakeMt5Terminal,
)

pytestmark = pytest.mark.unit


def test_confirm_firm_profile_without_sdk_returns_diferido_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: None)
    exit_code = main(["confirm-firm-profile"])
    output = capsys.readouterr().out.lower()
    assert exit_code == 2
    assert "diferido" in output or "no bloqueante" in output


class _NonInitializingTerminal(FakeMt5Terminal):
    """Fake que simula SDK presente pero sin terminal MT5 conectado."""

    def initialize(self, *args: object, **kwargs: object) -> bool:
        return False

    def last_error(self) -> tuple[int, str]:
        return (1, "IPC initialize failed (fake: sin terminal conectado)")


def test_confirm_firm_profile_without_connected_terminal_returns_diferido_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: _NonInitializingTerminal())
    exit_code = main(["confirm-firm-profile"])
    output = capsys.readouterr().out.lower()
    assert exit_code == 2
    assert "diferido" in output or "no bloqueante" in output


def test_confirm_firm_profile_reports_discrepancies_without_correcting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["EURUSD"])
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    exit_code = main(["confirm-firm-profile"])
    output = capsys.readouterr().out.lower()
    assert exit_code == 1
    assert "us500" in output


def test_confirm_firm_profile_all_symbols_present_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal = FakeMt5Terminal(
        trade_mode=ACCOUNT_TRADE_MODE_DEMO,
        available_symbols=["US500", "US100", "US30", "GER40"],
    )
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    exit_code = main(["confirm-firm-profile"])
    assert exit_code == 0


def test_export_without_sdk_returns_nonzero(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: None)
    exit_code = main(
        [
            "export",
            "--symbols",
            "US500",
            "--start",
            "2024-03-01T00:00:00+00:00",
            "--end",
            "2024-03-01T00:05:00+00:00",
            "--out",
            str(tmp_path / "raw"),
        ]
    )
    assert exit_code == 2


def test_export_non_demo_account_returns_nonzero(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_REAL, available_symbols=["US500"])
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    exit_code = main(
        [
            "export",
            "--symbols",
            "US500",
            "--start",
            "2024-03-01T00:00:00+00:00",
            "--end",
            "2024-03-01T00:05:00+00:00",
            "--out",
            str(tmp_path / "raw"),
        ]
    )
    assert exit_code == 1


def test_export_succeeds_with_demo_fake_terminal(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    exit_code = main(
        [
            "export",
            "--symbols",
            "US500",
            "--start",
            "2024-03-01T00:00:00+00:00",
            "--end",
            "2024-03-01T00:05:00+00:00",
            "--out",
            str(tmp_path / "raw"),
        ]
    )
    assert exit_code == 0


def test_export_cli_default_schedule_mode_is_off(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def _fake_run_export(*_args: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    monkeypatch.setattr(mt5_export, "run_export", _fake_run_export)

    exit_code = main(
        [
            "export",
            "--symbols",
            "US500",
            "--start",
            "2024-03-01T00:00:00+00:00",
            "--end",
            "2024-03-01T00:05:00+00:00",
            "--out",
            str(tmp_path / "raw"),
        ]
    )
    assert exit_code == 0
    assert captured["schedule_mode"] == "off"


def test_export_cli_passes_explicit_schedule_mode_through_to_run_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured: dict[str, object] = {}

    def _fake_run_export(*_args: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    terminal = FakeMt5Terminal(trade_mode=ACCOUNT_TRADE_MODE_DEMO, available_symbols=["US500"])
    monkeypatch.setattr(mt5_export, "_connect_real_terminal", lambda: terminal)
    monkeypatch.setattr(mt5_export, "run_export", _fake_run_export)

    exit_code = main(
        [
            "export",
            "--symbols",
            "US500",
            "--start",
            "2024-03-01T00:00:00+00:00",
            "--end",
            "2024-03-01T00:05:00+00:00",
            "--out",
            str(tmp_path / "raw"),
            "--schedule-mode",
            "strict",
        ]
    )
    assert exit_code == 0
    assert captured["schedule_mode"] == "strict"
