# Streamlit Cloud fix checklist

Live URL: https://kenya-housing-dashboard-plgu9ohb9wbgrvcb4fgkjv.streamlit.app/  
GitHub: https://github.com/jobk84092/kenya-housing-dashboard

## What’s wrong

1. **Cloud app shows “Oh no. Error running app”** — runtime crash on Streamlit Community Cloud (confirmed repeatedly).
2. **AI secrets bug** — after `secrets.toml` was removed from git (`2a6eead`), Cloud must hold `GROQ_API_KEY` in the app Secrets UI. The old code crashed with `StreamlitSecretNotFoundError` when secrets were missing (fixed in repo).
3. **Heavy unused deps** — `geopandas`, `folium`, `pydeck` were in `requirements.txt` but never imported; they often break/slow Cloud installs. Removed from requirements.
4. **Path robustness** — `Home.py` now resolves data via repo root (`Path(__file__).parents[1]`), not cwd.

## What you must do in Streamlit login (cannot be done from here)

1. Open https://share.streamlit.io/ and sign in with the GitHub account that owns `jobk84092/kenya-housing-dashboard`.
2. Open the **kenya-housing-dashboard** app → **Manage app** (bottom-right) → **Logs**.
   - Copy the red traceback — that is the definitive Cloud error.
3. **Settings → General**
   - **Main file path** must be: `app/Home.py`
   - Python version: **3.11** (matches CI)
4. **Settings → Secrets** — paste exactly:

```toml
GROQ_API_KEY = "your_real_key_from_https://console.groq.com/keys"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

5. **Reboot** the app (Manage app → Reboot).
6. If still failing: **Settings → Delete app** and redeploy from GitHub with main file `app/Home.py`.

## After code push

Push the local fixes, then in Streamlit Cloud click **Reboot** (or wait for auto-redeploy from `main`).

## Local verify

```bash
cd ~/Projects/kenya-housing-dashboard
pip install -r requirements.txt
streamlit run app/Home.py
```
