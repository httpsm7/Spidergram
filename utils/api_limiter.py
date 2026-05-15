"""
utils/api_limiter.py — API rate-limit tracker for Spidergram v3.

Tracks per-API usage in  data/api_usage.json.
Features:
  • Warns at 90 % usage (logs + dashboard badge)
  • Blocks calls at 100 %
  • Auto-resets counters at daily / hourly / monthly boundaries
  • Returns (allowed, pct_used, reset_time_str) on every check
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

from config.api_limits import API_LIMITS, WARN_THRESHOLD, BLOCK_THRESHOLD
from utils.logger import get_logger

logger  = get_logger("utils.api_limiter")
_lock   = threading.Lock()

# Persist usage here (survives restarts)
_USAGE_FILE = Path(__file__).parent.parent / "data" / "api_usage.json"


def _load() -> dict:
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _USAGE_FILE.exists():
        try:
            with open(_USAGE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    with open(_USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _now() -> datetime:
    return datetime.utcnow()


def _reset_times() -> dict:
    now = _now()
    # Daily: next midnight UTC
    tomorrow = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    # Hourly: top of next hour
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    # Monthly: 1st of next month
    if now.month == 12:
        nm = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        nm = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "daily":   tomorrow,
        "hourly":  next_hour,
        "monthly": nm,
    }


def _ensure_key(data: dict, api_name: str) -> dict:
    if api_name not in data:
        data[api_name] = {
            "daily_used":       0,
            "hourly_used":      0,
            "monthly_used":     0,
            "last_daily_date":  _now().date().isoformat(),
            "last_hourly_str":  _now().strftime("%Y-%m-%dT%H"),
            "last_monthly_str": _now().strftime("%Y-%m"),
            "warned_daily":     False,
            "warned_hourly":    False,
            "warned_monthly":   False,
        }
    return data[api_name]


def _maybe_reset(entry: dict):
    now = _now()
    today = now.date().isoformat()
    this_hour = now.strftime("%Y-%m-%dT%H")
    this_month = now.strftime("%Y-%m")

    if entry["last_daily_date"] != today:
        entry["daily_used"] = 0
        entry["last_daily_date"] = today
        entry["warned_daily"] = False

    if entry["last_hourly_str"] != this_hour:
        entry["hourly_used"] = 0
        entry["last_hourly_str"] = this_hour
        entry["warned_hourly"] = False

    if entry["last_monthly_str"] != this_month:
        entry["monthly_used"] = 0
        entry["last_monthly_str"] = this_month
        entry["warned_monthly"] = False


# ── Public API ──────────────────────────────────────────────────────────

def check_and_increment(api_name: str, amount: int = 1) -> Tuple[bool, float, str]:
    """
    Record one (or `amount`) API call.

    Returns:
        (allowed: bool, pct_used: float 0.0–1.0, reset_time: str)

    allowed=False means the API is rate-limited — caller must wait.
    """
    if api_name not in API_LIMITS:
        return True, 0.0, "N/A"

    cfg = API_LIMITS[api_name]
    resets = _reset_times()

    with _lock:
        data = _load()
        entry = _ensure_key(data, api_name)
        _maybe_reset(entry)

        pct       = 0.0
        reset_str = "N/A"
        blocked   = False

        # ── Daily ─────────────────────────────────────────────────
        if cfg.get("daily"):
            entry["daily_used"] += amount
            p = entry["daily_used"] / cfg["daily"]
            if p > pct:
                pct = p
                reset_str = resets["daily"].strftime("Tomorrow %H:%M UTC")
            if p >= BLOCK_THRESHOLD:
                blocked = True
            if p >= WARN_THRESHOLD and not entry["warned_daily"]:
                logger.warning(
                    f"⚠️  {cfg['display_name']} daily usage at {p*100:.1f}% "
                    f"({entry['daily_used']}/{cfg['daily']}). Resets: {reset_str}"
                )
                entry["warned_daily"] = True

        # ── Hourly ────────────────────────────────────────────────
        if cfg.get("hourly"):
            entry["hourly_used"] += amount
            p = entry["hourly_used"] / cfg["hourly"]
            if p > pct:
                pct = p
                reset_str = resets["hourly"].strftime("Next hour %H:00 UTC")
            if p >= BLOCK_THRESHOLD:
                blocked = True
            if p >= WARN_THRESHOLD and not entry["warned_hourly"]:
                logger.warning(
                    f"⚠️  {cfg['display_name']} hourly usage at {p*100:.1f}% "
                    f"({entry['hourly_used']}/{cfg['hourly']}). Resets: {reset_str}"
                )
                entry["warned_hourly"] = True

        # ── Monthly ───────────────────────────────────────────────
        if cfg.get("monthly"):
            entry["monthly_used"] += amount
            p = entry["monthly_used"] / cfg["monthly"]
            if p > pct:
                pct = p
                reset_str = resets["monthly"].strftime("1 %b %Y")
            if p >= BLOCK_THRESHOLD:
                blocked = True
            if p >= WARN_THRESHOLD and not entry["warned_monthly"]:
                logger.warning(
                    f"⚠️  {cfg['display_name']} monthly usage at {p*100:.1f}% "
                    f"({entry['monthly_used']:,}/{cfg['monthly']:,} {cfg['unit']}). "
                    f"Resets: {reset_str}"
                )
                entry["warned_monthly"] = True

        if blocked:
            logger.error(
                f"🚫 {cfg['display_name']} RATE LIMITED. Resets: {reset_str}"
            )

        _save(data)
        return not blocked, min(pct, 1.0), reset_str


def get_all_status() -> dict:
    """
    Return full usage status for all tracked APIs (for dashboard display).

    Returns dict keyed by API env-var name, each value contains:
      display_name, used, total, unit, pct (0-100), status, reset_str, free_tier
    """
    resets = _reset_times()
    with _lock:
        data  = _load()
        out   = {}

        for api_name, cfg in API_LIMITS.items():
            entry = _ensure_key(data, api_name)
            _maybe_reset(entry)

            pct = 0.0
            used = 0
            total = 0
            reset_str = "N/A"

            if cfg.get("daily"):
                p = entry["daily_used"] / cfg["daily"]
                if p >= pct:
                    pct = p
                    reset_str = resets["daily"].strftime("Tomorrow %H:%M UTC")
                used  = entry["daily_used"]
                total = cfg["daily"]

            if cfg.get("hourly"):
                p = entry["hourly_used"] / cfg["hourly"]
                if p >= pct:
                    pct = p
                    reset_str = resets["hourly"].strftime("Next hr %H:00 UTC")
                if not total:
                    used  = entry["hourly_used"]
                    total = cfg["hourly"]

            if cfg.get("monthly"):
                p = entry["monthly_used"] / cfg["monthly"]
                if p >= pct:
                    pct = p
                    reset_str = resets["monthly"].strftime("1 %b %Y")
                if not total:
                    used  = entry["monthly_used"]
                    total = cfg["monthly"]

            status = "ok"
            if pct >= WARN_THRESHOLD:
                status = "warning"
            if pct >= BLOCK_THRESHOLD:
                status = "blocked"

            out[api_name] = {
                "display_name": cfg["display_name"],
                "used":         used,
                "total":        total,
                "unit":         cfg["unit"],
                "pct":          round(pct * 100, 1),
                "status":       status,
                "reset_str":    reset_str,
                "free_tier":    cfg.get("free_tier", "—"),
                "docs":         cfg.get("docs", "#"),
            }

        _save(data)
        return out


def api_allowed(api_name: str, amount: int = 1) -> bool:
    """Convenience wrapper — returns True if call is allowed."""
    allowed, _, _ = check_and_increment(api_name, amount)
    return allowed
