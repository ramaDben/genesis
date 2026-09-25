"""Ficha de firma (`FirmProfile`) con los defaults conservadores del spec §1.3.

`profiles/the5ers.json` versiona los valores por defecto usados mientras PA-1
(símbolos MT5 exactos) y la confirmación de `daily_reset_time`/`house_rule`
siguen sin verificar contra una cuenta demo real (R42, R43). El pipeline (export,
sesiones, store) funciona correctamente solo con estos defaults.

Desde el Change #109, la ficha embebe el contrato de la casa (`HouseRule`, capa 1):
`house_rule is None` no significa "falta el dato", significa "esta ficha describe un
exchange u otro venue sin reglas de casa" (p.ej. `binance_futures.json`). Solo una
ficha con `house_rule` declarado habilita una evaluación prop (capa 3/4).
"""

import hashlib
import importlib.resources
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import time, timedelta
from pathlib import Path
from typing import Any

from genesis.data.errors import GenesisDataError
from genesis.data.house_rule import (
    ConsistencyRule,
    ConsistencySemantics,
    DailyLossLimit,
    DailyLossLimitSemantics,
    HouseRule,
    MaxLossLimit,
    MaxLossLimitKind,
    house_rule_hash,
)

CONFIG_VERSION: str = "genesis-data-firm-profile/2"
"""Versión del esquema de la ficha de firma (Change #109: `house_rule` embebido)."""

_DEFAULT_PROFILE_PACKAGE = "genesis.data.profiles"
_DEFAULT_PROFILE_RESOURCE = "the5ers.json"


@dataclass(frozen=True, slots=True)
class SymbolAliases:
    """Símbolo esperado para un nombre convencional, más sus alias documentados."""

    expected: str
    aliases: tuple[str, ...]


def resolve_symbol_alias(
    conventional_name: str,
    available_symbols: Sequence[str],
    expected_table: Mapping[str, SymbolAliases],
) -> str:
    """Resuelve el símbolo de mercado real para `conventional_name`.

    Intenta primero el símbolo esperado (`expected_table[conventional_name].expected`);
    si no está en `available_symbols`, prueba los alias documentados en orden. Si nada
    coincide, o si `conventional_name` no está documentado en `expected_table`, lanza
    `GenesisDataError` con contexto (símbolo buscado, candidatos probados, disponibles).
    """
    if conventional_name not in expected_table:
        message = (
            f"Símbolo convencional '{conventional_name}' no está documentado en la tabla de "
            f"la ficha de firma. Símbolos documentados: {sorted(expected_table)}."
        )
        raise GenesisDataError(message)

    aliases = expected_table[conventional_name]
    candidates = (aliases.expected, *aliases.aliases)
    for candidate in candidates:
        if candidate in available_symbols:
            return candidate

    message = (
        f"No se encontró símbolo para '{conventional_name}' entre los candidatos "
        f"{candidates} ni en los símbolos disponibles del feed: {list(available_symbols)}."
    )
    raise GenesisDataError(message)


@dataclass(frozen=True, slots=True)
class FirmProfile:
    """Ficha de firma activa: cortes de día, contrato de la casa y tabla de símbolos.

    Los valores por defecto (`load_firm_profile()` sin argumentos) son los "default
    conservador" del spec §1.3. `house_rule is None` significa que esta ficha no
    describe una prop firm (ver docstring del módulo).
    """

    name: str
    daily_reset_time: time
    daily_reset_tz: str
    server_tz: str
    symbols: Mapping[str, SymbolAliases]
    news_bracket_before: timedelta
    news_bracket_after: timedelta
    house_rule: HouseRule | None


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


def _parse_max_loss_limit(raw: dict[str, Any]) -> MaxLossLimit:
    return MaxLossLimit(amount=float(raw["amount"]), kind=MaxLossLimitKind(raw["kind"]))


def _parse_daily_loss_limit(raw: dict[str, Any] | None) -> DailyLossLimit | None:
    if raw is None:
        return None
    return DailyLossLimit(
        amount=float(raw["amount"]),
        semantics=DailyLossLimitSemantics(raw["semantics"]),
    )


def _parse_consistency_rule(raw: dict[str, Any] | None) -> ConsistencyRule | None:
    if raw is None:
        return None
    return ConsistencyRule(pct=float(raw["pct"]), semantics=ConsistencySemantics(raw["semantics"]))


def _parse_weekend_holding_allowed(raw: object) -> bool:
    """Coerción estricta: solo un `bool` real es válido (sin truthiness de Python).

    Un `"false"` (string no vacía) es truthy en Python y se leería como `True`; un
    `null` se leería silenciosamente como `False`. Ambos deben fallar, no colarse.
    """
    if not isinstance(raw, bool):
        raise TypeError(f"'weekend_holding_allowed' debe ser un booleano, recibido: {raw!r}")
    return raw


def _parse_house_rule(source: str, raw: dict[str, Any] | None) -> HouseRule | None:
    """Parsea el bloque `house_rule` de la ficha; `raw is None` es un caso válido (§D2)."""
    if raw is None:
        return None
    try:
        return HouseRule(
            max_loss_limit=_parse_max_loss_limit(raw["max_loss_limit"]),
            threshold_lock_at=(
                None if raw.get("threshold_lock_at") is None else float(raw["threshold_lock_at"])
            ),
            daily_loss_limit=_parse_daily_loss_limit(raw.get("daily_loss_limit")),
            consistency_rule=_parse_consistency_rule(raw.get("consistency_rule")),
            weekend_holding_allowed=_parse_weekend_holding_allowed(raw["weekend_holding_allowed"]),
            payout_buffer=float(raw["payout_buffer"]),
            min_net_profit_between_payouts=float(raw["min_net_profit_between_payouts"]),
            funded_starting_balance=float(raw["funded_starting_balance"]),
            account_size=float(raw["account_size"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        message = f"Bloque 'house_rule' inválido/incompleto en '{source}': {exc}"
        raise GenesisDataError(message) from exc


def load_firm_profile(path: Path | None = None) -> FirmProfile:
    """Carga la ficha de firma desde `path`, o desde `profiles/the5ers.json` por defecto.

    Exige `config_version == "genesis-data-firm-profile/2"`: ausente o distinto falla
    con el valor esperado y el recibido en el mensaje (R11). Lanza `GenesisDataError`
    con contexto (campo/símbolo faltante) si la ficha es inválida o está incompleta
    (fail-fast, R38).
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
        received_version = payload.get("config_version")
        if received_version != CONFIG_VERSION:
            message = (
                f"Ficha de firma en '{source}' con config_version inválido: "
                f"esperado {CONFIG_VERSION!r}, recibido {received_version!r}"
            )
            raise GenesisDataError(message)
        if "house_rule" not in payload:
            message = (
                f"Ficha de firma en '{source}' sin la clave 'house_rule' "
                "(usar null explícito si no es una prop firm)."
            )
            raise GenesisDataError(message)
        symbols_raw = payload["symbols"]
        symbols = {name: _parse_symbol_aliases(name, entry) for name, entry in symbols_raw.items()}
        hour, minute, second = (int(part) for part in payload["daily_reset_time"].split(":"))
        house_rule = _parse_house_rule(source, payload["house_rule"])
        return FirmProfile(
            name=payload["name"],
            daily_reset_time=time(hour, minute, second),
            daily_reset_tz=payload["daily_reset_tz"],
            server_tz=payload["server_tz"],
            symbols=symbols,
            news_bracket_before=timedelta(minutes=float(payload["news_bracket_before_minutes"])),
            news_bracket_after=timedelta(minutes=float(payload["news_bracket_after_minutes"])),
            house_rule=house_rule,
        )
    except GenesisDataError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Ficha de firma inválida/incompleta en '{source}': {exc}"
        raise GenesisDataError(message) from exc


def firm_profile_hash(profile: FirmProfile) -> str:
    """Hash `sha256` determinista de la ficha de firma activa (insumo de `ArtifactMetadata`).

    Compone `house_rule_hash(profile.house_rule)` como un campo más del diccionario
    canónico (D2, R4): un cambio del contrato de la casa invalida la procedencia de
    la ficha completa. `house_rule is None` se representa como `None`.

    **Incluye `funded_starting_balance` aparte del hash delegado** (contrato DH-4,
    `tasks.md`): `house_rule_hash` lo excluye a propósito porque no tiene consumidor
    funcional todavía (issue #112), pero la procedencia de la ficha completa sí debe
    distinguir dos fichas que solo difieren en ese campo.
    """
    canonical = {
        "name": profile.name,
        "daily_reset_time": profile.daily_reset_time.isoformat(),
        "daily_reset_tz": profile.daily_reset_tz,
        "server_tz": profile.server_tz,
        "symbols": {
            name: {"expected": aliases.expected, "aliases": list(aliases.aliases)}
            for name, aliases in sorted(profile.symbols.items())
        },
        "news_bracket_before_seconds": profile.news_bracket_before.total_seconds(),
        "news_bracket_after_seconds": profile.news_bracket_after.total_seconds(),
        "house_rule": None if profile.house_rule is None else house_rule_hash(profile.house_rule),
        "funded_starting_balance": (
            None if profile.house_rule is None else profile.house_rule.funded_starting_balance
        ),
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
