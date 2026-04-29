import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from buyer_guide import render_buyer_guide
from macro_dashboard import render_macro_dashboard
from places_risk import render_places_risk
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


def format_kes(value: float) -> str:
    return f"KES {int(value):,}"


@st.cache_data(ttl=3600)
def fetch_external_news(limit: int = 8) -> list[dict[str, str]]:
    feeds = [
        ("Google News", "https://news.google.com/rss/search?q=Kenya+affordable+housing"),
        ("Google News", "https://news.google.com/rss/search?q=Kenya+real+estate+market"),
        ("World Bank Kenya", "https://www.worldbank.org/en/country/kenya/news?output=rss"),
        ("UN-Habitat", "https://unhabitat.org/rss.xml"),
    ]
    items: list[dict[str, str]] = []

    for source, url in feeds:
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=7) as response:
                payload = response.read()
            root = ET.fromstring(payload)
            for node in root.findall(".//item"):
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                pub = (node.findtext("pubDate") or "").strip()
                if not title or not link:
                    continue
                title_l = title.lower()
                if not any(word in title_l for word in ["housing", "real estate", "mortgage", "property", "rent", "urban"]):
                    continue
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": pub[:16] if pub else "Recent",
                    }
                )
        except (URLError, TimeoutError, ET.ParseError):
            continue

    deduped: list[dict[str, str]] = []
    seen = set()
    for item in items:
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


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
df["metro_node"] = df["county"].map(metro_map).fillna("Other Nodes")
external_news = fetch_external_news()

st.title("Kenya Affordable Housing Dashboard")
st.caption(
    "Simple first view, with deeper economic and place-based pages available below."
)

home_tab, econ_tab, dev_tab, guide_tab, growth_tab = st.tabs(
    ["Home (Simple)", "Economic Data", "Developments", "Buyer Guide", "Growth & Environment"]
)

with home_tab:
    news_col, dev_col, stats_col = st.columns([1.2, 1.2, 1])

    with news_col:
        st.subheader("News & research updates")
        if external_news:
            for item in external_news[:6]:
                st.markdown(f"- [{item['title']}]({item['link']})")
                st.caption(f"{item['source']} | {item['published']}")
        else:
            st.info("Could not fetch external feeds right now. Try again in a moment.")

    with dev_col:
        st.subheader("Developments")
        developments = build_developments(df)
        st.dataframe(developments, use_container_width=True, hide_index=True)
        st.caption("Major metro nodes with most listings and their current median prices.")

    with stats_col:
        st.subheader("Stats (open data)")
        st.metric("Total listings", f"{len(df):,}")
        st.metric("Median price", format_kes(df["price_kes"].median()))
        affordable_share = (df["price_kes"] <= 5_000_000).mean() * 100
        st.metric("Homes <= KES 5M", f"{affordable_share:.0f}%")
        urban_share, urban_year = latest_indicator(wb_df, "SP.URB.TOTL.IN.ZS")
        if urban_share is not None and urban_year is not None:
            st.metric("Urban population", f"{urban_share:.1f}% ({urban_year})")
        inflation, inflation_year = latest_indicator(wb_df, "FP.CPI.TOTL.ZG")
        if inflation is not None and inflation_year is not None:
            st.metric("Inflation", f"{inflation:.1f}% ({inflation_year})")

    with st.expander("How to read this dashboard"):
        st.markdown(
            """
            - **News & research updates**: headlines from free public news/research feeds.
            - **Developments**: where listings are currently concentrated by metro node.
            - **Stats**: combines dashboard listings with open World Bank indicators.
            - Use top tabs to access deep analysis pages.
            """
        )

with econ_tab:
    render_macro_dashboard(
        wb_df,
        listing_median_kes=float(df["price_kes"].median()) if not df.empty else None,
        listing_count=len(df),
    )

with dev_tab:
    st.subheader("Median home prices by typology across metro nodes")
    typology_matrix = build_typology_matrix(df)
    if typology_matrix.empty:
        st.info("No metro-node data available yet for typology comparison.")
    else:
        st.dataframe(typology_matrix, use_container_width=True)
    st.caption("Rows are common unit typologies; columns are major metro nodes.")

with guide_tab:
    render_buyer_guide()

with growth_tab:
    render_places_risk(df, df)
