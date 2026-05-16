"""integrations/pexels.py — Pexels free image/video API."""

import requests
from config.settings import PEXELS_API_KEY
from utils.logger import get_logger

logger  = get_logger("integrations.pexels")
HEADERS = {"Authorization": PEXELS_API_KEY}


def search_photos(query: str, per_page: int = 5, orientation: str = "portrait") -> list[dict]:
    if not PEXELS_API_KEY:
        logger.warning("PEXELS_API_KEY not set.")
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers=HEADERS,
            params={"query": query, "per_page": per_page, "orientation": orientation},
            timeout=10,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        logger.debug(f"Pexels photos: {len(photos)} for '{query}'")
        return photos
    except Exception as exc:
        logger.error(f"Pexels photo search error: {exc}")
        return []


def search_videos(query: str, per_page: int = 3, orientation: str = "portrait") -> list[dict]:
    if not PEXELS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers=HEADERS,
            params={"query": query, "per_page": per_page, "orientation": orientation},
            timeout=10,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        logger.debug(f"Pexels videos: {len(videos)} for '{query}'")
        return videos
    except Exception as exc:
        logger.error(f"Pexels video search error: {exc}")
        return []


def get_best_video_file(video: dict, preferred_quality: str = "hd") -> str:
    """Return the URL of the best-quality video file."""
    files = video.get("video_files", [])
    for f in files:
        if f.get("quality") == preferred_quality:
            return f["link"]
    return files[0]["link"] if files else ""


def get_photo_url(photo: dict, size: str = "large2x") -> str:
    return photo.get("src", {}).get(size, "")
