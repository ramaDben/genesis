"""Capa 1 — datos: calendario, sesiones, calidad, store."""

from genesis.data.errors import AccountScopeError
from genesis.data.quality import QualityError
from genesis.data.store import (
    AnnotatedBar,
    ChunkWindow,
    DayBoundaryError,
    Granularity,
    RawParquetStore,
    iter_bars,
    plan_chunks,
)

__all__ = [
    "AccountScopeError",
    "AnnotatedBar",
    "ChunkWindow",
    "DayBoundaryError",
    "Granularity",
    "QualityError",
    "RawParquetStore",
    "iter_bars",
    "plan_chunks",
]
