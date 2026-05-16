"""
config/api_limits.py — API rate limits (free-tier defaults).
All thresholds in actual units (requests, characters, tokens, credits).
"""

# ── Thresholds ──────────────────────────────────────────────────────────
WARN_THRESHOLD  = 0.90   # Log warning + show red badge on dashboard
BLOCK_THRESHOLD = 1.00   # Stop making calls, wait for reset

# ── Per-API limits ──────────────────────────────────────────────────────
# daily / hourly / monthly: integer limit or None if no limit for that period
# unit  : what is being counted (requests / characters / tokens / credits)
# reset : how the limit resets  (daily / hourly / monthly / hourly_and_monthly)
# docs  : pricing page URL

API_LIMITS: dict = {
    "NEWSAPI_KEY": {
        "display_name": "NewsAPI",
        "daily":    100,
        "hourly":   None,
        "monthly":  None,
        "reset":    "daily",
        "unit":     "requests",
        "free_tier":"Developer: 100 req/day",
        "docs":     "https://newsapi.org/pricing",
    },
    "GNEWS_API_KEY": {
        "display_name": "GNews",
        "daily":    100,
        "hourly":   None,
        "monthly":  None,
        "reset":    "daily",
        "unit":     "requests",
        "free_tier":"Free: 100 req/day",
        "docs":     "https://gnews.io/pricing",
    },
    "PEXELS_API_KEY": {
        "display_name": "Pexels",
        "daily":    None,
        "hourly":   200,
        "monthly":  20000,
        "reset":    "hourly_and_monthly",
        "unit":     "requests",
        "free_tier":"200/hr · 20K/month",
        "docs":     "https://www.pexels.com/api/documentation/",
    },
    "ELEVENLABS_API_KEY": {
        "display_name": "ElevenLabs",
        "daily":    None,
        "hourly":   None,
        "monthly":  10000,
        "reset":    "monthly",
        "unit":     "characters",
        "free_tier":"Free: 10,000 chars/month",
        "docs":     "https://elevenlabs.io/pricing",
    },
    "GROK_API_KEY": {
        "display_name": "Grok (xAI)",
        "daily":    None,
        "hourly":   None,
        "monthly":  1_000_000,
        "reset":    "monthly",
        "unit":     "tokens",
        "free_tier":"Free: ~1M tokens/month",
        "docs":     "https://x.ai/api",
    },
    "CLOUDINARY_URL": {
        "display_name": "Cloudinary",
        "daily":    None,
        "hourly":   None,
        "monthly":  25,
        "reset":    "monthly",
        "unit":     "credits",
        "free_tier":"Free: 25 credits/month",
        "docs":     "https://cloudinary.com/pricing",
    },
}
