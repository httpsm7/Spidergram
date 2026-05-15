"""config/settings.py — Central configuration for Spidergram v2."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Paths ──────────────────────────────────────────────────────────────
DATA_DIR       = BASE_DIR / "data"
DB_PATH        = DATA_DIR / "db" / "spidergram.db"
LOGS_DIR       = DATA_DIR / "logs"
MEDIA_DIR      = DATA_DIR / "media"
IMAGES_DIR     = MEDIA_DIR / "images"
AUDIO_DIR      = MEDIA_DIR / "audio"
VIDEO_DIR      = MEDIA_DIR / "video"
TEMP_DIR       = MEDIA_DIR / "temp"
QUEUE_DIR      = DATA_DIR / "queue"
AGENTS_CONFIG  = BASE_DIR / "config" / "agents.json"
MODELFILES_DIR = BASE_DIR / "modelfiles"

for d in [DATA_DIR, DB_PATH.parent, LOGS_DIR, IMAGES_DIR,
          AUDIO_DIR, VIDEO_DIR, TEMP_DIR, QUEUE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── AI Models ──────────────────────────────────────────────────────────
OLLAMA_HOST   = os.getenv("OLLAMA_HOST",  "http://127.0.0.1:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "gemma3")
GROK_API_KEY  = os.getenv("GROK_API_KEY", "")

# ── News ───────────────────────────────────────────────────────────────
NEWSAPI_KEY  = os.getenv("NEWSAPI_KEY",  "")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")

# ── Media ──────────────────────────────────────────────────────────────
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# ── Voice ──────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# ── Instagram ──────────────────────────────────────────────────────────
INSTAGRAM_APP_ID     = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
GRAPH_BASE           = "https://graph.facebook.com/v19.0"

# ── Telegram ───────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")

# ── CDN ────────────────────────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.getenv("CLOUDINARY_API_KEY",    "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

# ── Web Dashboard ──────────────────────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "spidergram-v2-secret")
DASHBOARD_PORT   = int(os.getenv("DASHBOARD_PORT", 7111))

# ── Security ───────────────────────────────────────────────────────────
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

# ── Video Settings ─────────────────────────────────────────────────────
VIDEO_WIDTH      = 1080
VIDEO_HEIGHT     = 1920   # 9:16 vertical (Reels)
VIDEO_FPS        = 30
VIDEO_DURATION_S = 60     # max seconds
HOOK_DURATION_S  = 2      # first 2s hook

# ── Content Pipeline ───────────────────────────────────────────────────
MAX_NEWS_PER_RUN    = 20
POSTS_PER_DAY       = 4
DEDUP_THRESHOLD     = 0.85   # semantic similarity threshold

# ── Retry ──────────────────────────────────────────────────────────────
MAX_RETRIES      = 3
RETRY_DELAY_S    = 5
