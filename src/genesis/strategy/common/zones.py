"""Clasificación de zonas PRO/MID/CT a partir de un z-score de VWAP (R32-R35).

Implementación nueva (no porte): no existe `zones.py` ni lógica de clasificación
PRO/MID/CT en la fuente inspeccionada. Las 3 zonas se mantienen genéricas y
agnósticas al candidato (ADR-C6): la pierna PRO archivada para el Candidato A es
decisión de `candidate_a` (Issue F), no una limitación de este componente `common/`.
"""

from enum import StrEnum


class Zone(StrEnum):
    """Zona de clasificación de un z-score respecto al VWAP."""

    PRO = "pro"
    MID = "mid"
    CT = "ct"


def classify_zone(
    zscore: float,
    pro_zscore_max: float = 1.0,
    ct_zscore_min: float = 2.0,
) -> Zone:
    """Clasifica `zscore` en `Zone.PRO`/`Zone.MID`/`Zone.CT` por `abs(zscore)` (R34).

    Función pura: no lee ningún archivo de configuración ni depende de
    `VwapAnchorConfig`/`InspectorFunnelConfig`. Los umbrales se reciben como
    parámetros explícitos con defaults, nunca hardcodeados sin posibilidad de
    override (R33).

    - `Zone.PRO` si `abs(zscore) < pro_zscore_max`.
    - `Zone.MID` si `pro_zscore_max <= abs(zscore) < ct_zscore_min`.
    - `Zone.CT` si `abs(zscore) >= ct_zscore_min`.

    Lanza `ValueError` con ambos umbrales en el mensaje si
    `pro_zscore_max >= ct_zscore_min` (configuración de umbrales inconsistente,
    fail-fast, R35): nunca clasifica silenciosamente con umbrales invertidos.
    """
    if pro_zscore_max >= ct_zscore_min:
        message = (
            f"Umbrales de zona inconsistentes: pro_zscore_max={pro_zscore_max} debe "
            f"ser < ct_zscore_min={ct_zscore_min}."
        )
        raise ValueError(message)

    magnitude = abs(zscore)
    if magnitude < pro_zscore_max:
        return Zone.PRO
    if magnitude < ct_zscore_min:
        return Zone.MID
    return Zone.CT
