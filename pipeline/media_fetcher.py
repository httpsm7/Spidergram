"""
pipeline/media_fetcher.py
──────────────────────────
Step 5: Fetch and download images/videos from Pexels.
Tracks used media in DB to avoid reuse.
"""

from pathlib import Path
from database.models import UsedMedia, db
from integrations.pexels import (
    search_photos, search_videos,
    get_best_video_file, get_photo_url,
)
from utils import get_logger, download_file, unique_id
from config.settings import IMAGES_DIR, VIDEO_DIR

logger = get_logger("pipeline.media_fetcher")


def _is_used(pexels_id: str) -> bool:
    return UsedMedia.select().where(UsedMedia.pexels_id == str(pexels_id)).exists()


def _mark_used(pexels_id: str, media_type: str, url: str, local_path: str) -> None:
    with db:
        existing = UsedMedia.select().where(UsedMedia.pexels_id == str(pexels_id)).first()
        if existing:
            existing.used_count += 1
            existing.save()
        else:
            UsedMedia.create(
                pexels_id=str(pexels_id), media_type=media_type,
                url=url, local_path=local_path,
            )


def fetch_images(keywords: list[str], count: int = 5) -> list[str]:
    """
    Download `count` unique images matching keywords.
    Returns list of local file paths.
    """
    query   = " ".join(keywords[:3])
    photos  = search_photos(query, per_page=count + 5, orientation="portrait")
    paths   = []

    for photo in photos:
        pid = str(photo.get("id", ""))
        if _is_used(pid):
            continue
        url  = get_photo_url(photo, "large2x")
        dest = IMAGES_DIR / f"img_{pid}_{unique_id()}.jpg"
        if download_file(url, dest):
            _mark_used(pid, "photo", url, str(dest))
            paths.append(str(dest))
        if len(paths) >= count:
            break

    logger.info(f"Fetched {len(paths)} images for '{query}'")
    return paths


def fetch_background_video(keywords: list[str]) -> str:
    """
    Download one background video clip matching keywords.
    Returns local file path or ''.
    """
    query  = " ".join(keywords[:2])
    videos = search_videos(query, per_page=5, orientation="portrait")

    for video in videos:
        vid = str(video.get("id", ""))
        if _is_used(vid):
            continue
        url  = get_best_video_file(video, "hd")
        if not url:
            continue
        dest = VIDEO_DIR / f"bg_{vid}_{unique_id()}.mp4"
        if download_file(url, dest, timeout=60):
            _mark_used(vid, "video", url, str(dest))
            logger.info(f"Background video downloaded: {dest.name}")
            return str(dest)

    logger.warning(f"No background video found for '{query}'")
    return ""
