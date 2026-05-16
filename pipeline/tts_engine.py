"""
pipeline/tts_engine.py
───────────────────────
Step 6: Generate narration audio via ElevenLabs.
Retry logic built in. Falls back to pyttsx3 (offline) if ElevenLabs fails.
"""

from database.models import GeneratedScript
from integrations.elevenlabs import generate_speech
from utils import get_logger, retry, unique_id
from config.settings import AUDIO_DIR

logger = get_logger("pipeline.tts_engine")

VOICE_MAP = {
    "authoritative":  "21m00Tcm4TlvDq8ikWAM",   # Rachel
    "professional":   "AZnzlk1XvdvUeBnXmlld",    # Domi
    "analytical":     "EXAVITQu4vr4xnSDxMaL",    # Bella
    "energetic":      "ErXwobaYiN019PkySvjV",     # Antoni
    "conversational": "MF3mGyEYCl7XYWbV9V6O",    # Elli
}


def _pyttsx3_fallback(text: str) -> str:
    """Offline TTS fallback using pyttsx3."""
    try:
        import pyttsx3
        engine  = pyttsx3.init()
        dest    = str(AUDIO_DIR / f"tts_offline_{unique_id()}.wav")
        engine.save_to_file(text, dest)
        engine.runAndWait()
        logger.info(f"pyttsx3 fallback audio: {dest}")
        return dest
    except Exception as exc:
        logger.error(f"pyttsx3 fallback failed: {exc}")
        return ""


def generate_narration(script: GeneratedScript, voice_style: str = "professional") -> str:
    """
    Generate audio for the full script body.
    Returns local audio file path or ''.
    """
    narration_text = f"{script.hook} {script.body}"
    voice_id       = VOICE_MAP.get(voice_style, None)

    # Try ElevenLabs with retry
    try:
        path = retry(
            lambda: generate_speech(narration_text, voice_id=voice_id),
            attempts=3, delay=5,
        )
        if path:
            return path
    except Exception as exc:
        logger.warning(f"ElevenLabs retries exhausted: {exc}")

    # Fallback: offline pyttsx3
    logger.info("Using pyttsx3 offline TTS fallback.")
    return _pyttsx3_fallback(narration_text)
