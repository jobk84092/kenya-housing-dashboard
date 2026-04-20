import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from scoring import enrich_dataframe, filter_listings  # noqa: E402


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "listing_id": 1,
                "county": "Nairobi",
                "estate": "Kilimani",
                "latitude": -1.2921,
                "longitude": 36.8219,
                "price_kes": 8500000,
                "bedrooms": 2,
                "property_type": "apartment",
                "schools_2km": 9,
                "hospitals_3km": 6,
                "transit_stops_1km": 15,
            },
            {
                "listing_id": 2,
                "county": "Nakuru",
                "estate": "Lanet",
                "latitude": -0.3031,
                "longitude": 36.0800,
                "price_kes": 6500000,
                "bedrooms": 3,
                "property_type": "house",
                "schools_2km": 5,
                "hospitals_3km": 3,
                "transit_stops_1km": 6,
            },
        ]
    )


def test_enrich_dataframe_adds_scores() -> None:
    enriched = enrich_dataframe(_sample_df())
    assert "affordability_score" in enriched.columns
    assert "accessibility_score" in enriched.columns
    assert "overall_score" in enriched.columns
    assert enriched["overall_score"].between(0, 100).all()


def test_enrich_dataframe_fills_missing_accessibility_columns() -> None:
    df = _sample_df().drop(columns=["schools_2km", "hospitals_3km", "transit_stops_1km"])
    enriched = enrich_dataframe(df)
    assert "schools_2km" in enriched.columns
    assert "hospitals_3km" in enriched.columns
    assert "transit_stops_1km" in enriched.columns


def test_enrich_dataframe_requires_core_columns() -> None:
    broken = _sample_df().drop(columns=["price_kes"])
    with pytest.raises(ValueError, match="Missing required columns"):
        enrich_dataframe(broken)


def test_filter_listings_applies_all_filters() -> None:
    enriched = enrich_dataframe(_sample_df())
    filtered = filter_listings(
        df=enriched,
        counties=["Nairobi"],
        property_types=["apartment"],
        min_price=8000000,
        max_price=9000000,
        min_bedrooms=2,
        min_overall_score=30,
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["estate"] == "Kilimani"


def test_filter_listings_empty_program_selection_returns_no_rows() -> None:
    df = _sample_df().copy()
    df["housing_program"] = ["Boma Yangu / AHP", "Boma Yangu / AHP"]
    enriched = enrich_dataframe(df)
    out = filter_listings(
        df=enriched,
        counties=["Nairobi", "Nakuru"],
        property_types=["apartment", "house"],
        min_price=0,
        max_price=50_000_000,
        min_bedrooms=1,
        min_overall_score=0,
        housing_programs=[],
    )
    assert len(out) == 0


def test_filter_listings_by_housing_program() -> None:
    df = _sample_df().copy()
    df["housing_program"] = ["Tsavo / affordable corridor", "Boma Yangu / AHP"]
    enriched = enrich_dataframe(df)
    out = filter_listings(
        df=enriched,
        counties=["Nairobi", "Nakuru"],
        property_types=["apartment", "house"],
        min_price=0,
        max_price=50_000_000,
        min_bedrooms=1,
        min_overall_score=0,
        housing_programs=["Tsavo / affordable corridor"],
    )
    assert len(out) == 1
    assert out.iloc[0]["estate"] == "Kilimani"
