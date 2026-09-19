"""Ledger de ensayos append-only, persistente entre corridas (Issue #53).

Capa 4 (`genesis.validation`), módulo nuevo y autocontenido con tres
responsabilidades separadas (design.md §1): identidad de un ensayo
(`TrialRecord`, `TrialOutcomeKind`, `compute_trial_id`), lectura/agregación pura
(`read_trial_summary` → `TrialLedgerSummary`) y escritura idempotente
(`append_trial`, única I/O de escritura del módulo). `TrialLedger` es la fachada
delgada de inyección (ruta + claves institucionales de la corrida).

Dependencias permitidas: **solo stdlib** + `genesis.validation.errors` (A8). Sin
`numpy`/`pandas`/`scipy`/`statsmodels`/`sqlite3`. No importa de capas 1-3 ni de
`verdict.py`/`dsr_pbo.py`: la dependencia va en el sentido único
`verdict.py -> trial_ledger.py`, sin ciclo (design.md §4/§7).
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from genesis.validation.errors import TrialLedgerConfigError

CONFIG_VERSION: str = "genesis-validation-trial-ledger/1"
"""Versión del esquema de configuración de este módulo (propia, Alcance OUT del spec)."""

LEDGER_RELATIVE_PATH: str = "ledger/trials.jsonl"
"""Única declaración de la ruta relativa del ledger versionado en git (D4)."""

_REQUIRED_FIELDS = (
    "trial_id",
    "candidate_id",
    "symbol",
    "outcome",
    "discard_reason",
    "config_version",
    "dataset_hash_by_symbol",
    "firm_profile_hash",
    "exit_geometry_hash",
    "house_rule_hash",
    "git_commit",
    "recorded_at_utc",
)


class TrialOutcomeKind(StrEnum):
    """Desenlace de un ensayo registrado en el ledger (R1), exactamente 2 miembros."""

    WFA_COMPLETADO = "wfa-completado"
    DESCARTADO = "descartado"


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """Un ensayo persistido en `ledger/trials.jsonl` (R2), fila JSON Lines.

    `discard_reason` es obligatorio si y solo si `outcome == DESCARTADO` (R3,
    validado en `__post_init__`). `recorded_at_utc` es el único campo no
    determinista del registro: inyectable por el llamador, **no** participa de
    `compute_trial_id` (si participara, la idempotencia de R8 sería imposible).
    """

    trial_id: str
    candidate_id: str
    symbol: str
    outcome: TrialOutcomeKind
    discard_reason: str | None
    config_version: str
    dataset_hash_by_symbol: Mapping[str, str]
    firm_profile_hash: str
    exit_geometry_hash: str
    house_rule_hash: str
    git_commit: str
    recorded_at_utc: str

    def __post_init__(self) -> None:
        """Coherencia `outcome` <-> `discard_reason` (R3): fail-fast, nunca omisión silenciosa."""
        if self.outcome == TrialOutcomeKind.DESCARTADO and self.discard_reason is None:
            message = (
                f"TrialRecord(trial_id={self.trial_id!r}, candidate_id={self.candidate_id!r}, "
                f"symbol={self.symbol!r}): outcome=DESCARTADO exige discard_reason no nulo (R3)."
            )
            raise TrialLedgerConfigError(message)
        if self.outcome == TrialOutcomeKind.WFA_COMPLETADO and self.discard_reason is not None:
            message = (
                f"TrialRecord(trial_id={self.trial_id!r}, candidate_id={self.candidate_id!r}, "
                f"symbol={self.symbol!r}): outcome=WFA_COMPLETADO exige discard_reason=None "
                f"(recibido {self.discard_reason!r}, R3)."
            )
            raise TrialLedgerConfigError(message)


@dataclass(frozen=True, slots=True)
class TrialLedgerSummary:
    """Resumen agregado, puro, de `ledger/trials.jsonl` en un instante dado (R9/Q3/Q7).

    `trial_ids` es el conjunto de `trial_id` únicos: necesario para la
    auto-exclusión de Q4 (`extra = |snapshot.trial_ids \\ own_ids|`) en
    `run_verdict`. `n_rows` cuenta filas leídas; `n_trials_total` cuenta
    `trial_id` únicos; la diferencia expone duplicados sin fallar (Q7).
    """

    n_trials_total: int
    n_rows: int
    n_duplicate_trial_ids: int
    trial_ids: frozenset[str]
    n_trials_by_symbol: Mapping[str, int]
    n_trials_by_candidate_family: Mapping[str, int]
    n_trials_by_firm_profile_hash: Mapping[str, int]
    content_hash: str


def compute_trial_id(
    candidate_config: Mapping[str, object],
    dataset_hash_by_symbol: Mapping[str, str],
    firm_profile_hash: str,
    exit_geometry_hash: str,
    house_rule_hash: str,
) -> str:
    """`sha256` hexdigest de la serialización canónica completa de los 5 insumos (R4-R6).

    `candidate_config` participa **completo, sin lista blanca** (D2/R5): dos
    configuraciones distintas en cualquier campo producen `trial_id` distintos
    (defensa real contra el sub-conteo por colisión). Un `TypeError` de
    `json.dumps` (valor no serializable) se envuelve en `TrialLedgerConfigError`
    citando el campo ofensor (R6) — nunca `default=str`, que colisionaría dos
    objetos distintos con el mismo `repr`. Change #109 (D9): `risk_profile_hash`
    se sustituye por `exit_geometry_hash` + `house_rule_hash`.
    """
    payload = {
        "candidate_config": candidate_config,
        "dataset_hash_by_symbol": dataset_hash_by_symbol,
        "firm_profile_hash": firm_profile_hash,
        "exit_geometry_hash": exit_geometry_hash,
        "house_rule_hash": house_rule_hash,
    }
    try:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except TypeError as exc:
        message = (
            f"compute_trial_id: candidate_config={candidate_config!r} contiene un valor no "
            f"serializable a JSON ({exc}); R6 exige fallar en vez de omitir el campo en silencio."
        )
        raise TrialLedgerConfigError(message) from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_family(candidate_id: str) -> str:
    """Familia de un candidato: primer carácter de `candidate_id` (design.md §4)."""
    return candidate_id[:1]


def _parse_trial_record_line(line: str, *, ledger_path: Path, line_number: int) -> TrialRecord:
    """Reconstruye un `TrialRecord` de una línea; fail-fast con línea + ruta (Q7)."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        message = (
            f"read_trial_summary({ledger_path}): línea {line_number} no es JSON válido ({exc}); "
            "una línea ilegible es un ensayo perdido (Q7, fail-fast, nunca se saltea en silencio)."
        )
        raise TrialLedgerConfigError(message) from exc
    if not isinstance(raw, dict):
        message = (
            f"read_trial_summary({ledger_path}): línea {line_number} no es un objeto JSON "
            f"(tipo {type(raw).__name__}, Q7)."
        )
        raise TrialLedgerConfigError(message)
    missing = [field for field in _REQUIRED_FIELDS if field not in raw]
    if missing:
        message = (
            f"read_trial_summary({ledger_path}): línea {line_number} carece de las claves "
            f"obligatorias {missing} (Q7, fail-fast)."
        )
        raise TrialLedgerConfigError(message)
    try:
        outcome = TrialOutcomeKind(raw["outcome"])
    except ValueError as exc:
        message = (
            f"read_trial_summary({ledger_path}): línea {line_number} tiene outcome="
            f"{raw['outcome']!r} fuera de TrialOutcomeKind (Q7)."
        )
        raise TrialLedgerConfigError(message) from exc
    return TrialRecord(
        trial_id=raw["trial_id"],
        candidate_id=raw["candidate_id"],
        symbol=raw["symbol"],
        outcome=outcome,
        discard_reason=raw["discard_reason"],
        config_version=raw["config_version"],
        dataset_hash_by_symbol=raw["dataset_hash_by_symbol"],
        firm_profile_hash=raw["firm_profile_hash"],
        exit_geometry_hash=raw["exit_geometry_hash"],
        house_rule_hash=raw["house_rule_hash"],
        git_commit=raw["git_commit"],
        recorded_at_utc=raw["recorded_at_utc"],
    )


def read_trial_summary(ledger_path: Path) -> TrialLedgerSummary:
    """Lee `ledger_path` en una sola pasada binaria y devuelve el resumen agregado (R9/R10).

    Pura: no muta el archivo, no lo crea, no toca `mtime` (PR-4). Archivo
    inexistente -> `TrialLedgerSummary` con todo en cero y
    `content_hash = sha256(b"").hexdigest()`, sin excepción (R10). Lectura
    **binaria** (`read_bytes`), troceada por `b"\\n"`, decodificando UTF-8 por
    línea explícitamente (PR-4): el `content_hash` describe los bytes en disco
    tal cual, nunca una versión traducida por finales de línea de modo texto.
    """
    if not ledger_path.exists():
        empty_hash = hashlib.sha256(b"").hexdigest()
        return TrialLedgerSummary(
            n_trials_total=0,
            n_rows=0,
            n_duplicate_trial_ids=0,
            trial_ids=frozenset(),
            n_trials_by_symbol={},
            n_trials_by_candidate_family={},
            n_trials_by_firm_profile_hash={},
            content_hash=empty_hash,
        )

    raw_bytes = ledger_path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    n_rows = 0
    trial_ids: set[str] = set()
    n_duplicate_trial_ids = 0
    n_trials_by_symbol: dict[str, int] = {}
    n_trials_by_candidate_family: dict[str, int] = {}
    n_trials_by_firm_profile_hash: dict[str, int] = {}

    for line_number, raw_line in enumerate(raw_bytes.split(b"\n"), start=1):
        if raw_line == b"":
            continue
        line = raw_line.decode("utf-8")
        record = _parse_trial_record_line(line, ledger_path=ledger_path, line_number=line_number)
        n_rows += 1
        if record.trial_id in trial_ids:
            n_duplicate_trial_ids += 1
            continue
        trial_ids.add(record.trial_id)
        n_trials_by_symbol[record.symbol] = n_trials_by_symbol.get(record.symbol, 0) + 1
        family = _candidate_family(record.candidate_id)
        n_trials_by_candidate_family[family] = n_trials_by_candidate_family.get(family, 0) + 1
        n_trials_by_firm_profile_hash[record.firm_profile_hash] = (
            n_trials_by_firm_profile_hash.get(record.firm_profile_hash, 0) + 1
        )

    return TrialLedgerSummary(
        n_trials_total=len(trial_ids),
        n_rows=n_rows,
        n_duplicate_trial_ids=n_duplicate_trial_ids,
        trial_ids=frozenset(trial_ids),
        n_trials_by_symbol=n_trials_by_symbol,
        n_trials_by_candidate_family=n_trials_by_candidate_family,
        n_trials_by_firm_profile_hash=n_trials_by_firm_profile_hash,
        content_hash=content_hash,
    )


def append_trial(ledger_path: Path, record: TrialRecord) -> None:
    """Anexa `record` a `ledger_path` si su `trial_id` no está ya presente (R7/R8/R19).

    Única I/O de escritura del módulo. Crea los directorios padre si faltan.
    Idempotente por **identidad** (`trial_id`), no por contenido íntegro de la
    fila (R8): una segunda invocación con el mismo `trial_id` no agrega fila,
    aunque el resto de los campos difiera. `newline="\\n"` explícito es
    obligatorio (PR-4): sin él, un proceso Python en Windows escribiría CRLF y
    rompería el `content_hash` que el manifest promete reproducir byte a byte.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = read_trial_summary(ledger_path).trial_ids
    if record.trial_id in existing_ids:
        return

    row = {
        "trial_id": record.trial_id,
        "candidate_id": record.candidate_id,
        "symbol": record.symbol,
        "outcome": record.outcome.value,
        "discard_reason": record.discard_reason,
        "config_version": record.config_version,
        "dataset_hash_by_symbol": dict(record.dataset_hash_by_symbol),
        "firm_profile_hash": record.firm_profile_hash,
        "exit_geometry_hash": record.exit_geometry_hash,
        "house_rule_hash": record.house_rule_hash,
        "git_commit": record.git_commit,
        "recorded_at_utc": record.recorded_at_utc,
    }
    line = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.write("\n")


@dataclass(frozen=True, slots=True)
class TrialIdentityContext:
    """Claves institucionales de la corrida que registra/deriva un `TrialLedger` (Q5).

    `git_commit` solo se consume al registrar (`TrialLedger.build_record`), no al
    leer: `read_summary`/`trial_id_for_config` no lo necesitan.
    """

    dataset_hash_by_symbol: Mapping[str, str]
    firm_profile_hash: str
    exit_geometry_hash: str
    house_rule_hash: str
    git_commit: str


class TrialLedger:
    """Fachada delgada de inyección: ruta del ledger + identidad institucional de la corrida (R11).

    `trial_id_for_config` es la **única** derivación sancionada del `trial_id`
    (PR-2): ningún consumidor construye ni pasa un `trial_id` a mano.
    """

    def __init__(self, ledger_path: Path, identity: TrialIdentityContext) -> None:
        self._ledger_path = ledger_path
        self._identity = identity

    @property
    def ledger_path(self) -> Path:
        """Ruta del archivo `ledger/trials.jsonl` que envuelve esta fachada."""
        return self._ledger_path

    @property
    def identity(self) -> TrialIdentityContext:
        """Claves institucionales de la corrida inyectadas en el constructor."""
        return self._identity

    def read_summary(self) -> TrialLedgerSummary:
        """Delega en `read_trial_summary(self.ledger_path)` (R11)."""
        return read_trial_summary(self._ledger_path)

    def record(self, record: TrialRecord) -> None:
        """Delega en `append_trial(self.ledger_path, record)` (R11)."""
        append_trial(self._ledger_path, record)

    def trial_id_for_config(self, candidate_config: Mapping[str, object]) -> str:
        """`compute_trial_id(candidate_config, *self.identity[:4])` (PR-2/Q5)."""
        return compute_trial_id(
            candidate_config,
            self._identity.dataset_hash_by_symbol,
            self._identity.firm_profile_hash,
            self._identity.exit_geometry_hash,
            self._identity.house_rule_hash,
        )

    def build_record(
        self,
        candidate_id: str,
        symbol: str,
        candidate_config: Mapping[str, object],
        outcome: TrialOutcomeKind,
        discard_reason: str | None = None,
        recorded_at_utc: str | None = None,
    ) -> TrialRecord:
        """Construye un `TrialRecord` completo derivando su `trial_id` (PR-2).

        `recorded_at_utc` es inyectable (default `datetime.now(UTC)` en formato
        ISO 8601) para que los tests golden puedan fijarlo; **no** participa de
        `compute_trial_id` (si participara, la idempotencia de R8 sería
        imposible).
        """
        resolved_recorded_at_utc = (
            recorded_at_utc if recorded_at_utc is not None else datetime.now(UTC).isoformat()
        )
        trial_id = self.trial_id_for_config(candidate_config)
        return TrialRecord(
            trial_id=trial_id,
            candidate_id=candidate_id,
            symbol=symbol,
            outcome=outcome,
            discard_reason=discard_reason,
            config_version=CONFIG_VERSION,
            dataset_hash_by_symbol=self._identity.dataset_hash_by_symbol,
            firm_profile_hash=self._identity.firm_profile_hash,
            exit_geometry_hash=self._identity.exit_geometry_hash,
            house_rule_hash=self._identity.house_rule_hash,
            git_commit=self._identity.git_commit,
            recorded_at_utc=resolved_recorded_at_utc,
        )
