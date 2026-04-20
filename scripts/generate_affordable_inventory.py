#!/usr/bin/env python3
"""
Generate a large synthetic inventory of affordable-housing style listings.

Kenya's Boma Yangu / Affordable Housing Programme (AHP) does not publish a
public bulk API or CSV. This script models realistic project names, counties,
coordinates (jittered around known corridors), and price bands typical of
social/affordable inventory for dashboard and portfolio use.

Run: python scripts/generate_affordable_inventory.py --n 12000
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE_DIR / "data" / "sample" / "listings_affordable_bulk.csv"

# (program, estate_template, county, center_lat, center_lon, radius_km approx as deg)
# Names reflect public AHP-style projects and common affordable corridors; not an official registry.
PROJECT_HUBS: list[tuple[str, str, str, float, float, float]] = [
    ("Boma Yangu / AHP", "Park Road Ngara", "Nairobi", -1.276, 36.825, 0.012),
    ("Boma Yangu / AHP", "Mukuru kwa Reuben", "Nairobi", -1.313, 36.895, 0.015),
    ("Boma Yangu / AHP", "Shauri Moyo", "Nairobi", -1.285, 36.855, 0.01),
    ("Boma Yangu / AHP", "Starehe", "Nairobi", -1.272, 36.842, 0.01),
    ("Boma Yangu / AHP", "Clay City Kasarani", "Nairobi", -1.218, 36.905, 0.018),
    ("Boma Yangu / AHP", "Ruiru Kamulu", "Kiambu", -1.165, 36.985, 0.02),
    ("Boma Yangu / AHP", "Athi River Mavoko", "Machakos", -1.456, 36.978, 0.025),
    ("Boma Yangu / AHP", "Syokimau Phase", "Machakos", -1.362, 36.945, 0.018),
    ("Tsavo / affordable corridor", "Tsavo Road Athi River", "Machakos", -1.448, 36.965, 0.02),
    ("Tsavo / affordable corridor", "Kitengela South", "Kajiado", -1.495, 36.955, 0.022),
    ("Private affordable", "Ongata Rongai", "Kajiado", -1.397, 36.764, 0.02),
    ("Private affordable", "Ruiru Eastern Bypass", "Kiambu", -1.135, 36.965, 0.02),
    ("Boma Yangu / AHP", "Embakasi Pipeline", "Nairobi", -1.313, 36.895, 0.015),
    ("County affordable", "Kisumu Manyatta", "Kisumu", -0.117, 34.761, 0.015),
    ("County affordable", "Nakuru Pipeline", "Nakuru", -0.296, 36.054, 0.018),
    ("County affordable", "Eldoret Langas", "Uasin Gishu", 0.499, 35.259, 0.02),
    ("Coast affordable", "Mombasa Likoni", "Mombasa", -4.09, 39.66, 0.02),
    ("Coast affordable", "Mombasa Bamburi", "Mombasa", -3.979, 39.727, 0.018),
    ("Boma Yangu / AHP", "Kangundo Road", "Machakos", -1.32, 37.02, 0.025),
    ("Boma Yangu / AHP", "Thika Road corridor", "Kiambu", -1.12, 36.95, 0.02),
]

PROPERTY_TYPES = ["apartment", "apartment", "apartment", "maisonette"]


def _price_for(bedrooms: int, program: str, rng: np.random.Generator) -> int:
    """Rough affordable bands (KES); AHP-style lower than market core."""
    base = {1: (1_800_000, 3_200_000), 2: (2_400_000, 4_200_000), 3: (3_200_000, 5_800_000), 4: (4_000_000, 7_500_000)}
    lo, hi = base.get(bedrooms, (2_000_000, 4_500_000))
    if "Tsavo" in program:
        lo, hi = int(lo * 0.95), int(hi * 1.05)
    if "Boma Yangu" in program or "AHP" in program:
        lo, hi = int(lo * 0.92), int(hi * 0.98)
    return int(rng.integers(lo, hi, endpoint=True))


def generate(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hubs = np.array(PROJECT_HUBS, dtype=object)
    idx = rng.integers(0, len(PROJECT_HUBS), size=n)
    rows: list[dict] = []
    for i in range(n):
        program, estate_base, county, clat, clon, rad = hubs[idx[i]]
        lat = float(clat + rng.uniform(-rad, rad))
        lon = float(clon + rng.uniform(-rad, rad))
        bedrooms = int(rng.choice([1, 2, 2, 3, 3, 3, 4], size=1)[0])
        prop = str(rng.choice(PROPERTY_TYPES))
        block = int(rng.integers(1, 28))
        unit = int(rng.integers(101, 2200))
        estate = f"{estate_base} — Block {block} Unit {unit}"
        price = _price_for(bedrooms, program, rng)
        # Plausible amenity counts without calling APIs (urban projects skew higher)
        urban = county == "Nairobi" or "Boma" in program
        s_lo, s_hi = (8, 45) if urban else (4, 28)
        h_lo, h_hi = (4, 22) if urban else (2, 12)
        t_lo, t_hi = (6, 30) if urban else (2, 14)
        rows.append(
            {
                "listing_id": i + 1,
                "housing_program": program,
                "county": county,
                "estate": estate,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "price_kes": price,
                "bedrooms": bedrooms,
                "property_type": prop,
                "schools_2km": int(rng.integers(s_lo, s_hi + 1)),
                "hospitals_3km": int(rng.integers(h_lo, h_hi + 1)),
                "transit_stops_1km": int(rng.integers(t_lo, t_hi + 1)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate affordable-housing style listing inventory.")
    parser.add_argument("--n", type=int, default=25_000, help="Number of listings to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output CSV path.",
    )
    args = parser.parse_args()
    df = generate(n=args.n, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} rows to {args.output}")
    print("Programs:", df["housing_program"].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
