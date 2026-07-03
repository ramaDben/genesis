"""Metadata de reproducibilidad institucional de la capa 1 (datos).

Todo artefacto de salida (Parquet crudo de `mt5_export.py`, reporte de `quality.py`)
registra, como mínimo, `config_version`, el hash del dataset/chunk, la ficha de firma (o
su hash), el rango temporal cubierto y el commit de git vigente (spec §3, R39).
"""

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from genesis.data.errors import GenesisDataError
from genesis.data.symbols import SymbolFigure

CONFIG_VERSION: str = "genesis-data/1"
"""Versión del esquema de configuración/metadata de esta capa (R39)."""


def sha256_of(payload: bytes) -> str:
    """Calcula el hash `sha256` hexadecimal del contenido crudo de `payload`.

    Determinista: la misma entrada produce siempre la misma salida (R7, R36).
    """
    return hashlib.sha256(payload).hexdigest()


def current_git_commit(repo_root: Path | None = None) -> str:
    """Retorna el hash completo del commit de git vigente en `repo_root`.

    Lanza `GenesisDataError` con contexto si no se puede determinar (repo sin commits,
    `git` no disponible, o `repo_root` fuera de un repositorio).
    """
    root = repo_root if repo_root is not None else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        message = f"No se pudo determinar el commit de git vigente en '{root}': {exc}"
        raise GenesisDataError(message) from exc
    return result.stdout.strip()


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Ficha de reproducibilidad adjunta a cada artefacto de salida de esta capa.

    Campos mínimos exigidos por R39: `config_version`, `dataset_hash` (hash del
    contenido crudo del chunk/dataset), `firm_profile_hash` (hash de la ficha de firma
    activa), `time_range` (rango temporal cubierto) y `git_commit` (commit vigente al
    generar el artefacto). `symbol_figure` es opcional (solo aplica a exports de MT5).
    """

    config_version: str
    dataset_hash: str
    firm_profile_hash: str
    time_range: tuple[datetime, datetime]
    git_commit: str
    symbol_figure: SymbolFigure | None = None

    def to_json(self) -> str:
        """Serializa la metadata a JSON, incluyendo `time_range` en ISO 8601 UTC."""
        payload = asdict(self)
        payload["time_range"] = [ts.astimezone(UTC).isoformat() for ts in self.time_range]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> ArtifactMetadata:
        """Reconstruye `ArtifactMetadata` desde el JSON producido por `to_json`.

        Lanza `GenesisDataError` con contexto si el JSON tiene un esquema inválido.
        """
        try:
            payload = json.loads(raw)
            start_raw, end_raw = payload["time_range"]
            time_range = (
                datetime.fromisoformat(start_raw),
                datetime.fromisoformat(end_raw),
            )
            figure_raw = payload["symbol_figure"]
            figure = SymbolFigure(**figure_raw) if figure_raw is not None else None
            return cls(
                config_version=payload["config_version"],
                dataset_hash=payload["dataset_hash"],
                firm_profile_hash=payload["firm_profile_hash"],
                time_range=time_range,
                git_commit=payload["git_commit"],
                symbol_figure=figure,
            )
        except (KeyError, ValueError, TypeError) as exc:
            message = f"Metadata de artefacto con esquema inválido: {exc}. JSON recibido: {raw!r}"
            raise GenesisDataError(message) from exc
