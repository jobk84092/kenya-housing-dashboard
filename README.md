# Kenya Housing Dashboard (v0.1)

An open-data Streamlit dashboard for exploring housing affordability and urban access in Kenya.
Designed for two goals:

- practical house-hunting decisions
- showcasing analytics, data storytelling, and product thinking on GitHub

## Features

- House-hunt filters (housing programme, county, property type, price range, bedrooms, minimum score)
- Large affordable-style inventory (default: `data/sample/listings_affordable_bulk.csv` when present — thousands of units tagged e.g. Boma Yangu/AHP, Tsavo corridor)
- Market overview KPIs (listing count, median price, average scores)
- Price distribution and top-estate ranking charts
- Interactive map explorer of listings
- Affordability score (income benchmark vs listing price)
- Accessibility score (nearby schools, hospitals, transit proxy)
- CSV export of filtered shortlist
- **Macro playground** (World Bank): urbanisation, density, electricity, water, sanitation, internet, mobile, roads, air passengers, GDP, inflation, Gini, poverty, investment, industry, unemployment — dual-axis, area, bar, heat map, scatter

## Data Sources

- **Public listings pipeline (preferred when present):** `data/processed/listings_public_master.csv` from `scripts/fetch_public_housing_data.py` (Boma Yangu public AHP tables + BuyRentKenya homepage snippets; see manifest for caveats).
- **Bulk synthetic listings:** `data/sample/listings_affordable_bulk.csv` — `scripts/generate_affordable_inventory.py` for large-scale demos.
- **Small sample:** `data/sample/listings_sample.csv` if bulk file is absent
- OpenStreetMap Nominatim Search API for live amenity counts (optional refresh on a capped subset)
- World Bank Indicators API for macro indicators

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app/Home.py
```

## Generate thousands of affordable-style listings

```bash
python scripts/generate_affordable_inventory.py --n 12000
```

Writes `data/sample/listings_affordable_bulk.csv`. The app loads this file automatically when it exists (before the tiny sample or API-enriched subset). Adjust `--n` or `--seed` as needed.

## Run Tests

```bash
pytest
```

## Build Supporting Data

```bash
python scripts/refresh_data.py
```

This refreshes:

- `data/processed/listings_enriched.csv` using real OpenStreetMap Nominatim API counts
- `data/processed/worldbank_indicators_ke.csv` using the World Bank API
- `data/processed/refresh_metadata.json` with source + timestamp + quality status

For faster local testing, you can run:

```bash
python scripts/refresh_data.py --max-listings 5
```

## Scoring Logic (MVP)

- `affordability_score` (0-100): derived from `price_kes` against county monthly income benchmark
- `accessibility_score` (0-100): weighted by nearby schools, hospitals, and transit stops
- `overall_score`: `0.65 * affordability + 0.35 * accessibility`

These formulas are intentionally simple and explainable for portfolio/demo use.

## Portfolio Upgrade Ideas

- Replace sample CSV with scraped/open listing feeds and cleaning pipeline
- Add travel-time-to-work calculation (e.g., CBDs via OSM routes)
- Add saved shortlist profiles ("budget-first", "family-first", "investment")
- Add tests and CI (GitHub Actions) for score calculations and data quality
- Deploy on Streamlit Community Cloud with project screenshots

## Engineering Quality

- Reusable scoring and filtering logic in `app/scoring.py`
- Unit tests in `tests/test_scoring.py`
- Data-quality validation in `scripts/data_quality.py`
- CI workflow in `.github/workflows/ci.yml` (runs tests on push and PR)
- Scheduled refresh workflow in `.github/workflows/data-refresh.yml` (weekly + manual trigger)

## Data Refresh Best Practices Implemented

- Real external APIs only: World Bank + OpenStreetMap Nominatim
- Reproducible processed artifacts in `data/processed/`
- Metadata with `generated_at_utc`, source URLs, row counts, and quality status
- Automated validation gate before writing outputs
- Scheduled refresh via GitHub Actions cron

## Ready-to-Publish Checklist

- [ ] Add 2-3 dashboard screenshots to a `docs/` folder
- [ ] Record a 60-90 second demo GIF/video
- [ ] Add a short "What I learned" section to this README
- [ ] Deploy to Streamlit Community Cloud and add live link
- [ ] Enable GitHub Actions in the remote repo so scheduled refresh runs automatically
- [ ] Create first GitHub release (`v0.2.0-mvp`)

## Structure

- app/ → Streamlit app
- scripts/ → data pipelines
- data/ → raw + processed data
