from __future__ import annotations

import json
import time
import argparse
from datetime import UTC, datetime
import math
from pathlib import Path

import pandas as pd
import requests

from data_quality import validate_listings
from fetch_worldbank import DEFAULT_INDICATORS, fetch_multiple

BASE_DIR = Path(__file__).resolve().parents[1]
BULK_LISTINGS = BASE_DIR / "data" / "sample" / "listings_affordable_bulk.csv"
SAMPLE_LISTINGS = BULK_LISTINGS if BULK_LISTINGS.exists() else BASE_DIR / "data" / "sample" / "listings_sample.csv"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_LISTINGS = PROCESSED_DIR / "listings_enriched.csv"
WORLD_BANK_FILE = PROCESSED_DIR / "worldbank_indicators_ke.csv"
METADATA_FILE = PROCESSED_DIR / "refresh_metadata.json"

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "kenya-housing-dashboard/0.2 (portfolio project)"


def _bounding_box(lat: float, lon: float, radius_m: int) -> str:
    lat_delta = radius_m / 111_000
    lon_delta = radius_m / (111_000 * max(math.cos(math.radians(lat)), 0.1))
    left = lon - lon_delta
    right = lon + lon_delta
    top = lat + lat_delta
    bottom = lat - lat_delta
    return f"{left},{top},{right},{bottom}"


def _nominatim_count(lat: float, lon: float, radius_m: int, query_text: str, limit: int = 200) -> int:
    bbox = _bounding_box(lat, lon, radius_m)
    params = {
        "q": query_text,
        "format": "jsonv2",
        "bounded": 1,
        "viewbox": bbox,
        "limit": limit,
    }
    response = requests.get(
        NOMINATIM_SEARCH_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return len(payload) if isinstance(payload, list) else 0


def _query_with_retries(lat: float, lon: float, radius_m: int, query_text: str, retries: int = 3) -> int:
    for attempt in range(1, retries + 1):
        try:
            return _nominatim_count(lat=lat, lon=lon, radius_m=radius_m, query_text=query_text)
        except requests.RequestException:
            if attempt == retries:
                return 0
            time.sleep(attempt * 1.5)
    return 0


def enrich_accessibility(df: pd.DataFrame, request_pause_sec: float = 1.2) -> pd.DataFrame:
    enriched = df.copy()
    schools: list[int] = []
    hospitals: list[int] = []
    transit_stops: list[int] = []

    total = len(enriched)
    for idx, row in enumerate(enriched.itertuples(index=False), start=1):
        print(f"Enriching listing {idx}/{total}...", flush=True)
        lat = float(row.latitude)
        lon = float(row.longitude)
        schools.append(_query_with_retries(lat, lon, 2000, "school"))
        hospitals.append(
            _query_with_retries(lat, lon, 3000, "hospital")
            + _query_with_retries(lat, lon, 3000, "clinic")
        )
        transit_stops.append(_query_with_retries(lat, lon, 1000, "bus stop"))
        time.sleep(request_pause_sec)

    enriched["schools_2km"] = schools
    enriched["hospitals_3km"] = hospitals
    enriched["transit_stops_1km"] = transit_stops
    return enriched


def refresh() -> None:
    parser = argparse.ArgumentParser(description="Refresh external datasets used by dashboard.")
    parser.add_argument(
        "--max-listings",
        type=int,
        default=0,
        help="Optional cap for number of listings to enrich (0 means all).",
    )
    parser.add_argument(
        "--request-pause-sec",
        type=float,
        default=1.2,
        help="Pause between listing enrichments to avoid API overload.",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    listings = pd.read_csv(SAMPLE_LISTINGS)
    if args.max_listings > 0:
        listings = listings.head(args.max_listings).copy()
    enriched = enrich_accessibility(listings, request_pause_sec=args.request_pause_sec)

    dq_result = validate_listings(enriched)
    if not dq_result.is_valid:
        raise RuntimeError("Data quality checks failed: " + " | ".join(dq_result.errors))

    enriched.to_csv(PROCESSED_LISTINGS, index=False)

    wb = fetch_multiple(indicators=DEFAULT_INDICATORS, country="KE")
    wb.to_csv(WORLD_BANK_FILE, index=False)

    metadata = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "run_parameters": {
            "max_listings": int(args.max_listings),
            "request_pause_sec": float(args.request_pause_sec),
        },
        "sources": {
            "listings_base": str(SAMPLE_LISTINGS.relative_to(BASE_DIR)),
            "accessibility_api": NOMINATIM_SEARCH_URL,
            "macro_api": "https://api.worldbank.org",
        },
        "outputs": {
            "listings_enriched": str(PROCESSED_LISTINGS.relative_to(BASE_DIR)),
            "worldbank_indicators": str(WORLD_BANK_FILE.relative_to(BASE_DIR)),
        },
        "row_counts": {
            "listings_enriched": int(len(enriched)),
            "worldbank_indicators": int(len(wb)),
        },
        "warnings": dq_result.warnings,
        "quality_status": "passed",
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Refreshed data successfully. Metadata saved to {METADATA_FILE}")


if __name__ == "__main__":
    refresh()
