"""Esquema de datos inmutable para la representación declarativa de estrategias."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from genesis.strategy.genome.errors import (
    GenomeValidationError,
    MissingAcademicProvenanceError,
    UnknownRiskExitParamError,
)

_RISK_EXIT_PARAM_ALLOWLIST: Mapping[str, frozenset[str]] = {
    "chandelier_trailing": frozenset(
        {"lookback_bars", "atr_multiplier", "atr_stop_frac", "atr_period", "tp_rr_multiple"}
    ),
}
"""Allowlist de `risk_exit.params` por `kind` (D5 diseño, R8). Solo `chandelier_trailing`
tiene allowlist declarada hoy: otros `kind` pasan sin restricción hasta que tengan la
suya propia — no es una laxitud, es que ningún otro `kind` está implementado aún."""

_CHANDELIER_REQUIRED_PARAMS: tuple[str, ...] = ("lookback_bars", "atr_multiplier")
"""`chandelier_trailing` exige estas dos claves sin default silencioso (§1.4 del diseño):
el genoma es quien gobierna la geometría de salida, y un default acá reintroduciría el
mismo defecto de "parámetro muerto" que R8 ataca."""


class GenomeFidelity(StrEnum):
    """Grado de fidelidad respecto a la regla publicada (RFC §5.3)."""

    CANONICAL = "canonical"
    INTERPRETED = "interpreted"
    OPTIMIZED = "optimized"
    COMBINED = "combined"


@dataclass(frozen=True, slots=True)
class GenomeMetadata:
    """Metadatos de procedencia y trazabilidad intelectual (D1)."""

    id: str
    author: str
    paper_ref: str
    economic_rationale: str
    fidelity: GenomeFidelity


@dataclass(frozen=True, slots=True)
class GenomeUniverse:
    """Especificación de activo, temporalidad y sesión de trading."""

    symbol: str
    timeframe: str
    session: str


@dataclass(frozen=True, slots=True)
class GenomeAlpha:
    """Reglas de generación de señal alfa (régimen y trigger de entrada)."""

    regime_filter: Mapping[str, Any] | None
    entry_trigger: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class GenomeRiskExit:
    """Política de gestión de riesgo y salida."""

    kind: str
    params: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StrategyGenome:
    """Genoma declarativo completo de una estrategia cuantitativa."""

    metadata: GenomeMetadata
    universe: GenomeUniverse
    alpha: GenomeAlpha
    risk_exit: GenomeRiskExit
    raw_config: Mapping[str, Any]


def parse_genome(source: Path | str | Mapping[str, Any]) -> StrategyGenome:
    """Parsea y valida exhaustivamente una especificación de genoma declarativo."""
    raw_data: Any
    if isinstance(source, Path):
        try:
            content = source.read_text(encoding="utf-8")
            raw_data = yaml.safe_load(content)
        except Exception as exc:
            msg = f"Error reading or parsing YAML file {source}: {exc}"
            raise GenomeValidationError(msg) from exc
    elif isinstance(source, str):
        try:
            p = Path(source)
            if "\n" not in source and p.is_file():
                content = p.read_text(encoding="utf-8")
                raw_data = yaml.safe_load(content)
            else:
                raw_data = yaml.safe_load(source)
        except Exception as exc:
            raise GenomeValidationError(f"Error parsing YAML string: {exc}") from exc
    elif isinstance(source, Mapping):
        raw_data = source
    else:
        raise GenomeValidationError(f"Unsupported source type: {type(source)}")

    if not isinstance(raw_data, Mapping):
        raise GenomeValidationError(f"Genome YAML must be a mapping, got {type(raw_data).__name__}")

    # 1. Validar metadata
    metadata_dict = raw_data.get("metadata")
    if not isinstance(metadata_dict, Mapping):
        raise GenomeValidationError("Missing or invalid 'metadata' section")

    paper_ref = metadata_dict.get("paper_ref")
    if paper_ref is None or not str(paper_ref).strip():
        raise MissingAcademicProvenanceError(
            "Field 'paper_ref' is required and cannot be empty (academic provenance D1)"
        )

    fidelity_raw = metadata_dict.get("fidelity")
    if fidelity_raw is None:
        raise MissingAcademicProvenanceError("Field 'fidelity' is required in metadata")
    try:
        fidelity = GenomeFidelity(fidelity_raw)
    except ValueError as exc:
        valid_fidelities = [f.value for f in GenomeFidelity]
        raise MissingAcademicProvenanceError(
            f"Invalid fidelity: {fidelity_raw!r}. Must be one of {valid_fidelities}"
        ) from exc

    genome_id = metadata_dict.get("id")
    if not genome_id or not str(genome_id).strip():
        raise GenomeValidationError("Field 'id' is required in metadata")

    author = metadata_dict.get("author")
    if not author or not str(author).strip():
        raise GenomeValidationError("Field 'author' is required in metadata")

    metadata = GenomeMetadata(
        id=str(genome_id).strip(),
        author=str(author).strip(),
        paper_ref=str(paper_ref).strip(),
        economic_rationale=str(metadata_dict.get("economic_rationale", "")).strip(),
        fidelity=fidelity,
    )

    # 2. Validar universe
    universe_dict = raw_data.get("universe")
    if not isinstance(universe_dict, Mapping):
        raise GenomeValidationError("Missing or invalid 'universe' section")

    symbol = universe_dict.get("symbol")
    timeframe = universe_dict.get("timeframe")
    session = universe_dict.get("session")
    if not symbol or not str(symbol).strip():
        raise GenomeValidationError("Field 'symbol' is required in universe")
    if not timeframe or not str(timeframe).strip():
        raise GenomeValidationError("Field 'timeframe' is required in universe")
    if not session or not str(session).strip():
        raise GenomeValidationError("Field 'session' is required in universe")

    universe = GenomeUniverse(
        symbol=str(symbol).strip(),
        timeframe=str(timeframe).strip(),
        session=str(session).strip(),
    )

    # 3. Validar alpha
    alpha_dict = raw_data.get("alpha")
    if not isinstance(alpha_dict, Mapping):
        raise GenomeValidationError("Missing or invalid 'alpha' section")

    entry_trigger = alpha_dict.get("entry_trigger")
    if not isinstance(entry_trigger, Mapping):
        raise GenomeValidationError("Missing or invalid 'entry_trigger' in alpha section")

    regime_filter = alpha_dict.get("regime_filter")
    if regime_filter is not None and not isinstance(regime_filter, Mapping):
        raise GenomeValidationError("Field 'regime_filter' must be a mapping or null")

    alpha = GenomeAlpha(
        regime_filter=regime_filter,
        entry_trigger=entry_trigger,
    )

    # 4. Validar risk_exit
    risk_exit_dict = raw_data.get("risk_exit")
    if not isinstance(risk_exit_dict, Mapping):
        raise GenomeValidationError("Missing or invalid 'risk_exit' section")

    risk_kind = risk_exit_dict.get("kind")
    if not risk_kind or not str(risk_kind).strip():
        raise GenomeValidationError("Field 'kind' is required in risk_exit section")

    risk_params = risk_exit_dict.get("params", {})
    if not isinstance(risk_params, Mapping):
        raise GenomeValidationError("Field 'params' must be a mapping in risk_exit section")

    normalized_kind = str(risk_kind).strip()
    allowed_params = _RISK_EXIT_PARAM_ALLOWLIST.get(normalized_kind)
    if allowed_params is not None:
        for param_key in risk_params:
            if param_key not in allowed_params:
                raise UnknownRiskExitParamError(
                    f"Clave desconocida {param_key!r} en risk_exit.params para "
                    f"kind={normalized_kind!r}; admitidas: {sorted(allowed_params)}."
                )
    if normalized_kind == "chandelier_trailing":
        for required_key in _CHANDELIER_REQUIRED_PARAMS:
            if required_key not in risk_params:
                raise GenomeValidationError(
                    f"risk_exit.params.{required_key} es obligatorio para "
                    "kind='chandelier_trailing' (sin default silencioso, R9)."
                )

    risk_exit = GenomeRiskExit(
        kind=str(risk_kind).strip(),
        params=risk_params,
    )

    return StrategyGenome(
        metadata=metadata,
        universe=universe,
        alpha=alpha,
        risk_exit=risk_exit,
        raw_config=dict(raw_data),
    )
