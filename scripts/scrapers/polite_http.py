"""Polite HTTP helpers: User-Agent, delay, optional robots.txt check."""
from __future__ import annotations

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

DEFAULT_UA = "kenya-housing-dashboard/0.4 (+https://github.com/jobk84092/kenya-housing-dashboard; research)"


def fetch_text(url: str, timeout: int = 45) -> str:
    r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout)
    r.raise_for_status()
    return r.text


def robots_can_fetch(url: str, user_agent: str = DEFAULT_UA) -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"
    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots unavailable, be conservative: still allow only same-origin GET we already use in prod discussion
        return True


def polite_get(url: str, delay_sec: float = 0.0) -> str:
    if delay_sec > 0:
        time.sleep(delay_sec)
    if not robots_can_fetch(url):
        raise PermissionError(f"robots.txt disallows fetch: {url}")
    return fetch_text(url)
