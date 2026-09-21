#!/usr/bin/env python3
"""Cotiza el costo de los datos de CME en Databento **sin descargar ni gastar crédito**.

Cierra los puntos 2 y 3 del DoD de la casilla B.1 del `docs/ROADMAP_ARQUITECTO.md`:
la cotización real del rango objetivo y el catálogo de contratos con sus fechas.

Por qué existe
--------------
El precio de lista de Databento es por GB de datos binarios sin comprimir, y la
compañía **no publica** una cifra por dataset para el histórico de CME. El número
exacto sólo se conoce cotizando el rango concreto. Este script hace exactamente eso
y nada más: llama a `metadata.get_billable_size` y `metadata.get_cost`, que son
consultas de metadata y **no consumen crédito**.

No descarga ni una barra. Mirar el primer dato real es la casilla B.3, y por la
política del holdout (`docs/POLITICA_HOLDOUT.md`) eso no puede pasar antes de que
C.1a y C.1b estén ratificadas.

Uso
---
    export DATABENTO_API_KEY='db-...'
    uv run --no-project --with databento python scripts/quote_databento.py

La clave se lee del entorno a propósito: no se pasa por argumento para que no quede
en el historial del shell, y no se escribe en ningún archivo del repo.

Opciones útiles:
    --start 2019-05-01     primer día a cotizar (por defecto, el inicio del dataset)
    --end   2026-09-20     último día (por defecto, hoy)
    --json  ruta.json      además de la tabla, vuelca el resultado crudo
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, field

DATASET = "GLBX.MDP3"
"""CME Globex MDP 3.0 — el único venue relevante bajo la decisión D-C."""

CREDITO_INICIAL_USD = 125.0
"""Crédito de alta para cuentas nuevas. Expira 6 meses después del alta."""

# Combinaciones a cotizar. El orden importa: la primera es la compra propuesta.
#
# `MNQ.v.0` es el continuo de MNQ con regla de roll por volumen. Databento resuelve
# QUÉ contrato corresponde en cada momento, pero **entrega precios crudos, sin
# ajuste de roll** — el ajuste es trabajo nuestro (casilla B.3). Es justo el defecto
# que el estudio arXiv:2605.04004 cometió al concatenar sin ajustar.
COMBINACIONES: tuple[tuple[str, str, str, str], ...] = (
    ("MNQ.v.0", "ohlcv-1m", "continuous", "COMPRA PROPUESTA: barras 1m, agregables a 5m/15m"),
    ("MNQ.v.0", "ohlcv-1h", "continuous", "referencia: mismo rango en barras horarias"),
    ("MNQ.v.0", "ohlcv-1d", "continuous", "referencia: mismo rango en barras diarias"),
    ("NQ.v.0", "ohlcv-1m", "continuous", "alternativa de C.1b: historia larga del mini"),
    ("MNQ.FUT", "definition", "parent", "catálogo de contratos y sus fechas (insumo de B.2/C.1b)"),
)

MODOS = ("historical", "historical-streaming")
"""Verificados contra `FeedMode` del cliente 0.86.0: los valores válidos son
`historical` (descarga por lotes), `historical-streaming` y `live`. Tienen precios
unitarios distintos, así que se cotizan los dos que aplican. `live` no se cotiza:
esto es una compra de histórico."""


@dataclass
class Cotizacion:
    """Resultado de cotizar una combinación. Cualquier campo puede faltar si la API falló."""

    simbolo: str
    esquema: str
    stype_in: str
    nota: str
    gb: float | None = None
    costos: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def _parse_args() -> argparse.Namespace:
    hoy = dt.date.today()
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--start", default=None, help="Primer día (YYYY-MM-DD). Por defecto, el inicio del dataset."
    )
    p.add_argument(
        "--end", default=hoy.isoformat(), help="Último día (YYYY-MM-DD). Por defecto, hoy."
    )
    p.add_argument(
        "--json", dest="json_out", default=None, help="Ruta donde volcar el resultado crudo."
    )
    return p.parse_args()


def _rango_del_dataset(cliente) -> tuple[str | None, str | None, object]:
    """Devuelve (inicio, fin, crudo) de la cobertura disponible, o (None, None, error)."""
    try:
        rango = cliente.metadata.get_dataset_range(dataset=DATASET)
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"

    # La forma exacta del retorno cambió entre versiones del cliente; se tolera cualquiera.
    if isinstance(rango, dict):
        inicio = rango.get("start") or rango.get("start_date")
        fin = rango.get("end") or rango.get("end_date")
    else:
        inicio = getattr(rango, "start", None)
        fin = getattr(rango, "end", None)
    return (str(inicio) if inicio else None), (str(fin) if fin else None), rango


def _cotizar(
    cliente, simbolo: str, esquema: str, stype_in: str, nota: str, start: str, end: str
) -> Cotizacion:
    c = Cotizacion(simbolo=simbolo, esquema=esquema, stype_in=stype_in, nota=nota)
    comun = {
        "dataset": DATASET,
        "symbols": simbolo,
        "schema": esquema,
        "start": start,
        "end": end,
        "stype_in": stype_in,
    }

    try:
        bytes_facturables = cliente.metadata.get_billable_size(**comun)
        c.gb = float(bytes_facturables) / 1024**3
    except Exception as exc:
        c.error = f"get_billable_size — {type(exc).__name__}: {exc}"

    for modo in MODOS:
        try:
            c.costos[modo] = float(cliente.metadata.get_cost(**comun, mode=modo))
        except Exception as exc:
            # Un modo puede no aplicar a un esquema; no es motivo para abortar la corrida.
            if c.error is None:
                c.error = f"get_cost[{modo}] — {type(exc).__name__}: {exc}"

    return c


def _imprimir(cotizaciones: list[Cotizacion], start: str, end: str) -> None:
    print()
    print("=" * 78)
    print(f"COTIZACIÓN DATABENTO — {DATASET} — {start} .. {end}")
    print("=" * 78)
    print("Consultas de metadata: NO descargan datos y NO consumen crédito.")
    print()

    ancho = max(len(c.simbolo) for c in cotizaciones)
    print(
        f"{'símbolo'.ljust(ancho)}  {'esquema':<11} {'GB':>9}  {'por lotes':>11}  {'streaming':>11}"
    )
    print("-" * 78)
    for c in cotizaciones:
        gb = f"{c.gb:,.3f}" if c.gb is not None else "—"
        lotes = c.costos.get("historical")
        stream = c.costos.get("historical-streaming")
        l_txt = f"${lotes:,.2f}" if lotes is not None else "—"
        s_txt = f"${stream:,.2f}" if stream is not None else "—"
        print(f"{c.simbolo.ljust(ancho)}  {c.esquema:<11} {gb:>9}  {l_txt:>11}  {s_txt:>11}")
        print(f"{' '.ljust(ancho)}  └─ {c.nota}")
        if c.error:
            print(f"{' '.ljust(ancho)}  ⚠  {c.error}")
    print("-" * 78)

    propuesta = cotizaciones[0]
    mejor = min((v for v in propuesta.costos.values()), default=None)
    print()
    if mejor is None:
        print("No se pudo cotizar la compra propuesta. Revisar los errores de arriba.")
        return

    print(f"COMPRA PROPUESTA ({propuesta.simbolo} {propuesta.esquema}): ${mejor:,.2f}")
    print(f"Crédito de alta:                              ${CREDITO_INICIAL_USD:,.2f}")
    if mejor <= CREDITO_INICIAL_USD:
        print(f"→ ENTRA en el crédito. Sobrante: ${CREDITO_INICIAL_USD - mejor:,.2f}")
    else:
        print(f"→ NO entra en el crédito. Faltan: ${mejor - CREDITO_INICIAL_USD:,.2f}")
    print()
    print("Recordatorio: el crédito expira 6 meses después del ALTA, no del primer uso.")


def main() -> int:
    args = _parse_args()

    clave = os.environ.get("DATABENTO_API_KEY")
    if not clave:
        print("Falta DATABENTO_API_KEY en el entorno.", file=sys.stderr)
        print("  export DATABENTO_API_KEY='db-...'", file=sys.stderr)
        return 2

    try:
        import databento as db
    except ModuleNotFoundError:
        print("Falta el cliente de Databento. Correr con:", file=sys.stderr)
        print(
            "  uv run --no-project --with databento python scripts/quote_databento.py",
            file=sys.stderr,
        )
        return 2

    cliente = db.Historical(clave)

    inicio_ds, fin_ds, crudo = _rango_del_dataset(cliente)
    print(f"Cobertura de {DATASET}: {inicio_ds or '?'} .. {fin_ds or '?'}")
    if isinstance(crudo, str):
        print(f"  ⚠  no se pudo leer el rango: {crudo}")

    start = args.start or inicio_ds
    if not start:
        print("No hay fecha de inicio: pasar --start explícitamente.", file=sys.stderr)
        return 2

    cotizaciones = [
        _cotizar(cliente, simbolo, esquema, stype_in, nota, start, args.end)
        for simbolo, esquema, stype_in, nota in COMBINACIONES
    ]

    _imprimir(cotizaciones, start, args.end)

    if args.json_out:
        volcado = {
            "dataset": DATASET,
            "cobertura": {"start": inicio_ds, "end": fin_ds},
            "rango_cotizado": {"start": start, "end": args.end},
            "cotizado_el": dt.datetime.now(dt.UTC).isoformat(),
            "combinaciones": [
                {
                    "simbolo": c.simbolo,
                    "esquema": c.esquema,
                    "stype_in": c.stype_in,
                    "gb": c.gb,
                    "costos_usd": c.costos,
                    "error": c.error,
                }
                for c in cotizaciones
            ],
        }
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(volcado, fh, indent=2, ensure_ascii=False)
        print(f"\nVolcado en {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
