#!/usr/bin/env python3
"""Build a smaller listings parquet for Cloud / low-memory deploys."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "data" / "processed" / "listings_public_master.csv"
OUT_PARQUET = ROOT / "data" / "processed" / "listings_cloud.parquet"
OUT_CSV = ROOT / "data" / "processed" / "listings_cloud.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.source.exists():
        bulk = ROOT / "data" / "sample" / "listings_affordable_bulk.csv"
        args.source = bulk if bulk.exists() else ROOT / "data" / "sample" / "listings_sample.csv"

    df = pd.read_csv(args.source)
    n = min(args.n, len(df))
    subset = df.sample(n=n, random_state=args.seed) if len(df) > n else df

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    subset.to_parquet(OUT_PARQUET, index=False)
    subset.to_csv(OUT_CSV, index=False)
    print(f"Wrote {len(subset):,} rows -> {OUT_PARQUET.name} ({OUT_PARQUET.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
