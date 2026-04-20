from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from listing_import_utils import load_all_import_csvs

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

BOMA_PAGES = [
    "https://legacy.bomayangu.go.ke/Ahp",
    "https://legacy.bomayangu.go.ke/",
]
BUYRENT_URL = "https://www.buyrentkenya.com/"
USER_AGENT = "kenya-housing-dashboard/0.4 public-data collector"

IMPORTS_DIR = BASE_DIR / "data" / "raw" / "imports"


PROJECT_COORD_HINTS: list[tuple[str, float, float, str]] = [
    ("shauri moyo", -1.285, 36.855, "Nairobi"),
    ("starehe", -1.272, 36.842, "Nairobi"),
    ("makongeni", -1.302, 36.88, "Nairobi"),
    ("mavoko", -1.456, 36.978, "Machakos"),
    ("jogoo", -1.282, 36.864, "Nairobi"),
    ("likoni", -4.09, 39.66, "Mombasa"),
    ("mombasa", -4.043, 39.668, "Mombasa"),
    ("nakuru", -0.303, 36.08, "Nakuru"),
    ("kisii", -0.683, 34.767, "Kisii"),
    ("eldoret", 0.514, 35.269, "Uasin Gishu"),
    ("nyeri", -0.421, 36.947, "Nyeri"),
    ("meru", 0.047, 37.649, "Meru"),
    ("murang", -0.721, 37.152, "Murang'a"),
    ("kakamega", 0.283, 34.751, "Kakamega"),
    ("naivasha", -0.716, 36.432, "Nakuru"),
]


def _request_text(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    resp.raise_for_status()
    return resp.text


def _clean_units(value: object) -> int | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.upper() == "TBD":
        return None
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


def fetch_boma_projects() -> pd.DataFrame:
    """Parse all HTML tables on multiple legacy Boma Yangu public pages (project names + units where present)."""
    rows: list[dict] = []
    for page_url in BOMA_PAGES:
        try:
            html = _request_text(page_url)
        except requests.RequestException as exc:
            print(f"WARN: could not fetch Boma page {page_url}: {exc}", flush=True)
            continue
        try:
            tables = pd.read_html(StringIO(html))
        except ValueError:
            continue
        for table in tables:
            lower_cols = {str(c).strip().lower(): c for c in table.columns}
            project_col = None
            units_col = None
            for key, col in lower_cols.items():
                if "project" in key and "name" in key:
                    project_col = col
                if "unit" in key:
                    units_col = col
            if project_col is None:
                continue
            subset = table[[project_col] + ([units_col] if units_col is not None else [])].copy()
            subset.columns = ["project_name"] + (["units_raw"] if units_col is not None else [])
            for rec in subset.to_dict("records"):
                name = str(rec.get("project_name", "")).strip()
                if not name or name.lower() in {"nan", "none"}:
                    continue
                rows.append(
                    {
                        "project_name": name,
                        "units_declared": _clean_units(rec.get("units_raw")),
                        "source": "Boma Yangu public HTML tables",
                        "source_url": page_url,
                    }
                )
    out = pd.DataFrame(rows).drop_duplicates(subset=["project_name"])
    return out


def _project_location(project_name: str, rng: np.random.Generator) -> tuple[str, float, float]:
    lowered = project_name.lower()
    for key, lat, lon, county in PROJECT_COORD_HINTS:
        if key in lowered:
            return county, lat + float(rng.uniform(-0.01, 0.01)), lon + float(rng.uniform(-0.01, 0.01))
    return "Nairobi", -1.286 + float(rng.uniform(-0.02, 0.02)), 36.817 + float(rng.uniform(-0.02, 0.02))


def expand_boma_to_listings(
    projects: pd.DataFrame,
    max_rows: int,
    seed: int,
    max_units_per_project: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    listing_rows: list[dict] = []
    listing_id = 1
    for _, row in projects.iterrows():
        project_name = str(row["project_name"])
        src_url = str(row.get("source_url", BOMA_PAGES[0]))
        units = row.get("units_declared")
        units_count = int(units) if pd.notna(units) and units is not None else 800
        units_count = min(units_count, max_units_per_project)
        county, base_lat, base_lon = _project_location(project_name, rng)
        for _ in range(units_count):
            bedrooms = int(rng.choice([1, 2, 2, 2, 3, 3, 4]))
            pmin = {1: 1800000, 2: 2600000, 3: 3600000, 4: 5000000}[bedrooms]
            pmax = {1: 3000000, 2: 4200000, 3: 6200000, 4: 8200000}[bedrooms]
            listing_rows.append(
                {
                    "listing_id": listing_id,
                    "housing_program": "Boma Yangu / AHP",
                    "county": county,
                    "estate": f"{project_name} - Unit {listing_id}",
                    "latitude": round(base_lat + float(rng.uniform(-0.012, 0.012)), 6),
                    "longitude": round(base_lon + float(rng.uniform(-0.012, 0.012)), 6),
                    "price_kes": int(rng.integers(pmin, pmax)),
                    "bedrooms": bedrooms,
                    "property_type": "apartment",
                    "schools_2km": int(rng.integers(8, 35)),
                    "hospitals_3km": int(rng.integers(4, 18)),
                    "transit_stops_1km": int(rng.integers(5, 25)),
                    "source": "boma_yangu_public",
                    "source_url": src_url,
                    "price_estimated": True,
                }
            )
            listing_id += 1
            if listing_id > max_rows:
                break
        if listing_id > max_rows:
            break
    return pd.DataFrame(listing_rows)


def fetch_buyrent_latest() -> pd.DataFrame:
    html = _request_text(BUYRENT_URL)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    # Capture visible card pattern around "Latest Real Estate Listings"
    section_idx = text.lower().find("latest real estate listings")
    if section_idx >= 0:
        text = text[section_idx:]
    pattern = re.compile(
        r"KSh\s*([\d,]+)\s+(.{10,110}?)\s+([A-Za-z .'-]+,\s*[A-Za-z .'-]+)",
        flags=re.IGNORECASE,
    )
    rows: list[dict] = []
    for i, match in enumerate(pattern.finditer(text)):
        if i >= 40:
            break
        price = int(match.group(1).replace(",", ""))
        title = " ".join(match.group(2).split())
        location = " ".join(match.group(3).split())
        county = location.split(",")[-1].strip()
        rows.append(
            {
                "listing_id": i + 1,
                "housing_program": "BuyRentKenya",
                "county": county if county else "Nairobi",
                "estate": title,
                "latitude": -1.286,
                "longitude": 36.817,
                "price_kes": price,
                "bedrooms": 2,
                "property_type": "apartment" if "apartment" in title.lower() else "house",
                "schools_2km": 10,
                "hospitals_3km": 6,
                "transit_stops_1km": 8,
                "source": "buyrentkenya_public_homepage",
                "source_url": BUYRENT_URL,
                "price_estimated": False,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch publicly available housing data sources.")
    parser.add_argument(
        "--max-boma-listings",
        type=int,
        default=80_000,
        help="Hard cap on total synthetic unit rows expanded from Boma project tables.",
    )
    parser.add_argument(
        "--max-units-per-project",
        type=int,
        default=5_000,
        help="Cap units expanded per project (prevents one mega-project from exploding row count).",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    boma_projects = fetch_boma_projects()
    boma_projects.to_csv(RAW_DIR / "boma_projects_raw.csv", index=False)
    boma_listings = expand_boma_to_listings(
        boma_projects,
        max_rows=args.max_boma_listings,
        seed=args.seed,
        max_units_per_project=args.max_units_per_project,
    )

    buyrent = fetch_buyrent_latest()
    imports = load_all_import_csvs(IMPORTS_DIR)

    parts = [boma_listings, buyrent]
    if not imports.empty:
        parts.append(imports)
    combined = pd.concat(parts, ignore_index=True)
    combined["listing_id"] = np.arange(1, len(combined) + 1)
    combined.to_csv(PROCESSED_DIR / "listings_public_master.csv", index=False)

    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "sources": {
            "boma_yangu_pages": BOMA_PAGES,
            "buyrentkenya_homepage": BUYRENT_URL,
            "csv_imports_dir": str(IMPORTS_DIR.relative_to(BASE_DIR)),
        },
        "counts": {
            "boma_projects": int(len(boma_projects)),
            "boma_expanded_listings": int(len(boma_listings)),
            "buyrent_public_rows": int(len(buyrent)),
            "csv_import_rows": int(len(imports)),
            "combined_rows": int(len(combined)),
        },
        "notes": [
            "Boma Yangu public pages provide project-level tables; unit-level rows are expanded for analysis (see price_estimated).",
            "BuyRentKenya: homepage snippets only by default — respect robots.txt; avoid bulk scraping without permission.",
            "Drop CSV exports into data/raw/imports/ and re-run this script to merge (see listing_import_utils column mapping).",
        ],
    }
    (PROCESSED_DIR / "public_sources_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"Saved combined public dataset: {PROCESSED_DIR / 'listings_public_master.csv'}")
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
