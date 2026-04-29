import json
from pathlib import Path

import pandas as pd
import streamlit as st

from scoring import enrich_dataframe

st.set_page_config(page_title="Kenya Affordable Housing Dashboard", layout="wide")

MEGA_PARQUET = Path("data/processed/listings_mega.parquet")


@st.cache_data
def load_data() -> pd.DataFrame:
    public_path = Path("data/processed/listings_public_master.csv")
    bulk_path = Path("data/sample/listings_affordable_bulk.csv")
    enriched_path = Path("data/processed/listings_enriched.csv")
    sample_path = Path("data/sample/listings_sample.csv")

    if MEGA_PARQUET.exists():
        try:
            return enrich_dataframe(pd.read_parquet(MEGA_PARQUET))
        except ImportError as exc:
            raise RuntimeError(
                "Install pyarrow (`pip install pyarrow`) to read parquet data."
            ) from exc
    if public_path.exists():
        return enrich_dataframe(pd.read_csv(public_path))
    if bulk_path.exists():
        return enrich_dataframe(pd.read_csv(bulk_path))
    if enriched_path.exists():
        return enrich_dataframe(pd.read_csv(enriched_path))
    return enrich_dataframe(pd.read_csv(sample_path))


def get_refresh_metadata() -> dict:
    metadata_path = Path("data/processed/refresh_metadata.json")
    if not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def format_kes(value: float) -> str:
    return f"KES {int(value):,}"


def build_news_items(frame: pd.DataFrame, metadata: dict) -> list[tuple[str, str]]:
    refresh_time = metadata.get("generated_at_utc", "not available yet")
    items = [
        (
            "Latest data refresh",
            f"Our housing data was last refreshed on: {refresh_time}.",
        )
    ]

    cheapest = (
        frame.groupby("county", as_index=False)["price_kes"]
        .median()
        .sort_values("price_kes", ascending=True)
        .head(1)
    )
    if not cheapest.empty:
        row = cheapest.iloc[0]
        items.append(
            (
                "Most affordable county in current listings",
                f"{row['county']} has the lowest median listing price at {format_kes(row['price_kes'])}.",
            )
        )

    if "housing_program" in frame.columns and frame["housing_program"].notna().any():
        top_program = frame["housing_program"].value_counts().head(1)
        if not top_program.empty:
            items.append(
                (
                    "Most visible affordable housing program",
                    f"{top_program.index[0]} currently has the most listings in this dashboard.",
                )
            )
    else:
        active_county = frame["county"].value_counts().head(1)
        if not active_county.empty:
            items.append(
                (
                    "Most active location",
                    f"{active_county.index[0]} currently has the highest number of visible listings.",
                )
            )
    return items


def build_developments(frame: pd.DataFrame) -> pd.DataFrame:
    if "housing_program" in frame.columns and frame["housing_program"].notna().any():
        grouped = (
            frame.groupby("housing_program", as_index=False)
            .agg(
                listings=("listing_id", "count"),
                median_price=("price_kes", "median"),
                avg_score=("overall_score", "mean"),
            )
            .sort_values("listings", ascending=False)
            .head(8)
        )
        grouped = grouped.rename(columns={"housing_program": "development"})
    else:
        grouped = (
            frame.groupby("county", as_index=False)
            .agg(
                listings=("listing_id", "count"),
                median_price=("price_kes", "median"),
                avg_score=("overall_score", "mean"),
            )
            .sort_values("listings", ascending=False)
            .head(8)
            .rename(columns={"county": "development"})
        )

    grouped["median_price"] = grouped["median_price"].map(format_kes)
    grouped["avg_score"] = grouped["avg_score"].round(1)
    return grouped


df = load_data()
metadata = get_refresh_metadata()

st.title("Kenya Affordable Housing Dashboard")
st.caption(
    "A simple home page for beginners: see what is happening, where developments are active, and the key numbers."
)

news_col, dev_col, stats_col = st.columns([1.2, 1.2, 1])

with news_col:
    st.subheader("News")
    for headline, detail in build_news_items(df, metadata):
        st.markdown(f"**{headline}**")
        st.write(detail)

with dev_col:
    st.subheader("Developments")
    developments = build_developments(df)
    st.dataframe(developments, use_container_width=True, hide_index=True)

with stats_col:
    st.subheader("Stats")
    st.metric("Total listings", f"{len(df):,}")
    st.metric("Median price", format_kes(df["price_kes"].median()))
    st.metric("Average score", f"{df['overall_score'].mean():.1f} / 100")
    below_5m = (df["price_kes"] <= 5_000_000).mean() * 100
    st.metric("Homes <= KES 5M", f"{below_5m:.0f}%")

st.divider()
st.subheader("Starter shortlist (first look)")
starter = (
    df.sort_values("overall_score", ascending=False)
    .head(12)[["county", "estate", "property_type", "bedrooms", "price_kes", "overall_score"]]
    .copy()
)
starter["price_kes"] = starter["price_kes"].map(format_kes)
starter["overall_score"] = starter["overall_score"].round(1)
st.dataframe(starter, use_container_width=True, hide_index=True)

with st.expander("How to read this dashboard"):
    st.markdown(
        """
        - **News**: quick plain-language updates from the latest housing data.
        - **Developments**: areas/programs where most listings are currently showing up.
        - **Stats**: headline numbers to understand pricing and availability at a glance.
        - **Starter shortlist**: top options based on affordability + accessibility score.
        """
    )
