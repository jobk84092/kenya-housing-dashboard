#!/usr/bin/env python3
"""Fetch AHP news RSS feeds and write offline JSON for stable app boot."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from news_feed import fetch_news_from_feeds  # noqa: E402

OUT = ROOT / "data" / "processed" / "ahp_news.json"


def main() -> None:
    items = fetch_news_from_feeds(limit=15, timeout=8.0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(items)} items -> {OUT}")


if __name__ == "__main__":
    main()
