"""Tests de paridad numérica del motor VWAP — Capas 1 y 2 (R30).

Portado de
`C:\\Users\\bbrav\\ABON\\vwap-smc-inspector\\python\\tests\\test_vwap_parity.py`, acotado
a Capa 1 (`TestManualReference`, `TestDegenerateCA9`) y Capa 2
(`TestLayer2InternalConsistency` sobre `fixtures/sample_m1.csv`). `TestDefaultConfig`/
`TestLoadConfig` se adaptan para verificar únicamente los 5 campos de
`VwapAnchorConfig` (no los 19 de `InspectorConfig` de la fuente). La capa de
paridad MQL5<->Python de la fuente NO se porta (ADR-C5, §4.3 del design): no existe
`fixtures/mql5_reference.csv` y su marcador de pytest no está registrado en
`pyproject.toml` (`--strict-markers`).
"""

import csv
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from genesis.strategy.common.vwap_engine import (
    AnchorMode,
    VwapAnchorConfig,
    VWAPState,
    default_vwap_anchor_config,
    load_vwap_anchor_config,
    update_vwap,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# TestDefaultConfig / TestLoadConfig — adaptados a los 5 campos de VwapAnchorConfig
# ---------------------------------------------------------------------------


class TestDefaultConfig:
    """Verifica que `default_vwap_anchor_config()` retorna los 5 valores exactos (R25)."""

    def test_config_version(self) -> None:
        assert default_vwap_anchor_config().config_version == "2.0.0"

    def test_anchor_mode(self) -> None:
        cfg = default_vwap_anchor_config()
        assert cfg.anchor_mode == AnchorMode.NY_MIDNIGHT
        assert int(cfg.anchor_mode) == 0

    def test_vwap_warmup_bars(self) -> None:
        assert default_vwap_anchor_config().vwap_warmup_bars == 45

    def test_custom_anchor_hour(self) -> None:
        assert default_vwap_anchor_config().custom_anchor_hour == 0

    def test_server_to_utc_offset(self) -> None:
        assert default_vwap_anchor_config().server_to_utc_offset == -999


class TestLoadConfig:
    """Verifica carga desde JSON y validación de `config_version` (R26)."""

    def test_load_vwap_anchor_config_valid(self, tmp_path: Path) -> None:
        """`load_vwap_anchor_config` carga un JSON válido con los 5 campos."""
        payload = tmp_path / "vwap_anchor_config.json"
        payload.write_text(
            '{"config_version": "2.0.0", "anchor_mode": 0, "vwap_warmup_bars": 45, '
            '"custom_anchor_hour": 0, "server_to_utc_offset": -999}',
            encoding="utf-8",
        )
        cfg = load_vwap_anchor_config(payload)
        assert cfg.config_version == "2.0.0"
        assert cfg.anchor_mode == AnchorMode.NY_MIDNIGHT
        assert cfg.server_to_utc_offset == -999

    def test_load_vwap_anchor_config_missing_version(self, tmp_path: Path) -> None:
        """`load_vwap_anchor_config` lanza `ValueError` si falta `config_version`."""
        bad = tmp_path / "bad.json"
        bad.write_text('{"anchor_mode": 0}', encoding="utf-8")
        with pytest.raises(ValueError, match="config_version"):
            load_vwap_anchor_config(bad)

    def test_load_vwap_anchor_config_missing_fields_usa_defaults(self, tmp_path: Path) -> None:
        """Campos ausentes (salvo `config_version`) se completan con los defaults R25."""
        payload = tmp_path / "partial.json"
        payload.write_text('{"config_version": "2.0.0"}', encoding="utf-8")
        cfg = load_vwap_anchor_config(payload)
        defaults = default_vwap_anchor_config()
        assert cfg.vwap_warmup_bars == defaults.vwap_warmup_bars
        assert cfg.anchor_mode == defaults.anchor_mode
        assert cfg.custom_anchor_hour == defaults.custom_anchor_hour
        assert cfg.server_to_utc_offset == defaults.server_to_utc_offset


# ---------------------------------------------------------------------------
# Capa 1 — valores de referencia manuales (CA5)
# ---------------------------------------------------------------------------


def _ref_vwap_sigma(prices: list[float], volumes: list[int]) -> list[tuple[float, float, float]]:
    """Calcula (sv, vwap, sigma) acumulado tras cada vela (todas cerradas)."""
    s_v = s_pv = s_p2v = 0.0
    results = []
    for p, v in zip(prices, volumes, strict=False):
        s_v += v
        s_pv += p * v
        s_p2v += p * p * v
        vwap = s_pv / s_v
        var = max(s_p2v / s_v - vwap * vwap, 0.0)
        sigma = math.sqrt(var)
        results.append((s_v, vwap, sigma))
    return results


_PRICES = [100.0, 101.0, 102.0, 101.0, 100.0]
_VOLUMES = [10, 20, 15, 25, 10]
_REF = _ref_vwap_sigma(_PRICES, _VOLUMES)


def _rel_err(py_val: float, ref: float) -> float:
    return abs(py_val - ref) / max(abs(ref), 1e-10)


class TestManualReference:
    """CA5 — Paridad capa 1 con valores de referencia algebraicos."""

    def _run_sequence(self, cfg: VwapAnchorConfig) -> list:
        state = VWAPState()
        results = []
        for p, v in zip(_PRICES, _VOLUMES, strict=True):
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
            results.append(r)
        return results

    def test_manual_reference_vwap(self) -> None:
        """VWAP acumulado coincide con referencia IEEE 754 dentro de 1e-9 relativo."""
        cfg = default_vwap_anchor_config()
        results = self._run_sequence(cfg)
        for i, (r, (_sv, vwap_ref, _sigma_ref)) in enumerate(zip(results, _REF, strict=True)):
            err = _rel_err(r.vwap, vwap_ref)
            assert err <= 1e-9, f"Vela {i + 1}: vwap error={err:.2e} py={r.vwap} ref={vwap_ref}"

    def test_manual_reference_sigma(self) -> None:
        """Sigma acumulado coincide con referencia dentro de 1e-9 relativo."""
        cfg = default_vwap_anchor_config()
        results = self._run_sequence(cfg)
        for i, (r, (_sv, _vwap_ref, sigma_ref)) in enumerate(zip(results, _REF, strict=True)):
            err = _rel_err(r.sigma, sigma_ref)
            assert err <= 1e-9, f"Vela {i + 1}: sigma error={err:.2e} py={r.sigma} ref={sigma_ref}"

    def test_manual_reference_bands_symmetric(self) -> None:
        """Bandas son simétricas respecto al VWAP."""
        cfg = default_vwap_anchor_config()
        results = self._run_sequence(cfg)
        for i, r in enumerate(results):
            for k, (up, dn) in enumerate(
                [
                    (r.band_1up, r.band_1dn),
                    (r.band_2up, r.band_2dn),
                    (r.band_3up, r.band_3dn),
                ]
            ):
                diff_up = abs((up - r.vwap) - (r.vwap - dn))
                assert diff_up < 1e-12, f"Vela {i + 1} banda {k + 1}: asimetría={diff_up}"

    def test_manual_reference_is_valid(self) -> None:
        """is_valid=True cuando total_v>0."""
        cfg = default_vwap_anchor_config()
        results = self._run_sequence(cfg)
        for i, r in enumerate(results):
            assert r.is_valid is True, f"Vela {i + 1}: is_valid={r.is_valid}"


# ---------------------------------------------------------------------------
# Caso degenerado CA9: Sigma==0, precios idénticos
# ---------------------------------------------------------------------------


class TestDegenerateCA9:
    """CA9 — sigma=0, zscore=0, is_valid=True, bandas colapsadas."""

    def test_ca9_sigma_zero(self) -> None:
        cfg = default_vwap_anchor_config()
        state = VWAPState()
        prices = [100.0, 100.0, 100.0]
        volumes = [10, 20, 15]
        results = []
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
            results.append(r)
        for i, r in enumerate(results):
            assert r.sigma == 0.0, f"Vela {i + 1}: sigma={r.sigma}"
            assert r.zscore == 0.0, f"Vela {i + 1}: zscore={r.zscore}"
            assert r.is_valid is True, f"Vela {i + 1}: is_valid={r.is_valid}"
            assert r.band_1up == r.vwap, f"Vela {i + 1}: band_1up={r.band_1up} != vwap={r.vwap}"
            assert r.band_1dn == r.vwap, f"Vela {i + 1}: band_1dn={r.band_1dn} != vwap={r.vwap}"


# ---------------------------------------------------------------------------
# Capa 2 — consistencia interna sobre fixture sintético
# ---------------------------------------------------------------------------


def _load_sample_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestLayer2InternalConsistency:
    """Capa 2 (CA12) — consistencia interna sobre `sample_m1.csv`."""

    @pytest.fixture(autouse=True)
    def _require_fixture(self, sample_m1_path: Path) -> None:
        if not sample_m1_path.exists():
            pytest.skip("sample_m1.csv no disponible")

    def test_sigma_non_negative(self, sample_m1_path: Path) -> None:
        """sigma >= 0 en cada vela del fixture."""
        cfg = default_vwap_anchor_config()
        state = VWAPState()
        rows = _load_sample_csv(sample_m1_path)
        prev_dt = None
        for row in rows:
            dt = datetime.fromisoformat(row["time"].rstrip("Z")).replace(tzinfo=UTC)
            is_anchor = prev_dt is None or (dt.hour == 0 and dt.minute == 0)
            r = update_vwap(
                state,
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                tick_volume=int(row["tick_volume"]),
                bar_closed=True,
                is_anchor=is_anchor,
                config=cfg,
            )
            assert r.sigma >= 0.0, f"sigma negativo en {dt}: {r.sigma}"
            prev_dt = dt

    def test_bands_symmetric(self, sample_m1_path: Path) -> None:
        """Bandas simétricas respecto al VWAP."""
        cfg = default_vwap_anchor_config()
        state = VWAPState()
        rows = _load_sample_csv(sample_m1_path)
        prev_dt = None
        for row in rows:
            dt = datetime.fromisoformat(row["time"].rstrip("Z")).replace(tzinfo=UTC)
            is_anchor = prev_dt is None or (dt.hour == 0 and dt.minute == 0)
            r = update_vwap(
                state,
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                tick_volume=int(row["tick_volume"]),
                bar_closed=True,
                is_anchor=is_anchor,
                config=cfg,
            )
            if r.is_valid and r.sigma > 0:
                assert abs((r.band_1up - r.vwap) - (r.vwap - r.band_1dn)) < 1e-12
            prev_dt = dt

    def test_s_v_non_decreasing_intra_session(self, sample_m1_path: Path) -> None:
        """s_v no decrece dentro de cada sesión."""
        cfg = default_vwap_anchor_config()
        state = VWAPState()
        rows = _load_sample_csv(sample_m1_path)
        prev_sv = 0.0
        prev_dt = None
        for row in rows:
            dt = datetime.fromisoformat(row["time"].rstrip("Z")).replace(tzinfo=UTC)
            is_anchor = prev_dt is None or (dt.hour == 0 and dt.minute == 0)
            if is_anchor:
                prev_sv = 0.0
            update_vwap(
                state,
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                tick_volume=int(row["tick_volume"]),
                bar_closed=True,
                is_anchor=is_anchor,
                config=cfg,
            )
            assert state.s_v >= prev_sv - 1e-15, f"s_v decreció en {dt}: {state.s_v} < {prev_sv}"
            prev_sv = state.s_v
            prev_dt = dt
