"""Cotización de Databento para la casilla B.1 del roadmap del arquitecto.

Evidencia **no-pytest** (no bloquea `mise run ci`), en la línea de los `bench_*.py`.
Cierra el punto 2 del DoD de B.1 (`docs/ROADMAP_ARQUITECTO.md`): la cotización real
del rango objetivo, con el costo en GB y en dólares, obtenida de la API y no de una
captura de pantalla de la consola web.

**Por qué un script y no la consola web.** Un clic no deja registro de qué símbolo,
esquema, rango ni simbología se pidieron; los parámetros de este archivo sí. Esa
traza es lo que sostiene la identidad del dataset — y hace falta más de lo que se
creía: la licencia de Databento **no garantiza** poder re-pedir el mismo rango dentro
de dos años (§7.1c del roadmap, §9.3 del contrato), así que la evidencia es la copia
local más estos parámetros, no la promesa del proveedor.

**No descarga ni un byte y no consume crédito.** Sólo llama a los endpoints de
metadata (`metadata.get_cost`, `metadata.get_billable_size`,
`metadata.get_dataset_range`), que son gratuitos. La descarga real es otra casilla
y otra decisión humana.

**Las dos variantes de simbología no son intercambiables.** El continuo (`MNQ.v.0`,
`stype_in=continuous`) es la serie que Databento arma eligiendo el contrato de cada
fecha; los contratos sueltos (`MNQ.FUT`, `stype_in=parent`) son todos los
trimestrales por separado. B.3 hace el empalme de nuestro lado, y el ajuste de roll
necesita los contratos solapados alrededor de cada vencimiento — por eso se cotizan
los dos: uno es el piso y el otro el techo del presupuesto.

La clave de API se lee de `DATABENTO_API_KEY`, o del archivo que indique
`--env-file` (por defecto `~/.databento.env`, fuera del repo). Nunca se imprime.

Uso:
    uv run python scripts/quote_databento.py
    uv run python scripts/quote_databento.py --json
    uv run python scripts/quote_databento.py --schemas ohlcv-1m ohlcv-1h
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from databento import Historical

DATASET = "GLBX.MDP3"
"""CME Globex MDP 3.0 — el único venue admitido tras la decisión D-C."""

DEFAULT_START = "2019-05-05"
"""Primera sesión utilizable del MNQ, verificada en fuente primaria (C.1b)."""

DEFAULT_ENV_FILE = "~/.databento.env"

BYTES_PER_GB = 1024**3

# (etiqueta, sufijo de símbolo, stype_in) — el piso y el techo del presupuesto.
VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("continuo por volumen", "{root}.v.0", "continuous"),
    ("todos los contratos", "{root}.FUT", "parent"),
)


@dataclass(frozen=True)
class Quote:
    """Una cotización: qué se pidió y cuánto sale."""

    variante: str
    symbols: str
    stype_in: str
    schema: str
    start: str
    end: str
    bytes_facturables: int | None
    gb_facturables: float | None
    usd: float | None
    error: str | None


def _load_api_key(env_file: str) -> str:
    """Devuelve la clave de API, del entorno o del archivo de secretos.

    Falla con contexto si no la encuentra: una clave ausente es un error de
    configuración del operador, no una condición a la que el script deba adaptarse.
    """
    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    if key:
        return key

    path = Path(env_file).expanduser()
    if not path.is_file():
        raise SystemExit(
            f"No hay DATABENTO_API_KEY en el entorno ni archivo en {path}.\n"
            f"Creá el archivo con:\n"
            f"    umask 077; echo 'DATABENTO_API_KEY=db-...' > {env_file}"
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "DATABENTO_API_KEY":
            key = value.strip().strip("\"'")
            if key:
                return key

    raise SystemExit(f"El archivo {path} existe pero no define DATABENTO_API_KEY.")


def _default_end(rango: dict[str, Any]) -> str:
    """Fin del rango por defecto: el borde que el dataset declara, no «hoy».

    Pedir hasta hoy falla con `422 dataset_unavailable_range` en cuanto el reloj UTC
    cruza la medianoche, porque el archivo histórico va unas horas por detrás del
    presente. Medido el 2026-09-22: `end=2026-09-22` rechazado, con el borde real en
    `2026-09-21T16:12Z`. El borde se recorta al día, que es la granularidad del rango.
    """
    borde = rango.get("end")
    if not isinstance(borde, str):
        return datetime.now(UTC).date().isoformat()
    return borde[:10]


def _quote_one(
    client: Historical,
    *,
    variante: str,
    symbols: str,
    stype_in: str,
    schema: str,
    start: str,
    end: str,
) -> Quote:
    """Cotiza una combinación, capturando el error en vez de abortar la corrida.

    Una variante puede fallar por simbología no entitulada sin que eso invalide a
    las otras; el operador necesita ver la tabla completa para decidir.
    """
    try:
        # Explícito y no `**params`: el desempaquetado oculta el tipo de cada argumento
        # y `ty` no puede verificar la firma (`limit: int | None`) contra un `dict[str, str]`.
        size = client.metadata.get_billable_size(
            dataset=DATASET,
            symbols=symbols,
            stype_in=stype_in,
            schema=schema,
            start=start,
            end=end,
        )
        usd = client.metadata.get_cost(
            dataset=DATASET,
            symbols=symbols,
            stype_in=stype_in,
            schema=schema,
            start=start,
            end=end,
        )
    except Exception as exc:
        return Quote(
            variante=variante,
            symbols=symbols,
            stype_in=stype_in,
            schema=schema,
            start=start,
            end=end,
            bytes_facturables=None,
            gb_facturables=None,
            usd=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    return Quote(
        variante=variante,
        symbols=symbols,
        stype_in=stype_in,
        schema=schema,
        start=start,
        end=end,
        bytes_facturables=int(size),
        gb_facturables=round(int(size) / BYTES_PER_GB, 4),
        usd=round(float(usd), 4),
        error=None,
    )


def _print_table(quotes: list[Quote], credito: float) -> None:
    """Imprime la tabla de cotizaciones y el veredicto contra el crédito."""
    ancho = max(len(q.variante) for q in quotes)
    print(
        f"\n{'variante'.ljust(ancho)}  {'esquema':<10}  {'GB':>10}  {'USD':>10}  entra en crédito"
    )
    print("-" * (ancho + 52))
    for q in quotes:
        if q.error is not None or q.gb_facturables is None or q.usd is None:
            print(f"{q.variante.ljust(ancho)}  {q.schema:<10}  {'ERROR':>10}  {'—':>10}  {q.error}")
            continue
        entra = "sí" if q.usd <= credito else f"NO (faltan ${q.usd - credito:,.2f})"
        print(
            f"{q.variante.ljust(ancho)}  {q.schema:<10}  "
            f"{q.gb_facturables:>10.4f}  {q.usd:>10.2f}  {entra}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START, help="inicio del rango (inclusive)")
    parser.add_argument(
        "--end",
        default=None,
        help="fin del rango (exclusivo); por defecto, el borde que declara el dataset",
    )
    parser.add_argument(
        "--schemas",
        nargs="+",
        default=["ohlcv-1m"],
        help="esquemas a cotizar (ohlcv-1m es el que pide B.1)",
    )
    parser.add_argument(
        "--roots",
        nargs="+",
        default=["MNQ"],
        help="raíces de contrato a cotizar (MNQ es el elegido; NQ sirve de contraste)",
    )
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, help="archivo con la clave")
    parser.add_argument(
        "--credito",
        type=float,
        default=125.0,
        help="crédito disponible en USD, para el veredicto de la tabla",
    )
    parser.add_argument("--json", action="store_true", help="salida legible por máquina")
    args = parser.parse_args()

    client = Historical(_load_api_key(args.env_file))

    rango = client.metadata.get_dataset_range(dataset=DATASET)
    end = args.end or _default_end(rango)

    quotes = [
        _quote_one(
            client,
            variante=f"{root} — {variante}",
            symbols=plantilla.format(root=root),
            stype_in=stype_in,
            schema=schema,
            start=args.start,
            end=end,
        )
        for root in args.roots
        for schema in args.schemas
        for variante, plantilla, stype_in in VARIANTS
    ]

    if args.json:
        json.dump(
            {
                "dataset": DATASET,
                "rango_disponible": rango,
                "start": args.start,
                "end": end,
                "credito_usd": args.credito,
                "cotizaciones": [asdict(q) for q in quotes],
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        print()
        return 0

    print(f"dataset            : {DATASET}")
    print(f"rango disponible   : {rango}")
    print(f"rango cotizado     : {args.start} → {end}")
    print(f"crédito disponible : ${args.credito:,.2f}")
    _print_table(quotes, args.credito)
    print("\nNo se descargó ningún byte: sólo endpoints de metadata, que son gratuitos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
