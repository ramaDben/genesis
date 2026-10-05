#!/usr/bin/env python3
"""Enriquece determinísticamente los sidecars .meta.json de BTCUSDT con SymbolFigure."""

from __future__ import annotations

import json
from pathlib import Path

from genesis.data.metadata import ArtifactMetadata

BTCUSDT_FIGURE_PAYLOAD = {
    "symbol": "BTCUSDT",
    "tick_value": 0.10,
    "tick_size": 0.10,
    "volume_step": 0.001,
    "stops_level": 0,
    "freeze_level": 0,
    "digits": 1,
    "swap_long": 0.0,
    "swap_short": 0.0,
    "swap_rollover_day": 0,
}


def enrich_metadata(store_root: Path) -> int:
    sidecars = sorted((store_root / "BTCUSDT" / "m1").glob("*/*.meta.json"))
    if not sidecars:
        raise FileNotFoundError(
            f"No se encontraron sidecars en {store_root}/BTCUSDT/m1/*/*.meta.json"
        )

    count = 0
    for sidecar in sidecars:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        raw["symbol_figure"] = BTCUSDT_FIGURE_PAYLOAD
        serialized = json.dumps(raw, indent=2, sort_keys=True) + "\n"
        sidecar.write_text(serialized, encoding="utf-8")

        # Verificación inmediata de roundtrip
        meta = ArtifactMetadata.from_json(sidecar.read_text(encoding="utf-8"))
        if meta.symbol_figure is None or meta.symbol_figure.symbol != "BTCUSDT":
            raise ValueError(f"Falla de verificación en sidecar {sidecar}")
        if meta.symbol_figure.value_per_point != 1.0:
            raise ValueError(f"Invariante value_per_point rota en {sidecar}")
        count += 1

    return count


if __name__ == "__main__":
    store = Path("data/raw")
    n = enrich_metadata(store)
    print(f"Enriquecidos exitosamente {n} archivos .meta.json de BTCUSDT.")
