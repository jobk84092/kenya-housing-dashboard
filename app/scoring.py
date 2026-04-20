from __future__ import annotations

import pandas as pd

DEFAULT_INCOME_BY_COUNTY = {
    "Nairobi": 150000,
    "Mombasa": 90000,
    "Kiambu": 120000,
    "Nakuru": 85000,
    "Kisumu": 80000,
    "Uasin Gishu": 90000,
    "Machakos": 75000,
    "Kajiado": 90000,
}

REQUIRED_COLUMNS = [
    "listing_id",
    "county",
    "estate",
    "latitude",
    "longitude",
    "price_kes",
    "bedrooms",
    "property_type",
]

ACCESSIBILITY_COLUMNS = ["schools_2km", "hospitals_3km", "transit_stops_1km"]


def validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def _ensure_accessibility_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    for col in ACCESSIBILITY_COLUMNS:
        if col not in enriched.columns:
            enriched[col] = 1
    return enriched


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df)
    enriched = _ensure_accessibility_columns(df)
    enriched["monthly_income_benchmark"] = (
        enriched["county"].map(DEFAULT_INCOME_BY_COUNTY).fillna(80000)
    )
    # Affordability ratio approximates mortgage burden (30% income over 20 years).
    enriched["affordability_ratio"] = (
        enriched["price_kes"] / (enriched["monthly_income_benchmark"] * 12 * 20 * 0.30)
    )
    enriched["affordability_score"] = (100 * (1 - enriched["affordability_ratio"])).clip(
        lower=0, upper=100
    )
    enriched["accessibility_score"] = (
        enriched["schools_2km"] * 12
        + enriched["hospitals_3km"] * 18
        + enriched["transit_stops_1km"] * 10
    ).clip(upper=100)
    enriched["overall_score"] = (
        enriched["affordability_score"] * 0.65 + enriched["accessibility_score"] * 0.35
    ).round(1)
    return enriched


def filter_listings(
    df: pd.DataFrame,
    counties: list[str],
    property_types: list[str],
    min_price: int,
    max_price: int,
    min_bedrooms: int,
    min_overall_score: int,
    housing_programs: list[str] | None = None,
) -> pd.DataFrame:
    mask = (
        (df["county"].isin(counties))
        & (df["property_type"].isin(property_types))
        & (df["price_kes"].between(min_price, max_price))
        & (df["bedrooms"] >= min_bedrooms)
        & (df["overall_score"] >= min_overall_score)
    )
    if "housing_program" in df.columns and housing_programs is not None:
        if len(housing_programs) == 0:
            return df.iloc[0:0].copy()
        mask = mask & (df["housing_program"].isin(housing_programs))
    return df[mask].copy()
