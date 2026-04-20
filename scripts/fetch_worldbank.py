from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

# Curated bundle: urbanisation, housing context, infrastructure proxies, economy.
# Some series may be sparse for Kenya; empty responses are skipped downstream.
DEFAULT_INDICATORS = [
    "SP.POP.TOTL",  # Population, total
    "SP.URB.TOTL.IN.ZS",  # Urban population (% of total)
    "EN.POP.DNST",  # Population density (people per sq km of land)
    "NY.GDP.PCAP.CD",  # GDP per capita (current US$)
    "NY.GDP.MKTP.KD.ZG",  # GDP growth (annual %)
    "FP.CPI.TOTL.ZG",  # Inflation, consumer prices (annual %)
    "SI.POV.GINI",  # Gini index
    "SI.POV.DDAY",  # Poverty headcount at $2.15/day (2017 PPP)
    "EG.ELC.ACCS.ZS",  # Access to electricity (% of population)
    "SH.H2O.BASW.ZS",  # Basic drinking water services (%)
    "SH.STA.BASS.ZS",  # Basic sanitation (%)
    "IT.NET.USER.ZS",  # Individuals using the Internet (%)
    "IT.CEL.SETS.P2",  # Mobile cellular subscriptions (per 100 people)
    "SE.SEC.ENRR",  # Secondary school enrollment (% gross)
    "SH.DYN.MORT",  # Under-5 mortality (per 1,000 live births)
    "NE.GDI.FTOT.ZS",  # Gross fixed capital formation (% of GDP) — investment proxy
    "IS.ROD.DNST.K2",  # Road density (km per km² of land area)
    "IS.AIR.PSGR",  # Air transport, passengers carried
    "SL.UEM.TOTL.ZS",  # Unemployment, total (% labour force)
    "NV.IND.TOTL.ZS",  # Industry, value added (% of GDP)
]


def fetch_worldbank_indicator(
    indicator: str = "SP.POP.TOTL",
    country: str = "KE",
    timeout_sec: int = 90,
    retries: int = 4,
) -> list[dict]:
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=20000"
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout_sec)
            response.raise_for_status()
            break
        except (requests.RequestException, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                raise last_error
            time.sleep(1.5 * attempt)
    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    rows = payload[1] or []
    normalized: list[dict] = []
    for row in rows:
        normalized.append(
            {
                "country": country,
                "indicator_code": indicator,
                "indicator_name": (row.get("indicator") or {}).get("value"),
                "year": row.get("date"),
                "value": row.get("value"),
            }
        )
    return normalized


def fetch_multiple(indicators: list[str], country: str) -> pd.DataFrame:
    frames = []
    for code in indicators:
        try:
            data = fetch_worldbank_indicator(indicator=code, country=country)
        except requests.RequestException:
            print(f"WARN: skipped indicator {code} after retries (network error).", flush=True)
            continue
        if data:
            frames.append(pd.DataFrame(data))
    if not frames:
        return pd.DataFrame(columns=["country", "indicator_code", "indicator_name", "year", "value"])
    full = pd.concat(frames, ignore_index=True)
    full["year"] = pd.to_numeric(full["year"], errors="coerce")
    full = full.sort_values(["indicator_code", "year"], ascending=[True, True]).reset_index(drop=True)
    return full


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch selected World Bank indicators for Kenya.")
    parser.add_argument(
        "--country",
        default="KE",
        help="ISO country code (default: KE).",
    )
    parser.add_argument(
        "--indicators",
        nargs="+",
        default=DEFAULT_INDICATORS,
        help="Indicator codes to fetch.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/worldbank_indicators_ke.csv",
        help="CSV output path.",
    )
    args = parser.parse_args()

    df = fetch_multiple(indicators=args.indicators, country=args.country)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} records to {output_path}")
    print(f"Indicators: {', '.join(sorted(df['indicator_code'].dropna().unique()))}")


if __name__ == "__main__":
    main()
