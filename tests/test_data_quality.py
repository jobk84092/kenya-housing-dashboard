import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from data_quality import validate_listings  # noqa: E402


def _valid_df() -> pd.DataFrame:
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
                "schools_2km": 5,
                "hospitals_3km": 2,
                "transit_stops_1km": 4,
            }
        ]
    )


def test_validate_listings_accepts_valid_data() -> None:
    result = validate_listings(_valid_df())
    assert result.is_valid is True
    assert result.errors == []


def test_validate_listings_rejects_missing_columns() -> None:
    broken = _valid_df().drop(columns=["price_kes"])
    result = validate_listings(broken)
    assert result.is_valid is False
    assert any("Missing required columns" in err for err in result.errors)


def test_validate_listings_rejects_out_of_bounds_coordinates() -> None:
    broken = _valid_df().copy()
    broken.loc[0, "latitude"] = 20.0
    result = validate_listings(broken)
    assert result.is_valid is False
    assert any("latitude values outside Kenya bounds" in err for err in result.errors)
