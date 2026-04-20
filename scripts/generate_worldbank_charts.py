from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "processed" / "worldbank_indicators_ke.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "worldbank_charts"


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")


def generate_charts() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT_FILE}. Run scripts/refresh_data.py first."
        )

    df = pd.read_csv(INPUT_FILE)
    required_cols = {"indicator_code", "indicator_name", "year", "value"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in world bank data: {sorted(missing)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["year", "value"])

    indicators = (
        df[["indicator_code", "indicator_name"]]
        .drop_duplicates()
        .sort_values("indicator_code")
        .to_dict("records")
    )

    generated = 0
    for indicator in indicators:
        code = str(indicator["indicator_code"])
        name = str(indicator["indicator_name"])
        subset = df[df["indicator_code"] == code].sort_values("year")
        if subset.empty:
            continue

        fig = px.line(
            subset,
            x="year",
            y="value",
            markers=True,
            title=f"{name} ({code}) - Kenya",
            labels={"year": "Year", "value": "Value"},
        )
        fig.update_layout(template="plotly_white")

        filename = f"{slugify(code)}_{slugify(name)[:60]}.html"
        fig.write_html(str(OUTPUT_DIR / filename), include_plotlyjs="cdn")
        generated += 1

    print(f"Generated {generated} charts in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_charts()
