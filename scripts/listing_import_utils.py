"""Normalize user-supplied CSV exports into the dashboard listing schema."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REQUIRED_OUT = [
    "listing_id",
    "housing_program",
    "county",
    "sub_county",
    "estate",
    "latitude",
    "longitude",
    "price_kes",
    "bedrooms",
    "property_type",
    "listing_type",
    "contact_phone",
    "contact_email",
    "schools_2km",
    "hospitals_3km",
    "transit_stops_1km",
    "source",
    "source_url",
    "price_estimated",
]


def _first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    for col in df.columns:
        cl = col.lower().strip()
        for cand in candidates:
            if cand.lower() in cl:
                return col
    return None


def _parse_price(val: object) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    s = re.sub(r"[Kk]Sh|\$|,|\s", "", s)
    try:
        return float(s)
    except ValueError:
        m = re.search(r"[\d.]+", s)
        return float(m.group(0)) if m else None


def normalize_import_dataframe(df: pd.DataFrame, source_tag: str, source_url: str) -> pd.DataFrame:
    """Map common export column names to our schema. Fills sensible defaults for missing optional fields."""
    if df.empty:
        return pd.DataFrame(columns=REQUIRED_OUT)

    out = pd.DataFrame()
    c_estate = _first_col(df, ["estate", "title", "name", "property", "listing", "description"])
    c_price = _first_col(df, ["price_kes", "price", "amount", "asking_price", "rent"])
    c_county = _first_col(df, ["county", "region", "location", "area", "city"])
    c_lat = _first_col(df, ["latitude", "lat"])
    c_lon = _first_col(df, ["longitude", "lon", "lng"])
    c_bed = _first_col(df, ["bedrooms", "beds", "bed"])
    c_type = _first_col(df, ["property_type", "type", "category"])
    c_sub = _first_col(df, ["sub_county", "subcounty", "district", "division", "constituency"])
    c_lt = _first_col(df, ["listing_type", "transaction", "tenure", "deal_type"])
    c_phone = _first_col(df, ["contact_phone", "phone", "mobile", "tel", "msisdn"])
    c_email = _first_col(df, ["contact_email", "email", "e-mail"])

    if c_estate is None or c_price is None:
        raise ValueError(
            "Import CSV must include at least title/estate and price columns "
            "(e.g. estate, title, price_kes, price)."
        )

    prices = df[c_price].map(_parse_price)
    pos = prices.fillna(0) > 0
    df = df.loc[pos].reset_index(drop=True)
    prices = prices.loc[pos].reset_index(drop=True)
    if df.empty:
        raise ValueError("No rows with positive price after parsing.")
    n = len(df)
    out = pd.DataFrame()
    out["estate"] = df[c_estate].astype(str).str.strip()
    out["price_kes"] = prices.fillna(0).astype(int)
    out["county"] = (
        df[c_county].astype(str).str.strip()
        if c_county
        else pd.Series(["Nairobi"] * n, index=df.index)
    )
    out["latitude"] = (
        pd.to_numeric(df[c_lat], errors="coerce")
        if c_lat
        else pd.Series([-1.286] * n, index=df.index)
    ).fillna(-1.286)
    out["longitude"] = (
        pd.to_numeric(df[c_lon], errors="coerce")
        if c_lon
        else pd.Series([36.817] * n, index=df.index)
    ).fillna(36.817)
    out["bedrooms"] = (
        pd.to_numeric(df[c_bed], errors="coerce").fillna(2).astype(int)
        if c_bed
        else pd.Series([2] * n, index=df.index)
    )
    out["property_type"] = (
        df[c_type].astype(str).str.lower().str.strip()
        if c_type
        else pd.Series(["apartment"] * n, index=df.index)
    )
    out["sub_county"] = (
        df[c_sub].astype(str).str.strip()
        if c_sub
        else pd.Series([""] * n, index=df.index)
    )
    if c_lt:
        lt = df[c_lt].astype(str).str.strip().str.lower()
        lt = lt.replace(
            {
                "let": "rent",
                "lease": "rent",
                "rental": "rent",
                "to let": "rent",
                "for rent": "rent",
                "sale": "sale",
                "for sale": "sale",
                "sell": "sale",
            }
        )
        out["listing_type"] = lt.where(lt.isin(["sale", "rent"]), "sale")
    else:
        out["listing_type"] = "sale"
    out["contact_phone"] = (
        df[c_phone].astype(str).str.strip()
        if c_phone
        else pd.Series([""] * n, index=df.index)
    )
    out["contact_email"] = (
        df[c_email].astype(str).str.strip()
        if c_email
        else pd.Series([""] * n, index=df.index)
    )
    out["housing_program"] = source_tag
    out["schools_2km"] = 8
    out["hospitals_3km"] = 5
    out["transit_stops_1km"] = 7
    out["source"] = "csv_import"
    out["source_url"] = source_url
    out["price_estimated"] = False
    out["listing_id"] = 0
    return out[REQUIRED_OUT]


def load_all_import_csvs(imports_dir: Path) -> pd.DataFrame:
    imports_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    for path in sorted(imports_dir.glob("*.csv")):
        tag = path.stem[:60]
        raw = pd.read_csv(path)
        try:
            frames.append(normalize_import_dataframe(raw, source_tag=tag, source_url=f"file://{path.name}"))
        except ValueError as exc:
            print(f"WARN: skip import {path.name}: {exc}", flush=True)
    if not frames:
        return pd.DataFrame(columns=REQUIRED_OUT)
    return pd.concat(frames, ignore_index=True)
