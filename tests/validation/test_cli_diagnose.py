"""CLI `genesis-validate diagnose` — guard de placeholder + subcomando (T5.5, R107, R121)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from genesis.validation.signal_diagnostic import main
from tests.data.fakes import _default_symbol_figure

pytestmark = pytest.mark.unit


def _write_input_csv(path: Path) -> None:
    timestamps = pd.date_range("2024-01-02 10:00:00", periods=20, freq="min")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 20,
            "high": [100.2] * 20,
            "low": [99.8] * 20,
            "close": [100.0] * 20,
            "tick_volume": [10] * 20,
        }
    )
    frame.to_csv(path, index=False)


def test_xauusd_sin_bandera_placeholder_falla_sin_producir_informe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_csv = tmp_path / "input.csv"
    _write_input_csv(input_csv)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "diagnose",
            "--candidate",
            "A",
            "--firm",
            "The5ers",
            "--symbol",
            "XAUUSD",
            "--session-label",
            "london_ny_overlap",
            "--input-csv",
            str(input_csv),
            "--data-root",
            str(tmp_path / "data_root"),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code != 0
    assert not out_dir.exists() or not (out_dir / "report.json").exists()
    stderr = capsys.readouterr().err
    assert "XAUUSD" in stderr


def test_xauusd_con_bandera_placeholder_produce_informe_marcado(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    _write_input_csv(input_csv)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "diagnose",
            "--candidate",
            "A",
            "--firm",
            "The5ers",
            "--symbol",
            "XAUUSD",
            "--session-label",
            "london_ny_overlap",
            "--input-csv",
            str(input_csv),
            "--data-root",
            str(tmp_path / "data_root"),
            "--out",
            str(out_dir),
            "--allow-placeholder-figures",
        ]
    )

    assert exit_code == 0
    report_path = out_dir / "report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["symbol_figure_is_placeholder"] is True


def test_indice_sin_figure_json_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_csv = tmp_path / "input.csv"
    _write_input_csv(input_csv)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "diagnose",
            "--candidate",
            "A",
            "--firm",
            "The5ers",
            "--symbol",
            "US500",
            "--session-label",
            "us_session",
            "--input-csv",
            str(input_csv),
            "--data-root",
            str(tmp_path / "data_root"),
            "--out",
            str(out_dir),
        ]
    )
    assert exit_code != 0
    assert not (out_dir / "report.json").exists()


def test_indice_con_figure_json_produce_informe_no_placeholder(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    _write_input_csv(input_csv)
    out_dir = tmp_path / "out"
    figure_json = tmp_path / "figure.json"
    figure = _default_symbol_figure("US500")
    figure_json.write_text(
        json.dumps(
            {
                "symbol": figure.symbol,
                "tick_value": figure.tick_value,
                "tick_size": figure.tick_size,
                "volume_step": figure.volume_step,
                "stops_level": figure.stops_level,
                "freeze_level": figure.freeze_level,
                "digits": figure.digits,
                "swap_long": figure.swap_long,
                "swap_short": figure.swap_short,
                "swap_rollover_day": figure.swap_rollover_day,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "diagnose",
            "--candidate",
            "A",
            "--firm",
            "The5ers",
            "--symbol",
            "US500",
            "--session-label",
            "us_session",
            "--input-csv",
            str(input_csv),
            "--data-root",
            str(tmp_path / "data_root"),
            "--out",
            str(out_dir),
            "--figure-json",
            str(figure_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["symbol_figure_is_placeholder"] is False


def test_firm_no_coincidente_falla(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    _write_input_csv(input_csv)

    exit_code = main(
        [
            "diagnose",
            "--candidate",
            "A",
            "--firm",
            "OtraFirma",
            "--symbol",
            "US500",
            "--session-label",
            "us_session",
            "--input-csv",
            str(input_csv),
            "--data-root",
            str(tmp_path / "data_root"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert exit_code != 0
