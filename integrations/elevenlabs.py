"""integrations/elevenlabs.py — ElevenLabs text-to-speech."""

import requests
from pathlib import Path
from config.settings import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, AUDIO_DIR
from utils.logger import get_logger
from utils.helpers import unique_id

logger  = get_logger("integrations.elevenlabs")
BASE    = "https://api.elevenlabs.io/v1"


def generate_speech(text: str, voice_id: str = None,
                    stability: float = 0.5, similarity: float = 0.75) -> str:
    """
    Generate MP3 audio from text.
    Returns local file path or '' on failure.
    """
    key = ELEVENLABS_API_KEY
    if not key:
        logger.warning("ELEVENLABS_API_KEY not set — skipping TTS.")
        return ""

    vid = voice_id or ELEVENLABS_VOICE_ID
    try:
        r = requests.post(
            f"{BASE}/text-to-speech/{vid}",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={
                "text":          text,
                "model_id":      "eleven_multilingual_v2",
                "voice_settings": {"stability": stability, "similarity_boost": similarity},
            },
            timeout=60,
        )
        r.raise_for_status()
        dest = AUDIO_DIR / f"tts_{unique_id()}.mp3"
        dest.write_bytes(r.content)
        logger.info(f"TTS audio saved: {dest.name}")
        return str(dest)
    except Exception as exc:
        logger.error(f"ElevenLabs TTS error: {exc}")
        return ""


def list_voices() -> list[dict]:
    """Return available voices for the account."""
    key = ELEVENLABS_API_KEY
    if not key:
        return []
    try:
        r = requests.get(f"{BASE}/voices",
                         headers={"xi-api-key": key}, timeout=10)
        r.raise_for_status()
        return r.json().get("voices", [])
    except Exception as exc:
        logger.error(f"ElevenLabs list_voices error: {exc}")
        return []
