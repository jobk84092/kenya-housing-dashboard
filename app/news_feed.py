"""AHP news: offline JSON cache with live RSS fallback."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
NEWS_JSON = ROOT / "data" / "processed" / "ahp_news.json"

FEEDS = [
    ("Google News", "https://news.google.com/rss/search?q=Kenya+AHP+affordable+housing"),
    ("Google News", "https://news.google.com/rss/search?q=Kenya+affordable+housing+programme"),
    ("Google News", "https://news.google.com/rss/search?q=Kenya+Boma+Yangu+housing"),
    ("Google News", "https://news.google.com/rss/search?q=Kenya+real+estate+market"),
    ("World Bank Kenya", "https://www.worldbank.org/en/country/kenya/news?output=rss"),
    ("UN-Habitat", "https://unhabitat.org/rss.xml"),
]


def _parse_pub_date(pub: str) -> datetime | None:
    if not pub:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(pub, fmt)
        except ValueError:
            continue
    return None


def fetch_news_from_feeds(limit: int = 15, timeout: float = 5.0) -> list[dict[str, str]]:
    items: list[dict] = []
    for source, url in FEEDS:
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
            root = ET.fromstring(payload)
            for node in root.findall(".//item"):
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                pub = (node.findtext("pubDate") or "").strip()
                if not title or not link:
                    continue
                title_l = title.lower()
                if not any(
                    word in title_l
                    for word in ["housing", "real estate", "mortgage", "property", "rent", "urban"]
                ):
                    continue
                pub_datetime = _parse_pub_date(pub)
                ahp_keywords = [
                    "ahp",
                    "affordable housing programme",
                    "boma yangu",
                    "big four",
                    "housing fund",
                ]
                priority = 2 if any(kw in title_l for kw in ahp_keywords) else 1
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": pub[:16] if pub else "Recent",
                        "pub_datetime": pub_datetime,
                        "priority": priority,
                    }
                )
        except (URLError, TimeoutError, ET.ParseError, OSError):
            continue

    items_sorted = sorted(
        items,
        key=lambda x: (-x["priority"], -(x["pub_datetime"].timestamp() if x["pub_datetime"] else 0)),
    )
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items_sorted:
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "title": item["title"],
                "link": item["link"],
                "source": item["source"],
                "published": item["published"],
            }
        )
        if len(deduped) >= limit:
            break
    return deduped


def load_cached_news(path: Path = NEWS_JSON) -> list[dict[str, str]] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if isinstance(items, list) and items:
            return items
    except (json.JSONDecodeError, OSError):
        pass
    return None


@st.cache_data(ttl=3600)
def get_news(limit: int = 15) -> list[dict[str, str]]:
    cached = load_cached_news()
    if cached:
        return cached[:limit]
    return fetch_news_from_feeds(limit=limit)
