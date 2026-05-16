"""
pipeline/script_engine.py
──────────────────────────
Step 4: Generate narration script from a news item.
Primary: Ollama  |  Fallback: Grok API
"""

import json, re
from database.models import NewsItem, GeneratedScript, db
from integrations.grok import chat as grok_chat
from config.settings import OLLAMA_HOST, OLLAMA_MODEL
from utils import get_logger

import requests

logger = get_logger("pipeline.script_engine")


def _ollama_chat(messages: list[dict], model: str = OLLAMA_MODEL) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": 0.8}},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Ollama failed: {exc}")
        return ""


def _llm(messages: list[dict]) -> str:
    """Try Ollama first, fall back to Grok."""
    result = _ollama_chat(messages)
    if not result:
        logger.info("Falling back to Grok API…")
        result = grok_chat(messages)
    return result


SCRIPT_SCHEMA = """
Return ONLY valid JSON (no markdown) with these keys:
{
  "hook":     "<2-second attention hook — one punchy sentence>",
  "body":     "<full 45-55 second narration script, natural spoken language>",
  "caption":  "<Instagram caption 150-250 chars>",
  "hashtags": "<25 relevant hashtags as one string>",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}
"""


def generate_script(news_item: NewsItem, agent_config: dict) -> GeneratedScript | None:
    """
    Generate a full video script for one news item.
    Returns a persisted GeneratedScript or None on failure.
    """
    agent_id = agent_config.get("id", "unknown")
    prompt   = agent_config.get("prompt", "You are a news content creator.")

    messages = [
        {"role": "system", "content": prompt + "\n\n" + SCRIPT_SCHEMA},
        {"role": "user",   "content":
            f"News Title: {news_item.title}\n"
            f"Description: {news_item.description}\n"
            f"Source: {news_item.source}\n\n"
            "Generate the video script now."
        },
    ]

    raw  = _llm(messages)
    data = _parse_json(raw)

    if not data.get("body"):
        logger.error(f"Script generation failed for: {news_item.title[:60]}")
        return None

    with db:
        script = GeneratedScript.create(
            news     = news_item,
            agent_id = agent_id,
            hook     = data.get("hook", ""),
            body     = data.get("body", ""),
            caption  = data.get("caption", ""),
            hashtags = data.get("hashtags", ""),
        )

    logger.info(f"[{agent_id}] Script generated for: {news_item.title[:60]}")
    return script


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM output, stripping markdown fences if present."""
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("Could not parse script JSON — using empty defaults.")
    return {}
