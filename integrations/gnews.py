"""integrations/gnews.py — GNews API fallback when NewsAPI fails."""

import requests
from config.settings import GNEWS_API_KEY
from utils.logger import get_logger

logger = get_logger("integrations.gnews")
BASE   = "https://gnews.io/api/v4"


def fetch_top_news(keywords: list[str] = None, topic: str = "world",
                   language: str = "en", max_results: int = 10) -> list[dict]:
    key = GNEWS_API_KEY
    if not key:
        logger.warning("GNEWS_API_KEY not set.")
        return []
    try:
        params = {"apikey": key, "lang": language, "max": max_results}
        if keywords:
            params["q"] = " ".join(keywords)
            endpoint = f"{BASE}/search"
        else:
            params["topic"] = topic
            endpoint = f"{BASE}/top-headlines"

        r = requests.get(endpoint, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        # Normalise to same shape as NewsAPI
        normalised = [
            {
                "title":       a.get("title", ""),
                "description": a.get("description", ""),
                "url":         a.get("url", ""),
                "publishedAt": a.get("publishedAt", ""),
                "source":      {"name": a.get("source", {}).get("name", "GNews")},
            }
            for a in articles
        ]
        logger.info(f"GNews fetched {len(normalised)} articles")
        return normalised
    except Exception as exc:
        logger.error(f"GNews error: {exc}")
        return []
