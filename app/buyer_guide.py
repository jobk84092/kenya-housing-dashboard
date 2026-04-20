"""Educational 'what to look for' content — not scraped; general Kenya housing literacy."""
from __future__ import annotations

import streamlit as st


def render_buyer_guide() -> None:
    st.header("What to look for — neighborhoods & demographics")
    st.caption(
        "Practical lenses for house-hunting in Kenya. This tab is **editorial guidance**, not scraped from portals. "
        "Always verify prices, titles, and developer credentials on official channels."
    )

    t1, t2, t3, t4 = st.tabs(
        ["Checklist", "By demographic", "Nairobi areas", "Other cities & closing"]
    )

    with t1:
        st.subheader("Property inspection checklist")
        st.markdown(
            """
            **Legal & money**
            - Title / leasehold length, charges, and any caveats (get a lawyer for land vs apartment share titles).
            - Stamp duty, legal fees, and lender valuation if you are mortgaging.
            - Service charge history (for apartments): ask for **last 3 years** of AGMs and audited accounts.

            **Structure & defects**
            - Damp on external walls and around windows; mould smell in closets.
            - Roof leaks (ceilings, water marks); flat roofs need regular waterproofing.
            - Plumbing pressure, hot water, drainage speed in sinks and showers.
            - Power: three-phase if you plan AC + oven + instant shower simultaneously.

            **Location reality (not brochure maps)**
            - Rush-hour commute sample to work/school (same day, same time you will actually travel).
            - Night security: lighting, access control, guards presence after 10pm.
            - Flood-prone sections: ask neighbours, check historical flooding news for that exact road.
            """
        )

    with t2:
        st.subheader("What tends to matter by life stage")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                """
                **Young professionals / first purchase**
                - Walkability to matatu stage or future BRT/MRT corridor.
                - Fibre-ready buildings; backup water tanks.
                - Smaller units OK if resale liquidity in that estate is proven.

                **Young families**
                - Pediatric clinics within 20–30 minutes; playgrounds and school waitlists.
                - Stairs vs lift if pram/elderly visitors; parking for 2 cars if both parents drive.

                **Remote / hybrid workers**
                - Power reliability; quiet rooms; spare room for office.
                - Coworking backup within 15 minutes for video-call days.
                """
            )
        with c2:
            st.markdown(
                """
                **Investors (buy-to-let)**
                - Gross yield vs void risk; tenant type in that block (students vs families).
                - Service charge as % of rent; special levies history.
                - Second-hand market: how fast similar units sell in that micro-location.

                **Diaspora buyers**
                - Trusted local PM + documented snagging process before final payment.
                - USD/KES timing for deposit tranches; bank transfer audit trail.
                - Avoid pressure to wire to personal accounts — developer escrow / lawyer accounts only.
                """
            )

    with t3:
        st.subheader("Nairobi — how neighbourhoods often feel")
        st.markdown(
            """
            | Area vibe | Often appeals to | Trade-offs to sanity-check |
            |-----------|------------------|------------------------------|
            | **Kilimani / Lavington / parts of Westlands** | Upside professionals, expats | Premium pricing; traffic at peak |
            | **Karen / Langata** | Space-seekers, families | Commute length; some pockets remote from stages |
            | **Syokimau / Mlolongo / Athi corridor** | Budget buyers, airport-linked work | Commute variability; choose blocks with water discipline |
            | **Ruiru / Kamulu / Eastern bypass belt** | Value land + house seekers | Title diligence; infrastructure rollout timing |
            | **Eastlands regeneration pockets** | Price-sensitive urban buyers | Block-level security variance; visit nights/weekends |

            **Reading the hype:** “Upcoming expressway” can help or hurt (noise, dust years). Map **actual** opened segments, not artist impressions.
            """
        )

    with t4:
        st.subheader("Beyond Nairobi")
        st.markdown(
            """
            - **Mombasa:** salt air maintenance, sea breeze vs humidity, seasonal tourism noise.
            - **Kisumu / lakeside:** lake proximity flood risk; agricultural smell days.
            - **Nakuru / Naivasha:** altitude climate; flower farm logistics employment nearby.
            - **Eldoret:** student town rhythm; land banking vs built stock.

            **Affordable programmes (Boma Yangu / AHP style):** eligibility, savings streaks, and allocation rounds change — treat dashboards as **planning tools**, not allocation guarantees.

            **On “scraping every portal”:** many listing sites forbid bulk scraping in their terms. Safer portfolio path: **official exports**, **partner APIs**, or **your own saved CSVs** in `data/raw/imports/` (this repo merges them when you run the public ingest script).
            """
        )
