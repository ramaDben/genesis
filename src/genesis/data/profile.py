"""Ficha de firma (`FirmProfile`) con los defaults conservadores del spec §1.3.

`profiles/the5ers.json` versiona los valores por defecto usados mientras PA-1
(símbolos MT5 exactos) y la confirmación de `daily_reset_time`/`daily_loss_limit`
siguen sin verificar contra una cuenta demo real (R42, R43). El pipeline (export,
sesiones, store) funciona correctamente solo con estos defaults.
"""

import hashlib
import importlib.resources
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time, timedelta
from pathlib import Path

from genesis.data.errors import GenesisDataError

_DEFAULT_PROFILE_PACKAGE = "genesis.data.profiles"
_DEFAULT_PROFILE_RESOURCE = "the5ers.json"


@dataclass(frozen=True, slots=True)
class SymbolAliases:
    """Símbolo MT5 esperado para un nombre convencional, más sus alias documentados."""

    expected: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FirmProfile:
    """Ficha de firma activa: cortes de día, límites de riesgo y tabla de símbolos.

    Los valores por defecto (`load_firm_profile()` sin argumentos) son los "default
    conservador" del spec §1.3: `daily_reset_time=00:00 America/New_York`,
    `daily_loss_limit_pct=5.0`. Confirmarlos contra una cuenta demo real es un paso
    humano diferido (`mt5-export confirm-firm-profile`), no bloqueante para este Change.
    """

    name: str
    daily_reset_time: time
    daily_reset_tz: str
    daily_loss_limit_pct: float
    server_tz: str
    symbols: Mapping[str, SymbolAliases]
    news_bracket_before: timedelta
    news_bracket_after: timedelta


def _parse_symbol_aliases(name: str, raw: dict[str, object]) -> SymbolAliases:
    try:
        expected = raw["expected"]
        aliases = raw["aliases"]
        if not isinstance(expected, str) or not isinstance(aliases, list):
            raise TypeError("'expected' debe ser str y 'aliases' una lista")
        alias_values = tuple(str(alias) for alias in aliases)
        return SymbolAliases(expected=expected, aliases=alias_values)
    except (KeyError, TypeError) as exc:
        message = f"Entrada de símbolo '{name}' inválida en la ficha de firma: {exc}"
        raise GenesisDataError(message) from exc


def load_firm_profile(path: Path | None = None) -> FirmProfile:
    """Carga la ficha de firma desde `path`, o desde `profiles/the5ers.json` por defecto.

    Lanza `GenesisDataError` con contexto (campo/símbolo faltante) si la ficha es
    inválida o está incompleta (fail-fast, R38).
    """
    if path is not None:
        raw_text = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        resource = importlib.resources.files(_DEFAULT_PROFILE_PACKAGE).joinpath(
            _DEFAULT_PROFILE_RESOURCE
        )
        raw_text = resource.read_text(encoding="utf-8")
        source = f"{_DEFAULT_PROFILE_PACKAGE}/{_DEFAULT_PROFILE_RESOURCE}"

    try:
        payload = json.loads(raw_text)
        symbols_raw = payload["symbols"]
        symbols = {name: _parse_symbol_aliases(name, entry) for name, entry in symbols_raw.items()}
        hour, minute, second = (int(part) for part in payload["daily_reset_time"].split(":"))
        return FirmProfile(
            name=payload["name"],
            daily_reset_time=time(hour, minute, second),
            daily_reset_tz=payload["daily_reset_tz"],
            daily_loss_limit_pct=float(payload["daily_loss_limit_pct"]),
            server_tz=payload["server_tz"],
            symbols=symbols,
            news_bracket_before=timedelta(minutes=float(payload["news_bracket_before_minutes"])),
            news_bracket_after=timedelta(minutes=float(payload["news_bracket_after_minutes"])),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Ficha de firma inválida/incompleta en '{source}': {exc}"
        raise GenesisDataError(message) from exc


def firm_profile_hash(profile: FirmProfile) -> str:
    """Hash `sha256` determinista de la ficha de firma activa (insumo de `ArtifactMetadata`)."""
    canonical = {
        "name": profile.name,
        "daily_reset_time": profile.daily_reset_time.isoformat(),
        "daily_reset_tz": profile.daily_reset_tz,
        "daily_loss_limit_pct": profile.daily_loss_limit_pct,
        "server_tz": profile.server_tz,
        "symbols": {
            name: {"expected": aliases.expected, "aliases": list(aliases.aliases)}
            for name, aliases in sorted(profile.symbols.items())
        },
        "news_bracket_before_seconds": profile.news_bracket_before.total_seconds(),
        "news_bracket_after_seconds": profile.news_bracket_after.total_seconds(),
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
