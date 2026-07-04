"""Motor VWAP incremental portado de `vwap-smc-inspector` (R22-R27).

Módulo de dominio puro: solo stdlib (`math`, `dataclasses`, `datetime`, `zoneinfo`,
`enum`). No importa `numpy` ni ninguna librería externa (R27).

Fuente: `C:\\Users\\bbrav\\ABON\\vwap-smc-inspector\\python\\vwap_engine.py` (459
líneas). El algoritmo íntegro de `is_new_anchor`/`update_vwap`/`AnchorMode`/
`VWAPState`/`VWAPResult` se preserva SIN CAMBIOS FUNCIONALES (R22); la red de tests
portada (`tests/strategy/common/test_vwap_engine_properties.py`,
`test_is_new_anchor.py`, `test_vwap_parity.py`) verifica la equivalencia numérica
(paridad IEEE 754 ≤ 1e-9 relativo, Capas 1-2).

**Única desviación funcional/de firma respecto a la fuente (R24)**: el tipo
`InspectorConfig` de la fuente (19 campos: anclaje/warmup del VWAP + `smc_engine` +
`risk` del Candidato A) se renombra y recorta a `VwapAnchorConfig`, que conserva
EXACTAMENTE los 5 campos de anclaje/warmup (`config_version`, `anchor_mode`,
`vwap_warmup_bars`, `custom_anchor_hour`, `server_to_utc_offset`). Los 14 campos
restantes (`fractal_n`, `eq_tolerance_atr`, `sweep_tolerance_atr`, `sweep_window_k`,
`sweep_validity_m`, `free_path_radius_sigma`, `ct_zscore_min`, `min_rr`,
`sl_buffer_atr`, `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `atr_period`,
`session_filter`) pertenecen al namespace `candidates.A.*` (Issues D/F), fuera de
alcance de este Change (ADR-C5).

Otras adaptaciones son puramente de estilo para el lint del repo, sin cambio de
comportamiento (§7.2 del design): `timezone.utc` -> `UTC`, `timedelta` subido al
bloque de imports del módulo, `slots=True` en los dataclasses frozen.

Paridad MQL5<->Python <= 1e-9 relativo citada como nota de procedencia (no como test
ejecutable en este Change; la Capa 3 de paridad MQL5 queda diferida, ADR-C5, §4.3).
Anti-lookahead estructural: acumuladores committed (`s_v`/`s_pv`/`s_p2v`) solo se
actualizan al cerrar vela (`bar_closed=True`).
"""

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Enumeración de modos de anclaje
# ---------------------------------------------------------------------------


class AnchorMode(IntEnum):
    """Modo de anclaje del VWAP diario.

    NY_MIDNIGHT: medianoche hora de Nueva York (con DST automático vía IANA).
    SERVER_MIDNIGHT: medianoche en la hora servidor MT5 (sin conversión de zona).
    CUSTOM_HOUR: hora UTC fija configurada en `custom_anchor_hour` (sin DST).
    """

    NY_MIDNIGHT = 0
    SERVER_MIDNIGHT = 1
    CUSTOM_HOUR = 2


# ---------------------------------------------------------------------------
# Configuración de anclaje/warmup del VWAP (subconjunto renombrado, R23-R24)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VwapAnchorConfig:
    """Subconjunto de anclaje/warmup de la `InspectorConfig` de la fuente portada.

    Renombrado de `InspectorConfig` (R24); conserva EXACTAMENTE los 5 campos de
    anclaje/warmup del VWAP. Los 14 campos restantes de la fuente (`fractal_n`,
    `eq_tolerance_atr`, `sweep_tolerance_atr`, `sweep_window_k`, `sweep_validity_m`,
    `free_path_radius_sigma`, `ct_zscore_min`, `min_rr`, `sl_buffer_atr`,
    `tp_ct_mode`, `trail_timeframe`, `risk_percent`, `atr_period`,
    `session_filter`) pertenecen al namespace `candidates.A.*` (Issues D/F), fuera
    de alcance de este Change (R23, ADR-C5).
    """

    config_version: str
    """Versión SemVer de la estructura de configuración (e.g. '2.0.0')."""

    anchor_mode: AnchorMode
    """Modo de anclaje del VWAP diario."""

    vwap_warmup_bars: int
    """Número de velas cerradas necesarias para considerar el VWAP calentado."""

    custom_anchor_hour: int
    """Hora UTC (0-23) para el anchor en modo CUSTOM_HOUR.

    Ignorado si `anchor_mode != CUSTOM_HOUR`. Sin ajuste DST; la zona horaria es
    responsabilidad del operador.
    """

    server_to_utc_offset: int
    """Offset en minutos del servidor MT5 respecto a UTC.

    Centinela -999 indica autodetección dinámica (UTC directo cuando el dataset ya
    viene en UTC naive). Rango explícito válido: [-720, +720].
    """


def default_vwap_anchor_config() -> VwapAnchorConfig:
    """Retorna los 5 defaults exactos de anclaje/warmup portados de la fuente (R25).

    Renombrado de `default_config()` de la fuente. No realiza I/O.
    """
    return VwapAnchorConfig(
        config_version="2.0.0",
        anchor_mode=AnchorMode.NY_MIDNIGHT,
        vwap_warmup_bars=45,
        custom_anchor_hour=0,
        server_to_utc_offset=-999,
    )


def load_vwap_anchor_config(path: str | Path) -> VwapAnchorConfig:
    """Carga y valida los 5 campos de `VwapAnchorConfig` desde `path` (R26).

    Renombrado de `load_config()` de la fuente, acotado a los 5 campos portados.

    Lanza `ValueError` si el campo `config_version` está ausente o vacío. Los campos
    ausentes en el JSON se completan con los defaults de `default_vwap_anchor_config()`.

    Args:
        path: Ruta al archivo JSON de configuración.

    Returns:
        `VwapAnchorConfig` validado e inmutable.

    Raises:
        ValueError: Si `config_version` está ausente en el JSON.
        FileNotFoundError: Si el archivo no existe.
        json.JSONDecodeError: Si el archivo no es JSON válido.
    """
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        data: dict = json.load(fh)

    if "config_version" not in data or not data["config_version"]:
        raise ValueError("config_version ausente en el recurso de configuración de anclaje VWAP")

    defaults = default_vwap_anchor_config()
    return VwapAnchorConfig(
        config_version=str(data.get("config_version", defaults.config_version)),
        anchor_mode=AnchorMode(int(data.get("anchor_mode", int(defaults.anchor_mode)))),
        vwap_warmup_bars=int(data.get("vwap_warmup_bars", defaults.vwap_warmup_bars)),
        custom_anchor_hour=int(data.get("custom_anchor_hour", defaults.custom_anchor_hour)),
        server_to_utc_offset=int(data.get("server_to_utc_offset", defaults.server_to_utc_offset)),
    )


# ---------------------------------------------------------------------------
# Estado mutable del motor VWAP
# ---------------------------------------------------------------------------

_NY_TZ = ZoneInfo("America/New_York")


@dataclass
class VWAPState:
    """Acumuladores committed del motor VWAP (solo velas cerradas).

    Es mutable (`update_vwap` lo muta in-place). Solo contiene sumas de velas
    cerradas; los valores del tick en curso se calculan en temporales dentro de
    `update_vwap` para garantizar la invariante anti-lookahead.

    Permanece sin `slots=True` (RI-1, H6 del tasks.md): colisiona con
    `field(default_factory=...)` de `anchor_time` en la combinación usada por este
    módulo; es un value object interno mutable, no un tipo de dominio público.
    """

    s_v: float = 0.0
    """Suma acumulada de volúmenes de velas cerradas desde el último anchor."""

    s_pv: float = 0.0
    """Suma acumulada de precio_típico × volumen de velas cerradas."""

    s_p2v: float = 0.0
    """Suma acumulada de precio_típico² × volumen de velas cerradas."""

    bars_since_anchor: int = 0
    """Número de velas cerradas desde el último anchor (para cálculo de warm-up)."""

    is_warmed_up: bool = False
    """True cuando `bars_since_anchor >= vwap_warmup_bars`."""

    anchor_time: datetime = field(default_factory=lambda: datetime(1970, 1, 1, tzinfo=UTC))
    """Timestamp UTC del último anchor procesado."""


# ---------------------------------------------------------------------------
# Resultado inmutable de cada llamada a update_vwap
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VWAPResult:
    """Resultado de una llamada a `update_vwap` para una vela (o tick).

    Todos los valores reflejan los acumuladores temporales (incluyendo la vela en
    curso), no solo los committed. `frozen=True`: valor inmutable de retorno.
    """

    vwap: float
    """VWAP del precio típico ponderado por volumen desde el anchor."""

    sigma: float
    """Desviación estándar ponderada por volumen (sqrt de la varianza)."""

    band_1up: float
    """Banda superior 1σ (vwap + 1*sigma)."""

    band_1dn: float
    """Banda inferior 1σ (vwap - 1*sigma)."""

    band_2up: float
    """Banda superior 2σ (vwap + 2*sigma)."""

    band_2dn: float
    """Banda inferior 2σ (vwap - 2*sigma)."""

    band_3up: float
    """Banda superior 3σ (vwap + 3*sigma)."""

    band_3dn: float
    """Banda inferior 3σ (vwap - 3*sigma)."""

    zscore: float
    """Z-score del precio de cierre respecto al VWAP: (close - vwap) / sigma."""

    is_warmed_up: bool
    """True si `bars_since_anchor >= vwap_warmup_bars` tras el posible commit."""

    is_valid: bool
    """True si el volumen acumulado desde el anchor es > 0."""


# ---------------------------------------------------------------------------
# Función de anclaje (detección de nuevo día)
# ---------------------------------------------------------------------------


def is_new_anchor(bar_time: datetime, config: VwapAnchorConfig) -> bool:
    """Determina si `bar_time` corresponde al inicio de una nueva sesión VWAP.

    Implementa los tres modos de `AnchorMode`. `bar_time` se asume naive UTC
    (convención de datasets MT5 exportados a Python).

    Args:
        bar_time: Timestamp de la vela; naive UTC o timezone-aware.
        config: Configuración de anclaje del VWAP.

    Returns:
        True si `bar_time` es el primer minuto de la sesión según el modo configurado.
    """
    if bar_time.tzinfo is None:
        bar_time = bar_time.replace(tzinfo=UTC)

    mode = config.anchor_mode

    if mode == AnchorMode.NY_MIDNIGHT:
        ny_dt = bar_time.astimezone(_NY_TZ)
        return ny_dt.hour == 0 and ny_dt.minute == 0

    if mode == AnchorMode.SERVER_MIDNIGHT:
        if config.server_to_utc_offset != -999:
            server_dt = bar_time - timedelta(minutes=config.server_to_utc_offset)
            return server_dt.hour == 0 and server_dt.minute == 0
        return bar_time.hour == 0 and bar_time.minute == 0

    if mode == AnchorMode.CUSTOM_HOUR:
        return bar_time.hour == config.custom_anchor_hour and bar_time.minute == 0

    return False  # modo desconocido: nunca anclar


# ---------------------------------------------------------------------------
# Motor VWAP incremental (núcleo del dominio)
# ---------------------------------------------------------------------------


def update_vwap(
    state: VWAPState,
    high: float,
    low: float,
    close: float,
    tick_volume: int,
    bar_closed: bool,
    is_anchor: bool,
    config: VwapAnchorConfig,
) -> VWAPResult:
    """Actualiza el estado VWAP con los datos de la vela (o tick) actual.

    Implementa el algoritmo committed-vs-current portado de la fuente: los
    acumuladores permanentes (`s_v`, `s_pv`, `s_p2v`) solo se actualizan cuando
    `bar_closed=True`; los derivados del tick actual se calculan sobre temporales
    para no violar la invariante anti-lookahead.

    Args:
        state: Estado mutable del motor; se muta in-place si `bar_closed=True`.
        high: Precio máximo de la vela.
        low: Precio mínimo de la vela.
        close: Precio de cierre de la vela.
        tick_volume: Volumen de la vela (ticks). Valores <=0 se tratan como 0.
        bar_closed: True si la vela ha cerrado (commit de acumuladores).
        is_anchor: True si esta vela es el inicio de una nueva sesión VWAP.
            Obtener con `is_new_anchor(bar_time, config)` desde el caller.
        config: Configuración de anclaje/warmup del VWAP.

    Returns:
        `VWAPResult` con los valores calculados sobre los acumuladores temporales.
        `is_valid=False` cuando el volumen acumulado total es 0 (Caso A).
    """
    # Paso 1 — Reset en anchor
    # El reset aplica idéntico en los 3 modos antes de acumular esta vela.
    if is_anchor:
        state.s_v = 0.0
        state.s_pv = 0.0
        state.s_p2v = 0.0
        state.bars_since_anchor = 0
        state.is_warmed_up = False

    # Paso 2 — Precio típico y volumen seguro
    p = (high + low + close) / 3.0
    v = max(tick_volume, 0)  # guard: volumen negativo/inválido se trata como 0

    # Paso 3 — Acumuladores temporales (committed + vela en curso, no persistidos aún)
    current_v = state.s_v + v
    current_pv = state.s_pv + p * v
    current_p2v = state.s_p2v + p * p * v

    # Paso 4 — Caso A: volumen total cero desde anchor (CA8)
    if current_v == 0.0:
        return VWAPResult(
            vwap=0.0,
            sigma=0.0,
            band_1up=0.0,
            band_1dn=0.0,
            band_2up=0.0,
            band_2dn=0.0,
            band_3up=0.0,
            band_3dn=0.0,
            zscore=0.0,
            is_warmed_up=state.is_warmed_up,
            is_valid=False,
        )

    # Paso 5 — Derivados (current_v > 0)
    vwap = current_pv / current_v
    var = (current_p2v / current_v) - vwap * vwap
    var = max(var, 0.0)  # clamp: absorbe negativos por cancelación de redondeo
    sigma = math.sqrt(var)

    # Paso 6 — Caso B: sigma == 0 con current_v > 0 (CA9)
    # Precios idénticos: bandas colapsadas, zscore = 0 (sin división por cero)
    if sigma == 0.0:
        band_1up = band_1dn = vwap
        band_2up = band_2dn = vwap
        band_3up = band_3dn = vwap
        zscore = 0.0
    else:
        # Paso 7 — Caso normal: bandas +/- k*sigma y z-score
        band_1up = vwap + sigma
        band_1dn = vwap - sigma
        band_2up = vwap + 2.0 * sigma
        band_2dn = vwap - 2.0 * sigma
        band_3up = vwap + 3.0 * sigma
        band_3dn = vwap - 3.0 * sigma
        zscore = (close - vwap) / sigma

    # Paso 8 — Commit condicionado (anti-lookahead)
    if bar_closed:
        state.s_v = current_v
        state.s_pv = current_pv
        state.s_p2v = current_p2v
        state.bars_since_anchor += 1
        state.is_warmed_up = state.bars_since_anchor >= config.vwap_warmup_bars

    # Paso 9 — is_warmed_up en el resultado refleja el estado post-commit
    return VWAPResult(
        vwap=vwap,
        sigma=sigma,
        band_1up=band_1up,
        band_1dn=band_1dn,
        band_2up=band_2up,
        band_2dn=band_2dn,
        band_3up=band_3up,
        band_3dn=band_3dn,
        zscore=zscore,
        is_warmed_up=state.is_warmed_up,
        is_valid=True,
    )
