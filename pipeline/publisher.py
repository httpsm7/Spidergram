"""
pipeline/publisher.py
──────────────────────
Step 10: Upload video to CDN and publish to Instagram.
Records result in PostLog database table.
"""

from datetime import datetime
from database.models import PostLog, db
from integrations.instagram import publish_reel
from utils import get_logger, upload_cloudinary

logger = get_logger("pipeline.publisher")


def publish(
    agent_config: dict,
    video_path:   str,
    caption:      str,
    hashtags:     str,
    news_title:   str = "",
) -> PostLog:
    """
    Upload video → CDN → Instagram Reel.
    Returns a PostLog record (check .status for success/failed).
    """
    agent_id     = agent_config.get("id", "unknown")
    ig_user_id   = agent_config.get("ig_user_id", "")
    access_token = agent_config.get("access_token", "")

    with db:
        log = PostLog.create(
            agent_id   = agent_id,
            ig_user_id = ig_user_id,
            video_path = video_path,
            caption    = caption,
            hashtags   = hashtags,
            news_title = news_title,
            status     = "pending",
        )

    if not ig_user_id or not access_token:
        _fail(log, "Instagram credentials not configured for this agent.")
        return log

    # 1. Upload to CDN
    logger.info(f"[{agent_id}] Uploading video to CDN…")
    public_url = upload_cloudinary(video_path)
    if not public_url:
        _fail(log, "CDN upload failed — check Cloudinary credentials.")
        return log

    # 2. Publish to Instagram
    full_caption = f"{caption}\n.\n.\n.\n{hashtags}"
    logger.info(f"[{agent_id}] Publishing to Instagram…")
    media_id = publish_reel(ig_user_id, access_token, public_url, full_caption)

    if media_id:
        with db:
            log.media_id  = media_id
            log.status    = "success"
            log.posted_at = datetime.now()
            log.save()
        logger.info(f"[{agent_id}] ✅ Published! media_id={media_id}")
    else:
        _fail(log, "Instagram publish_reel returned None.")

    return log


def _fail(log: PostLog, reason: str) -> None:
    with db:
        log.status = "failed"
        log.error  = reason
        log.save()
    logger.error(f"Publish failed [{log.agent_id}]: {reason}")
