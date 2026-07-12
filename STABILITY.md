# Stability guide — Kenya Housing Dashboard

## What we fixed

| Layer | Change |
|---|---|
| **Memory** | Top nav + sub-pages use `st.radio` (only one section renders) |
| **Cache** | Listings & World Bank data use `st.cache_resource` (shared across users) |
| **Data** | `listings_cloud.parquet` (~5k rows) for Cloud; full data on Contabo via `KENYA_HOUSING_FULL_DATA=1` |
| **News** | Offline `data/processed/ahp_news.json` — no RSS at boot; daily GitHub Action refresh |
| **Deps** | Pinned versions in `requirements.txt` |
| **Secrets** | Safe `_get_secret()` — missing keys no longer crash the app |
| **Hosting** | Contabo Docker deploy under `deploy/` |

## Run locally

```bash
pip install -r requirements.txt
python scripts/build_cloud_subset.py   # optional
python scripts/fetch_news_json.py      # optional
streamlit run app/Home.py
```

Full dataset locally:

```bash
KENYA_HOUSING_FULL_DATA=1 streamlit run app/Home.py
```

## Contabo (recommended production host)

```bash
# One-time from Mac
bash deploy/install_contabo.sh

# After code changes
bash deploy/deploy.sh
```

- App: `http://127.0.0.1:8502` on server (nginx → public domain)
- Path: `/home/deploy/kenya-housing-dashboard`
- Secrets: `~deploy/kenya-housing-dashboard/.streamlit/secrets.toml`
- Health: `deploy/health_check.sh` every 15 min (auto-restart)
- Docker prune: weekly (Agent Office cron, Sundays 03:15)

## Streamlit Community Cloud

- Main file: `app/Home.py`
- Python: **3.11**
- Secrets: Groq + OpenRouter keys in Cloud UI
- Uses `listings_cloud.parquet` by default (lighter)
- Reboot after each deploy

## Monitoring

- Logs: `docker logs kenya-housing-dashboard -f`
- Health log: `/home/deploy/housing-data/kenya-housing-health.log`
- Optional: point UptimeRobot at `https://your-domain/_stcore/health`
