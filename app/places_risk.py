"""
County growth (census-based), environmental exposure hints, and inventory heat maps.

Reference tables live under data/reference/ and are intended for education and demos.
Production deployments should swap in licensed listing feeds and authoritative hazard GIS.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).resolve().parents[1]
REF = BASE / "data" / "reference"


def normalize_county_label(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    if s.lower().endswith(" county"):
        s = s[: -len(" county")].strip()
    aliases = {
        "Muranga": "Murang'a",
        "Tharaka Nithi": "Tharaka-Nithi",
        "Taita Taveta": "Taita-Taveta",
        "Taita–Taveta": "Taita-Taveta",
        "Elgeyo Marakwet": "Elgeyo-Marakwet",
        "Trans Nzoia": "Trans-Nzoia",
    }
    return aliases.get(s, s)


@lru_cache(maxsize=1)
def _load_census() -> pd.DataFrame:
    path = REF / "kenya_county_census_populations.csv"
    if not path.exists():
        return pd.DataFrame()
    d = pd.read_csv(path)
    d["county_key"] = d["county"].map(normalize_county_label)
    d["population_2009"] = pd.to_numeric(d["population_2009"], errors="coerce")
    d["population_2019"] = pd.to_numeric(d["population_2019"], errors="coerce")
    d = d.dropna(subset=["population_2009", "population_2019"])
    d = d[d["population_2009"] > 0]
    d["intercensal_cagr_pct"] = ((d["population_2019"] / d["population_2009"]) ** (1 / 10) - 1) * 100
    return d


@lru_cache(maxsize=1)
def _load_env() -> pd.DataFrame:
    path = REF / "kenya_county_environmental_exposure.csv"
    if not path.exists():
        return pd.DataFrame()
    d = pd.read_csv(path, usecols=lambda c: c.lower() != "disclaimer")
    d["county_key"] = d["county"].map(normalize_county_label)
    return d


def _inventory_by_county(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "county" not in frame.columns:
        return pd.DataFrame()
    g = frame.copy()
    g["_ck"] = g["county"].map(normalize_county_label)
    agg = g.groupby("_ck", as_index=False).agg(
        listing_count=("listing_id", "count"),
        median_price_kes=("price_kes", "median"),
        mean_score=("overall_score", "mean"),
    )
    agg = agg.rename(columns={"_ck": "county_key"})
    return agg


def render_places_risk(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    st.header("Places, growth & environmental context")
    st.markdown(
        "**Census growth** uses KNBS-era county totals mirrored on Wikipedia (2009 vs 2019). "
        "**Environmental scores** are coarse, editable priors — not a substitute for engineering studies, "
        "insurance underwriting, or NDMA bulletins. "
        "**Inventory heat** is derived only from listings currently loaded in this app."
    )
    st.warning(
        "**On “millions of real units with contacts”:** national-scale personal contact data belongs in "
        "licensed MLS/partnership feeds or seller-consented exports. This repo stays on public snippets, "
        "CSV imports you own, and synthetic bulk for load-testing — never mass scraping of private phones."
    )

    census = _load_census()
    env = _load_env()
    inv = _inventory_by_county(filtered if not filtered.empty else df)

    t1, t2, t3 = st.tabs(["County population growth", "Environmental exposure", "Inventory heat (this load)"])

    with t1:
        if census.empty:
            st.info("Missing `data/reference/kenya_county_census_populations.csv`.")
        else:
            st.subheader("Fastest-growing counties (intercensal CAGR, 2009→2019)")
            st.caption("Compound annual growth rate of enumerated population between Kenya’s 2009 and 2019 censuses.")
            top = census.nlargest(15, "intercensal_cagr_pct")
            fig = px.bar(
                top.sort_values("intercensal_cagr_pct"),
                x="intercensal_cagr_pct",
                y="county",
                orientation="h",
                hover_data=["population_2009", "population_2019"],
                labels={"intercensal_cagr_pct": "CAGR (% per year)", "county": "County"},
                title="Top 15 counties by population CAGR (approximate)",
            )
            fig.update_layout(template="plotly_white", yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Counties with declining or very slow growth (same window)")
            slow = census.nsmallest(8, "intercensal_cagr_pct")
            fig2 = px.bar(
                slow.sort_values("intercensal_cagr_pct", ascending=False),
                x="intercensal_cagr_pct",
                y="county",
                orientation="h",
                color="intercensal_cagr_pct",
                color_continuous_scale="Reds",
                labels={"intercensal_cagr_pct": "CAGR (% per year)", "county": "County"},
                title="Lowest CAGR — includes counties with security or boundary enumeration effects",
            )
            fig2.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    with t2:
        if env.empty:
            st.info("Missing `data/reference/kenya_county_environmental_exposure.csv`.")
        else:
            st.subheader("Counties to study harder for climate shocks (illustrative)")
            st.caption("Higher **shock_exposure_score** = more combined flood/drought pressure in this simplified rubric.")
            hi = env.nlargest(15, "shock_exposure_score").sort_values("shock_exposure_score")
            fig = px.bar(
                hi,
                x="shock_exposure_score",
                y="county",
                orientation="h",
                hover_data=["flood_risk", "drought_risk", "summary"],
                labels={"shock_exposure_score": "Exposure (1–5)", "county": "County"},
                title="Higher exposure — due diligence on drainage, insurance, and evacuation routes",
            )
            fig.update_layout(template="plotly_white", yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Relatively lower scores in this rubric (still do local checks)")
            lo = env.nsmallest(12, "shock_exposure_score").sort_values("shock_exposure_score", ascending=False)
            fig2 = px.bar(
                lo,
                x="shock_exposure_score",
                y="county",
                orientation="h",
                labels={"shock_exposure_score": "Exposure (1–5)", "county": "County"},
                title="Lower composite score in this demo table",
            )
            fig2.update_layout(template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)

    with t3:
        if inv.empty:
            st.info("No listings to aggregate.")
        else:
            st.subheader("Where your current filters concentrate inventory")
            if not census.empty:
                m = inv.merge(census[["county_key", "intercensal_cagr_pct"]], on="county_key", how="left")
                fig = px.scatter(
                    m,
                    x="intercensal_cagr_pct",
                    y="median_price_kes",
                    size="listing_count",
                    color="mean_score",
                    hover_name="county_key",
                    labels={
                        "intercensal_cagr_pct": "Population CAGR 09→19 (%)",
                        "median_price_kes": "Median listing price (KES)",
                        "listing_count": "Listings",
                        "mean_score": "Mean overall score",
                    },
                    title="County inventory vs census growth (where join matched)",
                )
                fig.update_layout(template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                topc = inv.nlargest(20, "listing_count").sort_values("listing_count")
                fig0 = px.bar(
                    topc,
                    x="listing_count",
                    y="county_key",
                    orientation="h",
                    hover_data=["median_price_kes", "mean_score"],
                    labels={"listing_count": "Listings", "county_key": "County"},
                    title="Top counties by listing count in current view",
                )
                fig0.update_layout(template="plotly_white", yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig0, use_container_width=True)

            base_sc = filtered if not filtered.empty else df
            if "sub_county" in df.columns and base_sc["sub_county"].astype(str).str.strip().str.len().gt(0).any():
                st.subheader("Sub-county / district heat (from your listing labels)")
                sc = base_sc.copy()
                sc["_sc"] = sc["sub_county"].astype(str).str.strip()
                sc = sc[sc["_sc"].str.len() > 0]
                if not sc.empty:
                    sg = (
                        sc.groupby(["county", "_sc"], as_index=False)
                        .agg(listing_count=("listing_id", "count"), median_price_kes=("price_kes", "median"))
                        .nlargest(25, "listing_count")
                    )
                    fig2 = px.bar(
                        sg.sort_values("listing_count"),
                        x="listing_count",
                        y="_sc",
                        color="county",
                        orientation="h",
                        hover_data=["median_price_kes"],
                        labels={"_sc": "Sub-county (as tagged)", "listing_count": "Listings"},
                    )
                    fig2.update_layout(template="plotly_white", height=520)
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.caption(
                    "Populate a **sub_county** column (imports or generator with `--sub-county-splits`) "
                    "to unlock sub-county concentration charts."
                )
