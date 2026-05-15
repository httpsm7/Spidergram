"""integrations/newsapi.py — NewsAPI.org wrapper."""

import requests
from config.settings import NEWSAPI_KEY
from utils.logger import get_logger

logger = get_logger("integrations.newsapi")
BASE   = "https://newsapi.org/v2"


def fetch_top_headlines(keywords: list[str] = None, category: str = "general",
                        language: str = "en", page_size: int = 20) -> list[dict]:
    key = NEWSAPI_KEY
    if not key:
        logger.warning("NEWSAPI_KEY not set.")
        return []
    try:
        params = {"apiKey": key, "language": language, "pageSize": page_size}
        if keywords:
            params["q"] = " OR ".join(keywords)
        else:
            params["category"] = category

        r = requests.get(f"{BASE}/top-headlines", params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        logger.info(f"NewsAPI fetched {len(articles)} articles [category={category}]")
        return articles
    except Exception as exc:
        logger.error(f"NewsAPI error: {exc}")
        return []


def fetch_everything(query: str, language: str = "en",
                     sort_by: str = "publishedAt", page_size: int = 20) -> list[dict]:
    key = NEWSAPI_KEY
    if not key:
        return []
    try:
        r = requests.get(f"{BASE}/everything", params={
            "q": query, "language": language,
            "sortBy": sort_by, "pageSize": page_size, "apiKey": key,
        }, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        logger.info(f"NewsAPI (everything) fetched {len(articles)} for '{query}'")
        return articles
    except Exception as exc:
        logger.error(f"NewsAPI everything error: {exc}")
        return []
