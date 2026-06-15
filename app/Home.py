import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
import streamlit as st

from ai_housing_guide import render_ai_housing_guide
from buyer_guide import render_buyer_guide
from macro_dashboard import render_macro_dashboard
from places_risk import render_places_risk
from scoring import enrich_dataframe

# Google Drive imports
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

st.set_page_config(page_title="Kenya Affordable Housing Dashboard", layout="wide")

MEGA_PARQUET = Path("data/processed/listings_mega.parquet")

# Google Drive setup
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@st.cache_resource(show_spinner="Authenticating with Google Drive...")
def get_google_drive_credentials():
    creds = None
    token_path = Path("token.json")
    creds_path = Path("credentials.json")
    
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            st.warning("To connect to Google Drive, please upload your `credentials.json` file (download from Google Cloud Console)")
            uploaded_creds = st.file_uploader("Upload credentials.json", type="json", key="gdrive_creds")
            if uploaded_creds:
                with open(creds_path, "wb") as f:
                    f.write(uploaded_creds.getvalue())
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
    return creds


@st.cache_data(ttl=3600, show_spinner="Fetching latest AHP documents from Google Drive...")
def fetch_ahp_docs_from_drive(_creds):
    if not _creds:
        return []
    
    service = build("drive", "v3", credentials=_creds)
    results = (
        service.files()
        .list(
            q="mimeType contains 'document' or mimeType contains 'pdf' or mimeType contains 'text'",
            pageSize=20,
            fields="files(id, name, createdTime, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc"
        )
        .execute()
    )
    items = results.get("files", [])
    return items


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
def fetch_external_news(limit: int = 15) -> list[dict[str, str]]:
    feeds = [
        ("Google News", "https://news.google.com/rss/search?q=Kenya+AHP+affordable+housing"),
        ("Google News", "https://news.google.com/rss/search?q=Kenya+affordable+housing+programme"),
        ("Google News", "https://news.google.com/rss/search?q=Kenya+Boma+Yangu+housing"),
        ("Google News", "https://news.google.com/rss/search?q=Kenya+real+estate+market"),
        ("World Bank Kenya", "https://www.worldbank.org/en/country/kenya/news?output=rss"),
        ("UN-Habitat", "https://unhabitat.org/rss.xml"),
    ]
    items: list[dict] = []

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
                
                # Parse pubDate to datetime
                pub_datetime = None
                if pub:
                    try:
                        # Try common RSS date formats
                        for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
                            try:
                                pub_datetime = datetime.strptime(pub, fmt)
                                break
                            except ValueError:
                                continue
                    except:
                        pass
                
                # Add priority score for AHP-specific terms
                ahp_keywords = ["ahp", "affordable housing programme", "boma yangu", "big four", "housing fund"]
                priority = 2 if any(kw in title_l for kw in ahp_keywords) else 1
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": pub[:16] if pub else "Recent",
                        "pub_datetime": pub_datetime,
                        "priority": priority,
                    }
                )
        except (URLError, TimeoutError, ET.ParseError):
            continue

    # Sort: first by priority (AHP first), then by date (newest first)
    items_sorted = sorted(
        items, 
        key=lambda x: (-x["priority"], -x["pub_datetime"].timestamp() if x["pub_datetime"] else 0)
    )
    deduped: list[dict[str, str]] = []
    seen = set()
    for item in items_sorted:
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        # Only keep the fields we need for display
        deduped.append({
            "title": item["title"],
            "link": item["link"],
            "source": item["source"],
            "published": item["published"]
        })
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

home_tab, econ_tab, dev_tab, ai_tab, guide_tab, growth_tab = st.tabs(
    ["Home (AHP News)", "Economic Data", "Developments", "AI Housing Guide", "Buyer Guide", "Growth & Environment"]
)

with home_tab:
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
        st.markdown("### 📊 Latest AHP Communications & Context")
        
        # Google Drive Integration
        creds = get_google_drive_credentials()
        ahp_docs = fetch_ahp_docs_from_drive(creds)
        
        if ahp_docs:
            st.markdown("#### 📁 Latest AHP Documents from Google Drive")
            for doc in ahp_docs[:5]:  # Show top 5 most recent
                st.markdown(f"📄 [{doc['name']}]({doc['webViewLink']})")
                st.caption(f"Last modified: {doc['modifiedTime'][:10]}")
                st.divider()
        else:
            st.markdown("""
            **About Kenya's Affordable Housing Programme (AHP):**
            - Part of the government's Big Four Agenda
            - Aims to increase access to decent, affordable housing
            - Focus on partnerships with private sector developers
            - Targets low- and middle-income households
            """)
            
            st.divider()
            
            st.markdown("""
            **Key Themes to Watch:**
            - Policy updates & regulatory changes
            - New project announcements
            - Financing & mortgage availability
            - Construction progress & delivery timelines
            - Impact on urban development
            """)
        
        st.divider()
        
        st.info("Use the top tabs for deeper dives into economic data, housing stock, AI guides, and more!")

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

with ai_tab:
    ai_context = {
        "listing_count": len(df),
        "median_price_kes": int(df["price_kes"].median()) if not df.empty else None,
        "affordable_share_pct": round(((df["price_kes"] <= 5_000_000).mean() * 100), 1) if not df.empty else None,
    }
    render_ai_housing_guide(ai_context)

with guide_tab:
    render_buyer_guide()

with growth_tab:
    render_places_risk(df, df)
