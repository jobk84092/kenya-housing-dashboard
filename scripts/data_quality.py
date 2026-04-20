from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

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


@dataclass
class DataQualityResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


def validate_listings(df: pd.DataFrame) -> DataQualityResult:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return DataQualityResult(is_valid=False, errors=errors, warnings=warnings)

    if df.empty:
        errors.append("Listings dataframe is empty.")
        return DataQualityResult(is_valid=False, errors=errors, warnings=warnings)

    duplicate_ids = df["listing_id"].duplicated().sum()
    if duplicate_ids > 0:
        errors.append(f"Found {duplicate_ids} duplicated listing_id values.")

    bad_lat = (~df["latitude"].between(-5.5, 5.5)).sum()
    bad_lon = (~df["longitude"].between(33.5, 42.5)).sum()
    if bad_lat > 0:
        errors.append(f"Found {bad_lat} latitude values outside Kenya bounds.")
    if bad_lon > 0:
        errors.append(f"Found {bad_lon} longitude values outside Kenya bounds.")

    non_positive_price = (df["price_kes"] <= 0).sum()
    if non_positive_price > 0:
        errors.append(f"Found {non_positive_price} non-positive prices.")

    missing_core = df[["county", "estate", "property_type"]].isna().sum().sum()
    if missing_core > 0:
        errors.append(f"Found {missing_core} missing values in key categorical fields.")

    if "schools_2km" not in df.columns or "hospitals_3km" not in df.columns or "transit_stops_1km" not in df.columns:
        warnings.append("Accessibility columns are missing; enrichment appears incomplete.")

    return DataQualityResult(is_valid=(len(errors) == 0), errors=errors, warnings=warnings)
