"""Contrato de calidad fail-fast y ruidoso sobre el Parquet crudo de `mt5_export.py`.

`check_quality` es pura sobre un frame ya cargado (sin SDK, sin I/O): detecta gaps
anómalos, duplicados y velas corruptas; calcula las ventanas reales de cobertura de
M1/ticks (proxy de PA-2); y emite un `sufficiency_verdict` que es un **proxy de historia
disponible**, nunca el gate G1 real (≥300 trades OOS, spec §7.1) — ese veredicto se
calcula en Issues H/I sobre el backtest real. Nunca interpola, rellena ni silencia una
anomalía detectada (spec §8).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd

from genesis.data.errors import GenesisDataError
from genesis.data.symbols import SymbolSpec

_M1_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
_TICKS_REQUIRED_COLUMNS = ("timestamp",)
_EXPECTED_M1_STEP_MINUTES = 1


class QualityError(GenesisDataError):
    """Frame crudo inválido/vacío que impide producir un `QualityReport` (R21)."""


@dataclass(frozen=True, slots=True)
class Gap:
    """Hueco anómalo entre dos barras M1 consecutivas."""

    start: datetime
    end: datetime
    missing_bars: int


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Reporte de calidad de un dataset crudo (M1 o ticks) de un símbolo.

    `sufficiency_verdict` es un **proxy de historia disponible** (número de sesiones de
    contado completas cubiertas frente a `SymbolSpec.min_full_sessions`), **no** el gate
    G1 real (≥300 trades OOS, spec §7.1) — ese veredicto definitivo se calcula en Issues
    H/I sobre el backtest real. `row_count` es el número de filas del frame de entrada,
    usado para verificar que `check_quality` nunca interpola ni rellena barras (R25).
    """

    symbol: str
    gaps: list[Gap]
    duplicates_count: int
    corrupt_bars_count: int
    m1_coverage_window: tuple[date, date]
    ticks_coverage_window: tuple[date, date] | None
    sufficiency_verdict: bool
    sufficiency_reason: str
    row_count: int


def _require_columns(frame: pd.DataFrame, required: tuple[str, ...], kind: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        message = f"Frame crudo '{kind}' con esquema inválido: faltan columnas {missing}."
        raise QualityError(message)


def _count_duplicates(frame: pd.DataFrame) -> int:
    return int(frame["timestamp"].duplicated().sum())


def _count_corrupt_bars(frame: pd.DataFrame) -> int:
    low_gt_high = frame["low"] > frame["high"]
    close_out_of_range = (frame["close"] < frame["low"]) | (frame["close"] > frame["high"])
    return int((low_gt_high | close_out_of_range).sum())


def _detect_gaps(sorted_timestamps: pd.Series) -> list[Gap]:
    """Detecta huecos entre barras M1 consecutivas (posicionales, frame ya ordenado)."""
    gaps: list[Gap] = []
    expected = pd.Timedelta(minutes=_EXPECTED_M1_STEP_MINUTES)
    values = sorted_timestamps.reset_index(drop=True)
    for position in range(1, len(values)):
        start_ts, end_ts = values.iloc[position - 1], values.iloc[position]
        delta = end_ts - start_ts
        if delta > expected:
            missing_bars = int(delta / expected) - 1
            gaps.append(
                Gap(
                    start=start_ts.to_pydatetime(),
                    end=end_ts.to_pydatetime(),
                    missing_bars=missing_bars,
                )
            )
    return gaps


def _coverage_window(sorted_timestamps: pd.Series) -> tuple[date, date]:
    return (
        sorted_timestamps.iloc[0].to_pydatetime().date(),
        sorted_timestamps.iloc[-1].to_pydatetime().date(),
    )


def _sufficiency(sorted_timestamps: pd.Series, min_full_sessions: int) -> tuple[bool, str]:
    trading_days = {ts.date() for ts in sorted_timestamps}
    available = len(trading_days)
    if available >= min_full_sessions:
        reason = (
            f"Cobertura suficiente (proxy de historia, NO es el gate G1): {available} sesiones "
            f"disponibles >= mínimo requerido {min_full_sessions}."
        )
        return True, reason
    reason = (
        f"Historia insuficiente (proxy de historia, NO es el gate G1): {available} sesiones "
        f"disponibles < mínimo requerido {min_full_sessions}. El símbolo debe excluirse, nunca "
        "rellenarse o interpolarse."
    )
    return False, reason


def check_quality(
    raw_frame: pd.DataFrame,
    symbol_spec: SymbolSpec,
    *,
    kind: Literal["m1", "ticks"] = "m1",
) -> QualityReport:
    """Evalúa la calidad de `raw_frame` (M1 o ticks) para `symbol_spec`.

    Detecta gaps anómalos (huecos de M1 mayores al esperado), duplicados (timestamp
    repetido) y velas corruptas (`low > high` o `close` fuera de `[low, high]`); ninguna
    anomalía queda fuera del reporte de forma silenciosa (R26). Calcula la ventana real de
    cobertura de M1 y, si `kind="ticks"`, la ventana real de disponibilidad de ticks (proxy
    de PA-2, spec §4.1/§11.1).

    `sufficiency_verdict` es un **proxy de historia disponible** (NO el gate G1 real de
    ≥300 trades OOS, que se calcula en Issues H/I sobre el backtest real): compara el
    número de sesiones de contado completas cubiertas contra `symbol_spec.min_full_sessions`.
    Nunca interpola, rellena ni sintetiza barras faltantes para alcanzar la suficiencia
    (R25): `row_count` siempre coincide con `len(raw_frame)`.

    Lanza `QualityError` si `raw_frame` está vacío o le faltan columnas requeridas
    (`timestamp`/`open`/`high`/`low`/`close` para `kind="m1"`; `timestamp` para
    `kind="ticks"`), antes de emitir cualquier reporte.
    """
    if raw_frame.empty:
        message = f"Frame crudo vacío para el símbolo '{symbol_spec.symbol}' (kind='{kind}')."
        raise QualityError(message)

    required = _M1_REQUIRED_COLUMNS if kind == "m1" else _TICKS_REQUIRED_COLUMNS
    _require_columns(raw_frame, required, kind)

    row_count = len(raw_frame)
    sorted_frame = raw_frame.sort_values("timestamp").reset_index(drop=True)
    sorted_timestamps = sorted_frame["timestamp"]

    duplicates_count = _count_duplicates(raw_frame)

    if kind == "m1":
        deduped = sorted_frame.drop_duplicates(subset="timestamp").reset_index(drop=True)
        corrupt_bars_count = _count_corrupt_bars(deduped)
        gaps = _detect_gaps(deduped["timestamp"])
        m1_coverage_window = _coverage_window(sorted_timestamps)
        ticks_coverage_window = None
    else:
        corrupt_bars_count = 0
        gaps = []
        m1_coverage_window = _coverage_window(sorted_timestamps)
        ticks_coverage_window = _coverage_window(sorted_timestamps)

    sufficiency_verdict, sufficiency_reason = _sufficiency(
        sorted_timestamps, symbol_spec.min_full_sessions
    )

    return QualityReport(
        symbol=symbol_spec.symbol,
        gaps=gaps,
        duplicates_count=duplicates_count,
        corrupt_bars_count=corrupt_bars_count,
        m1_coverage_window=m1_coverage_window,
        ticks_coverage_window=ticks_coverage_window,
        sufficiency_verdict=sufficiency_verdict,
        sufficiency_reason=sufficiency_reason,
        row_count=row_count,
    )
