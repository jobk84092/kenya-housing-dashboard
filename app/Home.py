import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import json
from pathlib import Path
from scoring import enrich_dataframe, filter_listings
from macro_dashboard import render_macro_dashboard
from buyer_guide import render_buyer_guide

st.set_page_config(page_title="Kenya Housing Dashboard", layout="wide")
st.title("Kenya Housing Finder + Portfolio Dashboard")
st.caption("Open-data style housing analytics for practical house hunting in Kenya.")

@st.cache_data
def load_data() -> pd.DataFrame:
    """Prefer public-source master file, then synthetic bulk, then enriched subset, then tiny sample."""
    public_path = Path("data/processed/listings_public_master.csv")
    bulk_path = Path("data/sample/listings_affordable_bulk.csv")
    enriched_path = Path("data/processed/listings_enriched.csv")
    sample_path = Path("data/sample/listings_sample.csv")
    if public_path.exists():
        data_path = public_path
    elif bulk_path.exists():
        data_path = bulk_path
    elif enriched_path.exists():
        data_path = enriched_path
    else:
        data_path = sample_path
    df = pd.read_csv(data_path)
    return enrich_dataframe(df)


def get_refresh_metadata() -> dict:
    metadata_path = Path("data/processed/refresh_metadata.json")
    if not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_worldbank_data() -> pd.DataFrame:
    wb_path = Path("data/processed/worldbank_indicators_ke.csv")
    if not wb_path.exists():
        return pd.DataFrame()
    wb = pd.read_csv(wb_path)
    if not {"indicator_code", "indicator_name", "year", "value"}.issubset(wb.columns):
        return pd.DataFrame()
    wb["year"] = pd.to_numeric(wb["year"], errors="coerce")
    wb["value"] = pd.to_numeric(wb["value"], errors="coerce")
    return wb.dropna(subset=["year", "value"]).copy()


def compute_insights(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return ["No listings match the current filters."]
    insights = []
    best = frame.sort_values("overall_score", ascending=False).iloc[0]
    insights.append(
        f"Top pick right now is {best['estate']} ({best['county']}) with overall score {best['overall_score']:.1f}."
    )
    affordable_share = (frame["affordability_score"] >= 60).mean() * 100
    insights.append(f"{affordable_share:.0f}% of filtered listings pass the affordability threshold (>=60).")
    high_access_share = (frame["accessibility_score"] >= 60).mean() * 100
    insights.append(f"{high_access_share:.0f}% of filtered listings have strong accessibility (>=60).")
    return insights


df = load_data()
wb_df = load_worldbank_data()
metadata = get_refresh_metadata()
_public_path = Path("data/processed/listings_public_master.csv")
_bulk_path = Path("data/sample/listings_affordable_bulk.csv")
if _public_path.exists():
    st.success(
        f"**{len(df):,} listings** loaded from public-source pipeline (`listings_public_master.csv`). "
        "Includes Boma Yangu project-level public data (expanded to unit-level analytical rows) and "
        "BuyRentKenya public homepage snippets."
    )
elif _bulk_path.exists() and len(df) >= 1000:
    st.success(
        f"**{len(df):,} listings** loaded from affordable-style bulk inventory (Boma Yangu/AHP, Tsavo corridor, coast, county programmes — synthetic, not an official Boma Yangu API export)."
    )
if metadata:
    st.info(
        "Data refreshed at: "
        + metadata.get("generated_at_utc", "unknown")
        + " | Sources: OpenStreetMap Nominatim + World Bank API"
    )
else:
    st.warning(
        "Listings file has no refresh metadata yet. For thousands of affordable-style units, run "
        "`python scripts/generate_affordable_inventory.py`. For live OSM counts on a subset, run "
        "`python scripts/refresh_data.py`."
    )

with st.sidebar:
    st.header("Your House-Hunt Filters")
    if "housing_program" in df.columns:
        programs = sorted(df["housing_program"].dropna().unique())
        housing_programs = st.multiselect(
            "Housing program / corridor",
            programs,
            default=programs,
            help="Program tag for filtering. Public-source pipeline includes Boma Yangu/AHP project-derived rows and BuyRentKenya public snippets.",
        )
    else:
        housing_programs = None
    counties = st.multiselect("County", sorted(df["county"].unique()), default=sorted(df["county"].unique()))
    prop_types = st.multiselect(
        "Property type",
        sorted(df["property_type"].unique()),
        default=sorted(df["property_type"].unique()),
    )
    min_price, max_price = int(df["price_kes"].min()), int(df["price_kes"].max())
    price_range = st.slider("Price range (KES)", min_price, max_price, (min_price, max_price), step=100000)
    max_bed = int(df["bedrooms"].max())
    bedrooms = st.slider("Minimum bedrooms", 1, max_bed, 2)
    min_overall_score = st.slider("Minimum overall score", 0, 100, 40)

filtered = filter_listings(
    df=df,
    counties=counties,
    property_types=prop_types,
    min_price=price_range[0],
    max_price=price_range[1],
    min_bedrooms=bedrooms,
    min_overall_score=min_overall_score,
    housing_programs=housing_programs,
)

house_tab, guide_tab, macro_tab, intel_tab = st.tabs(
    [
        "House-Hunt Dashboard",
        "Buyer & neighborhood guide",
        "Macro Dashboard",
        "Intelligence Output",
    ]
)

with house_tab:
    st.markdown(
        "Use this page to narrow your shortlist. Higher `overall_score` means a better balance of affordability and access."
    )
    if "housing_program" in df.columns:
        st.caption(
            f"Loaded **{len(df):,}** listings (affordable-style synthetic inventory). "
            "Boma Yangu does not publish a public bulk API; this dataset models project names, "
            "corridors, and price bands for analysis and demos."
        )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Listings found", f"{len(filtered)}")
    col2.metric("Median price", f"KES {int(filtered['price_kes'].median()):,}" if not filtered.empty else "N/A")
    col3.metric(
        "Avg affordability score",
        f"{filtered['affordability_score'].mean():.1f}" if not filtered.empty else "N/A",
    )
    col4.metric(
        "Avg accessibility score",
        f"{filtered['accessibility_score'].mean():.1f}" if not filtered.empty else "N/A",
    )

    if filtered.empty:
        st.warning("No listings match your filters. Try widening price range or lowering score threshold.")
    else:
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.subheader("Price Distribution")
            st.caption(
                "How to read: each bar shows how many listings fall in a price band. Taller bars mean more options at that budget level."
            )
            fig_hist = px.histogram(
                filtered,
                x="price_kes",
                nbins=10,
                color="property_type",
                barmode="overlay",
                labels={"price_kes": "Listing price (KES)", "count": "Number of listings"},
            )
            fig_hist.update_layout(
                xaxis_tickformat=",.0f",
                legend_title_text="Property type",
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        with chart_right:
            st.subheader("Top Areas by Score")
            st.caption(
                "How to read: areas on top rank better for your current filters and score settings. Longer bar = stronger recommendation."
            )
            top_areas = (
                filtered.groupby(["county", "estate"], as_index=False)["overall_score"]
                .mean()
                .sort_values("overall_score", ascending=False)
                .head(8)
            )
            fig_bar = px.bar(
                top_areas,
                x="overall_score",
                y="estate",
                color="county",
                orientation="h",
                text="overall_score",
                labels={"overall_score": "Overall score (0-100)", "estate": "Estate"},
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(
                yaxis={"categoryorder": "total ascending"},
                xaxis_range=[0, 100],
                margin=dict(l=10, r=10, t=40, b=10),
                legend_title_text="County",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Map Explorer")
        st.caption(
            "How to read: each dot is a listing. Bigger/greener dots are stronger overall options under your current filters."
        )
        view_state = pdk.ViewState(
            latitude=filtered["latitude"].mean(),
            longitude=filtered["longitude"].mean(),
            zoom=8.3,
            pitch=0,
        )
        map_df = filtered.copy()
        map_df["marker_radius"] = 800 + (map_df["overall_score"] * 35)
        map_df["green"] = (80 + map_df["overall_score"] * 1.5).clip(upper=220)
        map_df["red"] = (220 - map_df["overall_score"] * 1.7).clip(lower=30)
        prog_line = (
            "\nProgram: " + map_df["housing_program"].astype(str)
            if "housing_program" in map_df.columns
            else ""
        )
        map_df["tooltip"] = (
            "Estate: "
            + map_df["estate"].astype(str)
            + "\nCounty: "
            + map_df["county"].astype(str)
            + prog_line
            + "\nPrice: KES "
            + map_df["price_kes"].map(lambda x: f"{int(x):,}")
            + "\nOverall Score: "
            + map_df["overall_score"].astype(str)
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[longitude, latitude]",
            get_radius="marker_radius",
            get_fill_color="[red, green, 120, 170]",
            stroked=True,
            get_line_color=[20, 20, 20, 120],
            line_width_min_pixels=1,
            pickable=True,
        )
        st.pydeck_chart(
            pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=view_state,
                layers=[layer],
                tooltip={"text": "{tooltip}"},
            ),
            use_container_width=True,
        )

        st.subheader("Shortlist Table")
        shortlist_cols = [
            "listing_id",
            "county",
            "estate",
            "property_type",
            "bedrooms",
            "price_kes",
            "affordability_score",
            "accessibility_score",
            "overall_score",
        ]
        if "housing_program" in filtered.columns:
            shortlist_cols.insert(2, "housing_program")
        st.dataframe(
            filtered.sort_values("overall_score", ascending=False)[shortlist_cols],
            use_container_width=True,
        )

        csv_data = filtered.sort_values("overall_score", ascending=False).to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download filtered shortlist (CSV)",
            data=csv_data,
            file_name="kenya_housing_shortlist.csv",
            mime="text/csv",
        )

with guide_tab:
    render_buyer_guide()

with macro_tab:
    render_macro_dashboard(wb_df)

with intel_tab:
    st.subheader("Decision Intelligence")
    for bullet in compute_insights(filtered):
        st.write(f"- {bullet}")
    if not filtered.empty:
        st.markdown("**Top 3 recommendations based on current filters**")
        recommended = filtered.sort_values("overall_score", ascending=False).head(3)
        rec_cols = [
            "estate",
            "county",
            "property_type",
            "price_kes",
            "bedrooms",
            "affordability_score",
            "accessibility_score",
            "overall_score",
        ]
        if "housing_program" in recommended.columns:
            rec_cols.insert(2, "housing_program")
        st.dataframe(recommended[rec_cols], use_container_width=True)
        st.caption(
            "Recommendation logic: weighted score using affordability (65%) and accessibility (35%)."
        )
