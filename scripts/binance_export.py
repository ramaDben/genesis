"""Extractor de datos históricos M1 de Binance (Spot y Futures USDT-M).

Descarga archivos mensuales oficiales de Binance Vision (data.binance.vision),
extrae las barras de 1 minuto con conteo de transacciones y volumen real,
y las persiste en formato Parquet canónico compatible con `RawParquetStore` de Genesis.

Uso:
    uv run python scripts/binance_export.py \
        --symbol BTCUSDT --market futures --start 2024-01 --end 2026-06
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from genesis.data.metadata import ArtifactMetadata, current_git_commit
from genesis.data.mt5_export import ChunkWindow, Granularity, RawParquetStore

CONFIG_VERSION: str = "genesis-binance-export/1"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _month_range(start_str: str, end_str: str) -> list[str]:
    """Genera lista de meses 'YYYY-MM' entre start_str y end_str inclusivos."""
    start_dt = dt.datetime.strptime(start_str, "%Y-%m")
    end_dt = dt.datetime.strptime(end_str, "%Y-%m")

    current = start_dt
    months = []
    while current <= end_dt:
        months.append(current.strftime("%Y-%m"))
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        current = dt.datetime(year, month, 1)
    return months


def _binance_vision_url(symbol: str, market: str, month: str) -> str:
    """Construye URL de Binance Vision para klines mensuales de 1 minuto."""
    if market == "futures":
        return f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/1m/{symbol}-1m-{month}.zip"
    elif market == "spot":
        return f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{month}.zip"
    else:
        raise ValueError(f"Mercado no soportado: {market!r}. Usar 'futures' o 'spot'.")


def export_binance_m1(
    symbol: str,
    market: str,
    start_month: str,
    end_month: str,
    store_dir: Path,
    repo_root: Path,
) -> None:
    store = RawParquetStore(store_dir)
    months = _month_range(start_month, end_month)
    commit = current_git_commit(repo_root)
    firm_hash = f"binance-{market}"

    print(f"Iniciando exportación de {symbol} ({market}) desde {start_month} hasta {end_month}...")
    print(f"Total de meses a procesar: {len(months)}")

    downloaded = 0
    cached = 0
    errors = 0

    for month in months:
        year_int = int(month.split("-")[0])
        month_int = int(month.split("-")[1])

        # Ventana nominal del mes
        win_start = dt.datetime(year_int, month_int, 1, 0, 0, tzinfo=dt.UTC)
        next_year = year_int + (1 if month_int == 12 else 0)
        next_month = 1 if month_int == 12 else month_int + 1
        win_end = dt.datetime(next_year, next_month, 1, 0, 0, tzinfo=dt.UTC) - dt.timedelta(
            minutes=1
        )
        window = ChunkWindow(win_start, win_end)

        if store.has_chunk(symbol, Granularity.M1, window):
            print(f"  [{month}] ✓ En caché (skip)")
            cached += 1
            continue

        url = _binance_vision_url(symbol, market, month)
        print(f"  [{month}] Descargando desde Binance Vision...")
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310

        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                zip_data = resp.read()
        except urllib.error.HTTPError as exc:
            print(f"  [{month}] ✗ Error HTTP {exc.code}: {exc.reason}")
            errors += 1
            continue
        except Exception as exc:
            print(f"  [{month}] ✗ Error descargando: {exc}")
            errors += 1
            continue

        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                # Detectar si la primera línea tiene encabezado de texto o numérico
                first_line = f.readline().decode("utf-8").strip()
                f.seek(0)
                has_header = "open_time" in first_line.lower() or "open" in first_line.lower()

                if has_header:
                    raw_df = pd.read_csv(f)
                    # Normalizar nombres de columnas a minúsculas
                    raw_df.columns = [c.lower() for c in raw_df.columns]
                    open_time_col = "open_time"
                    open_col = "open"
                    high_col = "high"
                    low_col = "low"
                    close_col = "close"
                    count_col = "count" if "count" in raw_df.columns else "number_of_trades"
                else:
                    raw_df = pd.read_csv(
                        f,
                        header=None,
                        usecols=[0, 1, 2, 3, 4, 8],
                        names=["open_time", "open", "high", "low", "close", "count"],
                    )
                    open_time_col = "open_time"
                    open_col = "open"
                    high_col = "high"
                    low_col = "low"
                    close_col = "close"
                    count_col = "count"

        df = pd.DataFrame()
        df["timestamp"] = pd.to_datetime(raw_df[open_time_col].astype("int64"), unit="ms", utc=True)
        df["open"] = raw_df[open_col].astype("float64")
        df["high"] = raw_df[high_col].astype("float64")
        df["low"] = raw_df[low_col].astype("float64")
        df["close"] = raw_df[close_col].astype("float64")
        df["tick_volume"] = raw_df[count_col].astype("int64")

        # Ajustar ventana temporal real de los datos
        actual_start = df["timestamp"].iloc[0].to_pydatetime()
        actual_end = df["timestamp"].iloc[-1].to_pydatetime()
        actual_window = ChunkWindow(actual_start, actual_end)

        chunk_hash = store.chunk_hash(df)
        metadata = ArtifactMetadata(
            config_version=CONFIG_VERSION,
            dataset_hash=chunk_hash,
            firm_profile_hash=firm_hash,
            time_range=(actual_start, actual_end),
            git_commit=commit,
        )

        out_path = store.write_chunk(df, symbol, Granularity.M1, actual_window, metadata)
        print(
            f"  [{month}] Guardado: {out_path.name} ({len(df):,} barras, h:{chunk_hash[:8]})"
        )
        downloaded += 1

    print("\n" + "=" * 50)
    print(f"Resumen de exportación para {symbol}:")
    print(f"  • Meses descargados: {downloaded}")
    print(f"  • Meses en caché:     {cached}")
    print(f"  • Errores/Faltantes:  {errors}")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exportador M1 de Binance para Genesis")
    parser.add_argument("--symbol", default="BTCUSDT", help="Símbolo de Binance (default: BTCUSDT)")
    parser.add_argument(
        "--market",
        choices=["futures", "spot"],
        default="futures",
        help="Mercado (default: futures)",
    )
    parser.add_argument("--start", default="2024-01", help="Mes inicial YYYY-MM (default: 2024-01)")
    parser.add_argument("--end", default="2026-06", help="Mes final YYYY-MM (default: 2026-06)")
    parser.add_argument(
        "--store", default="data/raw", help="Directorio raíz del store Parquet (default: data/raw)"
    )

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    store_dir = repo_root / args.store

    export_binance_m1(
        symbol=args.symbol,
        market=args.market,
        start_month=args.start,
        end_month=args.end,
        store_dir=store_dir,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()
