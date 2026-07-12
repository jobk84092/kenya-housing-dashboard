import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_housing_guide import render_ai_housing_guide
from buyer_guide import render_buyer_guide
from macro_dashboard import render_macro_dashboard
from news_feed import get_news
from places_risk import render_places_risk
from scoring import enrich_dataframe

st.set_page_config(page_title="Kenya Affordable Housing Dashboard", layout="wide")

# Repo root — works whether Streamlit cwd is repo root or app/
ROOT = Path(__file__).resolve().parents[1]
MEGA_PARQUET = ROOT / "data" / "processed" / "listings_mega.parquet"
CLOUD_PARQUET = ROOT / "data" / "processed" / "listings_cloud.parquet"
USE_FULL_DATA = os.getenv("KENYA_HOUSING_FULL_DATA", "").lower() in ("1", "true", "yes")


@st.cache_resource
def load_data() -> pd.DataFrame:
    public_path = ROOT / "data" / "processed" / "listings_public_master.csv"
    bulk_path = ROOT / "data" / "sample" / "listings_affordable_bulk.csv"
    enriched_path = ROOT / "data" / "processed" / "listings_enriched.csv"
    sample_path = ROOT / "data" / "sample" / "listings_sample.csv"

    try:
        if MEGA_PARQUET.exists():
            return enrich_dataframe(pd.read_parquet(MEGA_PARQUET))
        if not USE_FULL_DATA and CLOUD_PARQUET.exists():
            return enrich_dataframe(pd.read_parquet(CLOUD_PARQUET))
        if public_path.exists():
            return enrich_dataframe(pd.read_csv(public_path))
        if bulk_path.exists():
            return enrich_dataframe(pd.read_csv(bulk_path))
        if enriched_path.exists():
            return enrich_dataframe(pd.read_csv(enriched_path))
        if sample_path.exists():
            return enrich_dataframe(pd.read_csv(sample_path))
    except Exception as exc:
        st.error(f"Could not load listings data: {exc}")
        return pd.DataFrame()

    st.warning("No listings CSV/parquet found under data/.")
    return pd.DataFrame()


def get_refresh_metadata() -> dict:
    metadata_path = ROOT / "data" / "processed" / "refresh_metadata.json"
    if not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_resource
def load_worldbank_data() -> pd.DataFrame:
    wb_path = ROOT / "data" / "processed" / "worldbank_indicators_ke.csv"
    if not wb_path.exists():
        return pd.DataFrame()
    wb = pd.read_csv(wb_path)
    if not {"indicator_code", "indicator_name", "year", "value"}.issubset(wb.columns):
        return pd.DataFrame()
    wb["year"] = pd.to_numeric(wb["year"], errors="coerce")
    wb["value"] = pd.to_numeric(wb["value"], errors="coerce")
    return wb.dropna(subset=["year", "value"]).copy()


def format_kes(value: float) -> str:
    return f"KES {int(value):,}"


def latest_indicator(wb: pd.DataFrame, indicator_code: str) -> tuple[float | None, int | None]:
    subset = wb[wb["indicator_code"] == indicator_code].sort_values("year")
    if subset.empty:
        return None, None
    row = subset.iloc[-1]
    return float(row["value"]), int(row["year"])


def build_developments(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["metro_node", "county"], as_index=False)
        .agg(
            listings=("listing_id", "count"),
            median_price=("price_kes", "median"),
        )
        .sort_values("listings", ascending=False)
        .head(10)
    )
    grouped["development"] = grouped["county"] + " (" + grouped["metro_node"] + ")"
    grouped = grouped[["development", "listings", "median_price"]]
    grouped["median_price"] = grouped["median_price"].map(format_kes)
    return grouped


def build_typology_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["typology"] = (
        frame["bedrooms"].fillna(0).astype(int).astype(str)
        + "BR "
        + frame["property_type"].astype(str).str.title()
    )
    node_order = ["Nairobi Metro", "Coast Metro", "Rift Valley Metro", "Lake Metro"]
    market = frame[frame["metro_node"].isin(node_order)].copy()
    if market.empty:
        return pd.DataFrame()
    top_typologies = market["typology"].value_counts().head(10).index
    market = market[market["typology"].isin(top_typologies)]
    typology_matrix = (
        market.groupby(["typology", "metro_node"], as_index=False)["price_kes"]
        .median()
        .pivot(index="typology", columns="metro_node", values="price_kes")
    )
    typology_matrix = typology_matrix.reindex(columns=node_order)
    return typology_matrix.apply(
        lambda col: col.map(lambda value: format_kes(value) if pd.notna(value) else "-")
    )


df = load_data()
metadata = get_refresh_metadata()
wb_df = load_worldbank_data()
metro_map = {
    "Nairobi": "Nairobi Metro",
    "Kiambu": "Nairobi Metro",
    "Machakos": "Nairobi Metro",
    "Kajiado": "Nairobi Metro",
    "Mombasa": "Coast Metro",
    "Kilifi": "Coast Metro",
    "Kwale": "Coast Metro",
    "Nakuru": "Rift Valley Metro",
    "Uasin Gishu": "Rift Valley Metro",
    "Kisumu": "Lake Metro",
}
if not df.empty and "county" in df.columns:
    df["metro_node"] = df["county"].map(metro_map).fillna("Other Nodes")
else:
    df = df.copy()
    df["metro_node"] = pd.Series(dtype="object")

st.title("Kenya Affordable Housing Dashboard")
st.caption(
    "Simple first view, with deeper economic and place-based pages available below."
)

# Only render the selected page (st.tabs runs ALL tab bodies every time and
# can exceed Streamlit Community Cloud's ~1GB memory limit).
PAGES = [
    "Home (AHP News)",
    "Economic Data",
    "Developments",
    "AI Housing Guide",
    "Buyer Guide",
    "Growth & Environment",
]
page = st.radio("Navigate", PAGES, horizontal=True, label_visibility="collapsed")

if page == "Home (AHP News)":
    external_news = get_news()
    st.subheader("🏠 Kenya Affordable Housing Programme (AHP) News & Analysis")

    news_col, analysis_col = st.columns([1.2, 1])

    with news_col:
        st.markdown("### 📰 Latest AHP & Housing News")
        if external_news:
            for item in external_news[:10]:
                st.markdown(f"📌 [{item['title']}]({item['link']})")
                st.caption(f"Source: {item['source']} | {item['published']}")
                st.divider()
        else:
            st.info("Could not fetch external feeds right now. Try again in a moment.")

    with analysis_col:
        st.markdown("### 📊 Kenya AHP: Latest Context & Developments")

        st.markdown("""
        **Kenya Kwanza Manifesto & AHP Commitments (2022-2027):**
        The Kenya Kwanza government prioritizes affordable housing as a key pillar of its economic agenda, with commitments to:
        - Deliver 200,000 affordable housing units annually
        - Expand access to mortgage financing (including through the Kenya Mortgage Refinance Company - KMRC)
        - Partner with county governments and private sector developers
        - Establish housing fund contributions via statutory deductions
        - Invest in infrastructure (roads, water, electricity) to support new housing projects
        - Empower local artisans and contractors in the construction sector
        - Promote green building and climate-resilient housing solutions
        """)

        st.divider()

        st.markdown("""
        **Key Recent Presidential & Government Announcements:**
        - **Affordable Housing Fund (AHF) Deductions:** The government rolled out statutory deductions for the AHP, with contributions from both employees and employers to fund affordable housing initiatives
        - **County Partnerships:** Collaboration with devolved units to identify land and implement housing projects in all 47 counties
        - **Boma Yangu Programme:** Expansion of the national affordable housing platform to streamline application and allocation processes
        - **Economic Stimulus:** Positioning the construction and housing sector as a key driver of job creation and economic growth
        - **Infrastructure First:** Prioritizing the provision of roads, water, electricity, and sewerage in areas earmarked for affordable housing
        """)

        st.divider()

        st.markdown("""
        **Key Themes to Watch:**
        - Policy updates & regulatory changes
        - New project announcements
        - Financing & mortgage availability
        - Construction progress & delivery timelines
        - Impact on urban development & county-level implementation
        """)

        st.divider()

        st.info("Use the top navigation for deeper dives into economic data, housing stock, AI guides, and more!")

elif page == "Economic Data":
    render_macro_dashboard(
        wb_df,
        listing_median_kes=float(df["price_kes"].median()) if not df.empty else None,
        listing_count=len(df),
    )

elif page == "Developments":
    st.subheader("Median home prices by typology across metro nodes")
    typology_matrix = build_typology_matrix(df)
    if typology_matrix.empty:
        st.info("No metro-node data available yet for typology comparison.")
    else:
        st.dataframe(typology_matrix, use_container_width=True)
    st.caption("Rows are common unit typologies; columns are major metro nodes.")

elif page == "AI Housing Guide":
    ai_context = {
        "listing_count": len(df),
        "median_price_kes": int(df["price_kes"].median()) if not df.empty else None,
        "affordable_share_pct": round(((df["price_kes"] <= 5_000_000).mean() * 100), 1) if not df.empty else None,
    }
    render_ai_housing_guide(ai_context)

elif page == "Buyer Guide":
    render_buyer_guide()

elif page == "Growth & Environment":
    render_places_risk(df, df)
