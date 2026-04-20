"""
Jobs vs Housing Stress Index — educational composite from public macro series.

Interprets: "Are people getting squeezed on shelter costs while labour markets weaken?"
Uses World Bank series only (no proprietary rent index required). Housing pressure is proxied
by headline CPI; optional in-app listing median gives a local price snapshot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


CODES = {
    "unemployment": "SL.UEM.TOTL.ZS",
    "inflation": "FP.CPI.TOTL.ZG",
    "gdp_pc_growth": "NY.GDP.PCAP.KD.ZG",
}


def _series(wb: pd.DataFrame, code: str) -> pd.DataFrame:
    s = wb[wb["indicator_code"] == code][["year", "value"]].dropna().sort_values("year")
    return s.rename(columns={"value": code})


def _minmax_stress(series: pd.Series, *, invert: bool = False) -> pd.Series:
    """Map to 0-100 where 100 = high stress (bad)."""
    lo, hi = series.min(), series.max()
    if hi <= lo or pd.isna(lo) or pd.isna(hi):
        return pd.Series(np.nan, index=series.index)
    x = (series - lo) / (hi - lo) * 100.0
    if invert:
        x = 100.0 - x
    return x.clip(0, 100)


def build_stress_table(wb: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    wb = wb.copy()
    wb["year"] = pd.to_numeric(wb["year"], errors="coerce")
    wb["value"] = pd.to_numeric(wb["value"], errors="coerce")
    wb = wb.dropna(subset=["year", "value"])

    u = _series(wb, CODES["unemployment"])
    inf = _series(wb, CODES["inflation"])
    g = _series(wb, CODES["gdp_pc_growth"])

    if u.empty or inf.empty:
        return pd.DataFrame(), []

    merged = u.merge(inf, on="year", how="inner")
    if not g.empty:
        merged = merged.merge(g, on="year", how="inner")
    merged = merged.sort_values("year")

    stress_cols: list[str] = []
    if CODES["unemployment"] in merged.columns:
        merged["stress_unemployment"] = _minmax_stress(merged[CODES["unemployment"]], invert=False)
        stress_cols.append("stress_unemployment")
    if CODES["inflation"] in merged.columns:
        merged["stress_inflation"] = _minmax_stress(merged[CODES["inflation"]], invert=False)
        stress_cols.append("stress_inflation")
    if CODES["gdp_pc_growth"] in merged.columns:
        merged["stress_jobs_income"] = _minmax_stress(merged[CODES["gdp_pc_growth"]], invert=True)
        stress_cols.append("stress_jobs_income")

    if len(stress_cols) < 2:
        return pd.DataFrame(), []
    merged["stress_index"] = merged[stress_cols].mean(axis=1, skipna=True)
    merged = merged.dropna(subset=["stress_index"])
    return merged, stress_cols


def render_jobs_housing_stress(
    wb_df: pd.DataFrame,
    listing_median_kes: float | None = None,
    listing_count: int | None = None,
) -> None:
    st.subheader("Jobs vs housing stress index")
    st.markdown(
        """
        **Question this answers:** *Are people more likely to feel “priced out” while the labour market weakens?*

        We combine **unemployment**, **headline inflation** (proxy for broad cost-of-living pressure including rent),
        and **GDP per capita growth** (weak growth raises stress — inverted in the index).
        Kenya does not expose a clean World Bank **housing-only CPI** code in this bundle; headline CPI is the standard macro substitute.
        """
    )
    st.caption(
        "Index is a **0–100 stress score** per year: higher = more pressure. Each ingredient is min–max scaled "
        "over the years shown, then averaged (GDP per capita growth is inverted so weak growth raises stress). "
        "This is a teaching device, not a CBK or KNBS official index."
    )
    if listing_median_kes is not None or listing_count is not None:
        m1, m2 = st.columns(2)
        m1.metric(
            "Median listing in app data (KES)",
            f"{int(listing_median_kes):,}" if listing_median_kes is not None else "—",
        )
        m2.metric(
            "Listings in current load",
            f"{listing_count:,}" if listing_count is not None else "—",
        )
        st.caption(
            "Snapshot only — not a national rent index. Good for comparing **your inventory** to macro years side by side."
        )

    tbl, stress_cols = build_stress_table(wb_df)
    if tbl.empty or "stress_index" not in tbl.columns:
        st.warning(
            "Not enough overlapping World Bank series to build the index. "
            "Run `python scripts/fetch_worldbank.py` after pulling the latest `fetch_worldbank.py` indicators."
        )
        return

    used = ", ".join(
        {
            "stress_unemployment": "unemployment",
            "stress_inflation": "inflation (CPI)",
            "stress_jobs_income": "GDP per capita growth (inverted)",
        }.get(c, c)
        for c in stress_cols
    )
    st.info(f"**Ingredients in your bundle:** {used}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tbl["year"],
            y=tbl["stress_index"],
            name="Composite stress",
            line=dict(width=3, color="#c0392b"),
            mode="lines+markers",
        )
    )
    for col, color, name in [
        ("stress_unemployment", "#2980b9", "Stress: unemployment"),
        ("stress_inflation", "#8e44ad", "Stress: inflation"),
        ("stress_jobs_income", "#16a085", "Stress: weak inc. growth"),
    ]:
        if col in tbl.columns:
            fig.add_trace(
                go.Scatter(
                    x=tbl["year"],
                    y=tbl[col],
                    name=name,
                    line=dict(width=1, dash="dot", color=color),
                    opacity=0.65,
                    mode="lines",
                )
            )
    fig.update_layout(
        title="Composite stress vs ingredients (0 = calm year in sample, 100 = max stress year in sample)",
        template="plotly_white",
        yaxis_title="Stress (0–100)",
        xaxis_title="Year",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**How to read a spike**")
        st.markdown(
            "- Stress rises when **unemployment** or **inflation** is unusually high *for Kenya in this window*.\n"
            "- It also rises when **GDP per capita growth** is unusually weak (inverted), proxying jobs/income momentum."
        )
    with c2:
        st.markdown("**What this is not**")
        st.markdown(
            "- Not a literal **median rent** series (national microdata needs KNBS / surveys or paid feeds).\n"
            "- Not mortgage-rate stress (add CBK policy rate series in a future upgrade).\n"
            "- Min–max scaling is **relative to the years plotted**, not an absolute global benchmark."
        )

    with st.expander("Underlying levels (same years)"):
        show_cols = ["year"] + [c for c in tbl.columns if c in CODES.values()]
        st.dataframe(tbl[show_cols].sort_values("year", ascending=False).head(25), use_container_width=True)
