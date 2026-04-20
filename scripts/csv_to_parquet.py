#!/usr/bin/env python3
"""Convert a large listings CSV to Parquet for faster loads and smaller disk footprint.

Example:
  python scripts/csv_to_parquet.py \\
    --input data/sample/listings_affordable_bulk.csv \\
    --output data/processed/listings_mega.parquet
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert listings CSV to Parquet.")
    parser.add_argument("--input", type=Path, required=True, help="Source CSV path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/listings_mega.parquet"),
        help="Destination Parquet path (default: data/processed/listings_mega.parquet).",
    )
    parser.add_argument("--chunksize", type=int, default=200_000, help="Rows per chunk (streaming write).")
    args = parser.parse_args()

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("pyarrow is required. Run: pip install pyarrow") from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer: pq.ParquetWriter | None = None
    total = 0
    for chunk in pd.read_csv(args.input, chunksize=args.chunksize):
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(str(args.output), table.schema, compression="snappy")
        writer.write_table(table)
        total += len(chunk)
        print(f"Wrote {total:,} rows...", flush=True)
    if writer is not None:
        writer.close()
    print(f"Done. {total:,} rows -> {args.output}")


if __name__ == "__main__":
    main()
