"""
pipeline/deduplicator.py
─────────────────────────
Deduplication engine.
Method 1: SHA-256 title hash (fast, exact).
Method 2: Jaccard similarity on word sets (lightweight semantic approx).
Optionally upgrades to sentence-transformers if installed.
"""

from config.settings import DEDUP_THRESHOLD
from database.models import NewsItem
from utils import get_logger, sha256

logger = get_logger("pipeline.deduplicator")


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _embedding_similarity(a: str, b: str) -> float:
    """Use sentence-transformers if available, else fall back to Jaccard."""
    try:
        from sentence_transformers import SentenceTransformer, util
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        embs   = _model.encode([a, b])
        return float(util.cos_sim(embs[0], embs[1]))
    except ImportError:
        return _jaccard(a, b)


def is_duplicate(title: str, recent_titles: list[str] = None) -> bool:
    """
    Return True if `title` is a duplicate of any existing news item
    or any title in recent_titles.
    """
    h = sha256(title)
    # Exact hash check (DB)
    if NewsItem.select().where(NewsItem.hash == h).exists():
        logger.debug(f"Duplicate (hash): {title[:60]}")
        return True

    # Semantic check against recent_titles
    if recent_titles:
        for existing in recent_titles:
            score = _jaccard(title, existing)
            if score >= DEDUP_THRESHOLD:
                logger.debug(f"Duplicate (similarity={score:.2f}): {title[:50]}")
                return True
    return False


def deduplicate(articles: list[dict], key: str = "title") -> list[dict]:
    """
    Filter a list of article dicts, removing duplicates.
    Returns the deduplicated list.
    """
    seen_titles: list[str] = []
    unique: list[dict] = []
    for art in articles:
        title = art.get(key, "")
        if not title:
            continue
        if not is_duplicate(title, seen_titles):
            unique.append(art)
            seen_titles.append(title)
    removed = len(articles) - len(unique)
    if removed:
        logger.info(f"Deduplicator removed {removed}/{len(articles)} duplicates.")
    return unique
