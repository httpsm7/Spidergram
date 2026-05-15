"""
pipeline/news_fetcher.py
─────────────────────────
Step 1-3: Fetch → Deduplicate → Filter trending
Failsafe: NewsAPI fails → GNews
"""

from datetime import datetime
from database.models import NewsItem, db
from integrations.newsapi import fetch_top_headlines, fetch_everything
from integrations.gnews   import fetch_top_news
from utils import get_logger, sha256

logger = get_logger("pipeline.news_fetcher")


def _save_article(article: dict, category: str, language: str) -> NewsItem | None:
    title = (article.get("title") or "").strip()
    if not title or title == "[Removed]":
        return None

    h = sha256(title)
    try:
        with db:
            item, created = NewsItem.get_or_create(
                hash=h,
                defaults={
                    "title":       title,
                    "description": article.get("description", "") or "",
                    "url":         article.get("url", ""),
                    "source":      article.get("source", {}).get("name", ""),
                    "category":    category,
                    "language":    language,
                    "published":   _parse_date(article.get("publishedAt")),
                }
            )
        return item if created else None
    except Exception as exc:
        logger.debug(f"DB save error: {exc}")
        return None


def _parse_date(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_for_agent(agent_config: dict) -> list[NewsItem]:
    """
    Fetch and store new articles for one agent.
    Returns list of newly inserted NewsItem objects.
    """
    keywords   = agent_config.get("news_keywords", [])
    categories = agent_config.get("news_categories", ["general"])
    language   = agent_config.get("language", "en")
    agent_id   = agent_config.get("id", "unknown")
    new_items  = []

    for category in categories:
        logger.info(f"[{agent_id}] Fetching: category={category} keywords={keywords[:2]}")

        # Primary: NewsAPI
        raw = fetch_top_headlines(keywords=keywords, category=category, language=language)

        # Fallback: GNews
        if not raw:
            logger.warning(f"[{agent_id}] NewsAPI empty — falling back to GNews")
            raw = fetch_top_news(keywords=keywords, language=language)

        for article in raw:
            item = _save_article(article, category, language)
            if item:
                new_items.append(item)

    logger.info(f"[{agent_id}] {len(new_items)} new articles saved.")
    return new_items


def get_unused_items(agent_id: str, category: str = None, limit: int = 5) -> list[NewsItem]:
    """Return up to `limit` unused NewsItems for the given category."""
    query = NewsItem.select().where(NewsItem.used == False)
    if category:
        query = query.where(NewsItem.category == category)
    return list(query.order_by(NewsItem.published.desc()).limit(limit))
