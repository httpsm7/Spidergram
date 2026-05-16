"""integrations/instagram.py — Instagram Graph API wrapper."""

import time
import requests
from config.settings import GRAPH_BASE
from utils.logger import get_logger

logger  = get_logger("integrations.instagram")
SESSION = requests.Session()


def publish_image(ig_user_id: str, access_token: str,
                  image_url: str, caption: str) -> str | None:
    """Two-step image publish. Returns media_id or None."""
    cid = _create_container(ig_user_id, access_token,
                            image_url=image_url, caption=caption)
    return _publish(ig_user_id, access_token, cid) if cid else None


def publish_reel(ig_user_id: str, access_token: str,
                 video_url: str, caption: str) -> str | None:
    """Two-step reel publish. Returns media_id or None."""
    cid = _create_container(ig_user_id, access_token,
                            video_url=video_url, caption=caption, media_type="REELS")
    if not cid:
        return None
    logger.info("Waiting 20s for reel processing…")
    time.sleep(20)
    return _publish(ig_user_id, access_token, cid)


def _create_container(ig_user_id, token, image_url="", video_url="",
                      caption="", media_type="IMAGE") -> str | None:
    payload = {"access_token": token, "caption": caption}
    if media_type == "REELS":
        payload.update({"video_url": video_url, "media_type": "REELS"})
    else:
        payload["image_url"] = image_url
    for attempt in range(3):
        try:
            r = SESSION.post(f"{GRAPH_BASE}/{ig_user_id}/media",
                             data=payload, timeout=30)
            r.raise_for_status()
            return r.json().get("id")
        except Exception as exc:
            time.sleep(2 ** attempt)
            logger.warning(f"Container create attempt {attempt+1}: {exc}")
    return None


def _publish(ig_user_id, token, creation_id) -> str | None:
    for attempt in range(3):
        try:
            r = SESSION.post(
                f"{GRAPH_BASE}/{ig_user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=30,
            )
            r.raise_for_status()
            media_id = r.json().get("id")
            logger.info(f"Published media_id={media_id}")
            return media_id
        except Exception as exc:
            time.sleep(2 ** attempt)
            logger.warning(f"Publish attempt {attempt+1}: {exc}")
    return None


def get_insights(media_id: str, token: str) -> dict:
    try:
        r = SESSION.get(
            f"{GRAPH_BASE}/{media_id}/insights",
            params={"metric": "likes,comments,saved,impressions,reach,plays",
                    "access_token": token},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        return {item["name"]: item["values"][0]["value"] for item in data}
    except Exception as exc:
        logger.debug(f"Insights error: {exc}")
        return {}


def get_account_info(ig_user_id: str, token: str) -> dict:
    try:
        r = SESSION.get(f"{GRAPH_BASE}/{ig_user_id}",
                        params={"fields": "username,followers_count,media_count",
                                "access_token": token}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning(f"Account info error: {exc}")
        return {}
