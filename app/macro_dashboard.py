"""
Rich macro / development dashboard for Kenya using World Bank time series.
Educational copy + varied chart types (not only single-indicator lines).
"""
from __future__ import annotations

import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from jobs_housing_stress import render_jobs_housing_stress


def _wb_slice(df: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    if df.empty or "indicator_code" not in df.columns:
        return pd.DataFrame()
    return df[df["indicator_code"].isin(codes)].copy()


def _latest_by_indicator(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = df.dropna(subset=["value"]).sort_values(["indicator_code", "year"])
    return d.groupby("indicator_code", as_index=False).tail(1)


def _short_name(name: str, max_len: int = 42) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    text = re.sub(r"\s+", " ", name.strip())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def render_macro_dashboard(
    wb_df: pd.DataFrame,
    listing_median_kes: float | None = None,
    listing_count: int | None = None,
) -> None:
    st.header("Kenya macro playground")
    st.markdown(
        "This page connects **national development trends** to **why housing feels the way it does**: "
        "cities growing faster than supply, infrastructure catching up, prices and incomes moving at different speeds. "
        "Data: [World Bank Open Data](https://data.worldbank.org/country/kenya) (free, global definitions)."
    )

    if wb_df.empty:
        st.warning(
            "No World Bank CSV found. Run `python scripts/refresh_data.py` (or `python scripts/fetch_worldbank.py`) "
            "to download the expanded indicator bundle."
        )
        return

    wb = wb_df.copy()
    wb["year"] = pd.to_numeric(wb["year"], errors="coerce")
    wb["value"] = pd.to_numeric(wb["value"], errors="coerce")
    wb = wb.dropna(subset=["year", "value"])
    codes_present = sorted(wb["indicator_code"].dropna().unique())
    st.caption(f"Loaded **{len(codes_present)}** indicators · **{len(wb):,}** year-observations.")

    # --- Spark KPIs from latest available year per series ---
    latest = _latest_by_indicator(wb)
    def pick(code: str) -> tuple[float | None, int | None]:
        row = latest[latest["indicator_code"] == code]
        if row.empty:
            return None, None
        return float(row.iloc[0]["value"]), int(row.iloc[0]["year"])

    urban_val, urban_yr = pick("SP.URB.TOTL.IN.ZS")
    elec_val, elec_yr = pick("EG.ELC.ACCS.ZS")
    gdp_pc, gdp_yr = pick("NY.GDP.PCAP.CD")
    infl_val, infl_yr = pick("FP.CPI.TOTL.ZG")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Urban population (% of total)", f"{urban_val:.1f}%" if urban_val is not None else "—")
    c2.metric("Access to electricity (% of pop.)", f"{elec_val:.1f}%" if elec_val is not None else "—")
    c3.metric("GDP per capita (US$)", f"${gdp_pc:,.0f}" if gdp_pc is not None else "—")
    c4.metric("Inflation (annual %)", f"{infl_val:.1f}%" if infl_val is not None else "—")
    st.caption(
        f"Spark tiles use latest available year per series (e.g. urban {urban_yr or '—'}, electricity {elec_yr or '—'})."
    )

    with st.expander("Why this matters for housing (60-second read)", expanded=False):
        st.markdown(
            """
            - **Urbanisation** pulls people into cities → more competition for well-located homes and rentals.
            - **Electricity, water, internet** are proxies for how liveable new neighbourhoods become — and what you pay for in service charges.
            - **GDP per capita vs inequality (Gini)** hints whether growth is broad-based — that shapes who can afford a deposit.
            - **Investment (% of GDP)** is a coarse proxy for how much the economy is building *stuff* (including infrastructure that unlocks new suburbs).
            - **Road density** (when available) is imperfect but fun: more paved connectivity often supports sprawl and commuter belts (think Thika Road effects).
            """
        )

    tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs(
        [
            "Urban & population",
            "Infrastructure & connectivity",
            "Economy & prices",
            "Explorer & heat map",
            "Jobs vs housing stress",
        ]
    )

    with tab_a:
        st.subheader("Urbanisation and crowding")
        st.caption("Urban share and population density rise together when cities absorb migration faster than new housing stock.")

        u1 = _wb_slice(wb, ["SP.URB.TOTL.IN.ZS", "EN.POP.DNST"])
        if not u1.empty:
            urban = u1[u1["indicator_code"] == "SP.URB.TOTL.IN.ZS"].sort_values("year")
            dens = u1[u1["indicator_code"] == "EN.POP.DNST"].sort_values("year")
            if not urban.empty and not dens.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                name_u = urban["indicator_name"].iloc[0]
                name_d = dens["indicator_name"].iloc[0]
                fig.add_trace(
                    go.Scatter(
                        x=urban["year"],
                        y=urban["value"],
                        name=_short_name(str(name_u)),
                        line=dict(width=3),
                        mode="lines+markers",
                    ),
                    secondary_y=False,
                )
                fig.add_trace(
                    go.Scatter(
                        x=dens["year"],
                        y=dens["value"],
                        name=_short_name(str(name_d)),
                        line=dict(dash="dot", width=2),
                        mode="lines+markers",
                    ),
                    secondary_y=True,
                )
                fig.update_layout(
                    title="Urban population (left) vs population density (right)",
                    template="plotly_white",
                    hovermode="x unified",
                    legend_orientation="h",
                    legend_yanchor="bottom",
                    legend_y=-0.25,
                )
                fig.update_yaxes(title_text="Urban % of population", secondary_y=False)
                fig.update_yaxes(title_text="People per km²", secondary_y=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                single = urban if not urban.empty else dens
                fig = px.line(single, x="year", y="value", markers=True, title="Urbanisation / density (single series available)")
                fig.update_layout(template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

        pop = _wb_slice(wb, ["SP.POP.TOTL"])
        if not pop.empty:
            p = pop.sort_values("year")
            fig2 = px.area(
                p,
                x="year",
                y="value",
                title="Total population — stacked area feels like 'pressure rising'",
                labels={"value": "Population", "year": "Year"},
            )
            fig2.update_traces(line_color="#1f77b4", fillcolor="rgba(31,119,180,0.25)")
            fig2.update_layout(template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)

    with tab_b:
        st.subheader("Basics that make a neighbourhood viable")
        st.caption("These series do not measure 'good roads near your listing' — they show national progress that supports (or lags) new towns.")

        basics = _wb_slice(wb, ["EG.ELC.ACCS.ZS", "SH.H2O.BASW.ZS", "SH.STA.BASS.ZS", "IT.NET.USER.ZS"])
        if not basics.empty:
            fig = px.line(
                basics,
                x="year",
                y="value",
                color="indicator_name",
                markers=True,
                title="Electricity, water, sanitation, internet — long runs",
            )
            fig.update_layout(template="plotly_white", legend_title_text="Indicator", yaxis_title="% of population (where applicable)")
            st.plotly_chart(fig, use_container_width=True)

        road = _wb_slice(wb, ["IS.ROD.DNST.K2"])
        if not road.empty:
            r = road.sort_values("year")
            fig_r = px.bar(
                r,
                x="year",
                y="value",
                title="Road density (km per km² of land) — infra backbone proxy",
                labels={"value": "Road density", "year": "Year"},
            )
            fig_r.update_layout(template="plotly_white")
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.info("Road density series not available in your current CSV — re-fetch indicators after upgrading `fetch_worldbank.py`.")

        air = _wb_slice(wb, ["IS.AIR.PSGR"])
        if not air.empty:
            a = air.sort_values("year")
            fig_a = px.scatter(
                a,
                x="year",
                y="value",
                size="value",
                title="Air passengers (if reported) — connectivity and tourism pulse",
                labels={"value": "Air passengers (carrier/period definition varies)"},
            )
            fig_a.update_layout(template="plotly_white")
            st.plotly_chart(fig_a, use_container_width=True)

    with tab_c:
        st.subheader("Macro pressure on wallets and construction costs")
        econ = _wb_slice(wb, ["NY.GDP.PCAP.CD", "NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SI.POV.GINI", "NE.GDI.FTOT.ZG"])
        if not econ.empty:
            fig = px.line(
                econ,
                x="year",
                y="value",
                color="indicator_name",
                markers=True,
                title="GDP per capita, growth, inflation, inequality, investment — same era, different stories",
            )
            fig.update_layout(template="plotly_white", legend_title_text="Indicator", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

        gini = _wb_slice(wb, ["SI.POV.GINI"])
        if not gini.empty:
            g = gini.sort_values("year")
            fig_g = px.area(
                g,
                x="year",
                y="value",
                title="Gini index — inequality lens (higher = more unequal)",
                labels={"value": "Gini"},
            )
            fig_g.update_traces(line_color="#d62728", fillcolor="rgba(214,39,40,0.2)")
            fig_g.update_layout(template="plotly_white")
            st.plotly_chart(fig_g, use_container_width=True)

        unemp = _wb_slice(wb, ["SL.UEM.TOTL.ZS"])
        if not unemp.empty:
            u = unemp.sort_values("year")
            fig_u = px.line(u, x="year", y="value", markers=True, title="Unemployment (% of labour force)")
            fig_u.update_layout(template="plotly_white")
            st.plotly_chart(fig_u, use_container_width=True)

    with tab_d:
        st.subheader("Compare everything at once")
        st.caption("Heat map: each row is an indicator, each column is a year. Colour = z-score within that indicator (so different units can sit on one chart).")

        pivot = wb.pivot_table(index="indicator_code", columns="year", values="value", aggfunc="last")
        pivot = pivot.loc[:, pivot.columns >= (pivot.columns.max() - 45)] if len(pivot.columns) else pivot
        pivot = pivot.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if pivot.shape[0] >= 2 and pivot.shape[1] >= 3:
            z = pivot.sub(pivot.mean(axis=1), axis=0).div(pivot.std(axis=1).replace(0, float("nan")), axis=0)
            z = z.dropna(axis=0, how="all").fillna(0)
            name_map = wb.drop_duplicates("indicator_code").set_index("indicator_code")["indicator_name"].to_dict()
            z.index = [f"{i}: {_short_name(str(name_map.get(i, i)), 36)}" for i in z.index]
            fig_h = px.imshow(
                z,
                aspect="auto",
                title="Relative strength vs each indicator's own history (last ~45 years)",
                color_continuous_scale="RdBu_r",
                zmin=-2,
                zmax=2,
            )
            fig_h.update_layout(template="plotly_white", xaxis_title="Year", yaxis_title="Indicator")
            st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.info("Not enough overlapping years for a heat map yet — fetch more indicators or widen the year window.")

        st.subheader("Pick-your-own adventure")
        opts = (
            wb[["indicator_code", "indicator_name"]]
            .drop_duplicates()
            .sort_values("indicator_name")
            .apply(lambda r: f"{r['indicator_name']} ({r['indicator_code']})", axis=1)
            .tolist()
        )
        pick = st.selectbox("Deep dive one indicator", options=opts, key="macro_pick_one")
        code = pick.split("(")[-1].replace(")", "").strip()
        ser = wb[wb["indicator_code"] == code].sort_values("year")
        if not ser.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig_l = px.line(ser, x="year", y="value", markers=True, title="Line view")
                fig_l.update_layout(template="plotly_white")
                st.plotly_chart(fig_l, use_container_width=True)
            with c2:
                fig_b = px.bar(ser, x="year", y="value", title="Bar view — emphasise decade-to-decade jumps")
                fig_b.update_layout(template="plotly_white")
                st.plotly_chart(fig_b, use_container_width=True)

        st.subheader("Cross-indicator scatter (same year)")
        st.caption("Pick two indicators; each dot is one year. Fun way to spot 'urbanisation vs GDP per capita' style relationships.")
        colx, coly = st.columns(2)
        code_opts = sorted(wb["indicator_code"].unique())
        ix = min(5, len(code_opts) - 1)
        iy = min(2, len(code_opts) - 1)
        if len(code_opts) > 1 and iy == ix:
            iy = (ix + 1) % len(code_opts)
        with colx:
            xc = st.selectbox("X axis code", code_opts, index=ix, key="mx")
        with coly:
            yc = st.selectbox("Y axis code", code_opts, index=iy, key="my")
        wide = wb.pivot_table(index="year", columns="indicator_code", values="value", aggfunc="last")
        if xc == yc:
            st.warning("Pick **two different** indicators for X and Y. Same code twice creates duplicate column names and breaks the chart.")
        elif xc in wide.columns and yc in wide.columns:
            scat = wide[[xc, yc]].dropna().reset_index()
            # Unique column names for Plotly/Narwhals (even if codes were ever duplicated upstream)
            scat = scat.rename(columns={xc: "x_value", yc: "y_value"})
            nm = wb.drop_duplicates("indicator_code").set_index("indicator_code")["indicator_name"].to_dict()
            lx = _short_name(str(nm.get(xc, xc)), 30)
            ly = _short_name(str(nm.get(yc, yc)), 30)
            fig_s = px.scatter(
                scat,
                x="x_value",
                y="y_value",
                text="year",
                title=f"{lx} vs {ly}",
                labels={"x_value": lx, "y_value": ly},
            )
            fig_s.update_traces(textposition="top center", marker=dict(size=10))
            fig_s.update_layout(template="plotly_white")
            st.plotly_chart(fig_s, use_container_width=True)

    with tab_e:
        render_jobs_housing_stress(
            wb,
            listing_median_kes=listing_median_kes,
            listing_count=listing_count,
        )

    st.divider()
    st.markdown(
        "**Next upgrades (tell me if you want them):** overlay Kenya mortgage/CBK series, "
        "county-level splits (where WB has them), or satellite night-lights as an informal urban growth proxy."
    )
