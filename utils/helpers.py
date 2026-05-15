"""utils/helpers.py — Shared utilities."""

import hashlib, json, shutil, time, uuid
from pathlib import Path
import requests
from utils.logger import get_logger

logger = get_logger("utils.helpers")


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def unique_id() -> str:
    return uuid.uuid4().hex[:12]


def download_file(url: str, dest: Path, timeout: int = 30) -> bool:
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        return True
    except Exception as exc:
        logger.warning(f"Download failed ({url}): {exc}")
        return False


def retry(fn, attempts: int = 3, delay: int = 5):
    """Call fn up to `attempts` times, returning result or raising last exception."""
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Attempt {i+1}/{attempts} failed: {exc}")
            time.sleep(delay * (i + 1))
    raise last_exc


def load_json(path: Path, default=None):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def upload_cloudinary(file_path: str) -> str:
    """Upload media to Cloudinary, return public URL or ''."""
    from config.settings import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        return ""
    try:
        import cloudinary, cloudinary.uploader
        cloudinary.config(cloud_name=CLOUDINARY_CLOUD_NAME,
                          api_key=CLOUDINARY_API_KEY,
                          api_secret=CLOUDINARY_API_SECRET)
        res = cloudinary.uploader.upload(file_path, resource_type="auto", folder="spidergram")
        return res.get("secure_url", "")
    except Exception as exc:
        logger.warning(f"Cloudinary upload failed: {exc}")
        return ""
