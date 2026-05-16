"""integrations/grok.py — xAI Grok API fallback LLM."""

import requests
from config.settings import GROK_API_KEY
from utils.logger import get_logger

logger = get_logger("integrations.grok")
BASE   = "https://api.x.ai/v1"


def chat(messages: list[dict], model: str = "grok-beta",
         temperature: float = 0.8, max_tokens: int = 1500) -> str:
    """
    Send a chat completion request to Grok.
    Returns assistant reply or '' on failure.
    """
    key = GROK_API_KEY
    if not key:
        logger.warning("GROK_API_KEY not set.")
        return ""
    try:
        r = requests.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model":       model,
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error(f"Grok API error: {exc}")
        return ""
