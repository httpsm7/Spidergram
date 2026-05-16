"""
utils/security.py
─────────────────
Encrypted API key storage using Fernet symmetric encryption.
Keys stored in data/db/keys.enc — never in plain text.

Key storage priority:
  1. ENCRYPTION_KEY env variable (from .env)
  2. data/encryption.key file (auto-created, writable fallback)
  3. Auto-generate new key + print to console for user to copy
"""

import base64
import json
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from utils.logger import get_logger

logger    = get_logger("utils.security")
BASE_DIR  = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data"
KEYS_FILE = DATA_DIR / "db" / "keys.enc"
KEY_FILE  = DATA_DIR / "encryption.key"   # fallback when .env is not writable


def _load_or_create_key() -> str:
    """
    Load encryption key from (in order):
      1. ENCRYPTION_KEY environment variable
      2. data/encryption.key file
      3. Generate new key, save to data/encryption.key
    Never crashes with PermissionError.
    """
    # 1. Check environment
    key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if key:
        return key

    # 2. Check data/encryption.key file
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            os.environ["ENCRYPTION_KEY"] = key   # cache for this session
            return key

    # 3. Generate new key
    key = Fernet.generate_key().decode()
    logger.warning("=" * 60)
    logger.warning("NEW ENCRYPTION KEY GENERATED")
    logger.warning(f"  Key: {key}")
    logger.warning(f"  Saved to: {KEY_FILE}")
    logger.warning("  To persist: add  ENCRYPTION_KEY=%s  to your .env" % key)
    logger.warning("=" * 60)

    # Save to writable fallback file
    try:
        KEY_FILE.write_text(key)
        logger.info(f"Encryption key saved to {KEY_FILE}")
    except Exception as e:
        logger.error(f"Could not save key file: {e}")
        logger.warning("Key is only in memory — will regenerate on restart!")

    # Try to append to .env (best-effort, ignore PermissionError)
    _try_write_env_key(key)
    os.environ["ENCRYPTION_KEY"] = key
    return key


def _try_write_env_key(key: str) -> None:
    """Try to write ENCRYPTION_KEY to .env — silently skip on any error."""
    env_path = BASE_DIR / ".env"
    try:
        if env_path.exists():
            content = env_path.read_text()
            if "ENCRYPTION_KEY=" in content:
                # Already has a key entry — update it
                lines = [
                    f"ENCRYPTION_KEY={key}" if ln.startswith("ENCRYPTION_KEY=") else ln
                    for ln in content.splitlines()
                ]
                env_path.write_text("\n".join(lines) + "\n")
            else:
                with open(env_path, "a") as f:
                    f.write(f"\nENCRYPTION_KEY={key}\n")
            logger.info("ENCRYPTION_KEY written to .env")
    except PermissionError:
        logger.warning(
            f".env is not writable (PermissionError). "
            f"Key saved to {KEY_FILE} instead. "
            f"Run: chmod 600 .env   OR   echo 'ENCRYPTION_KEY={key}' >> .env"
        )
    except Exception as e:
        logger.warning(f"Could not write to .env: {e}")


def _get_fernet() -> Fernet:
    key = _load_or_create_key()
    key_bytes = key.encode() if isinstance(key, str) else key
    # Fernet needs exactly 32 bytes urlsafe-base64-encoded (44 chars)
    try:
        return Fernet(key_bytes)
    except Exception:
        # If the key is malformed, pad/trim it
        raw = key_bytes[:32].ljust(32, b"0")
        return Fernet(base64.urlsafe_b64encode(raw))


# ── Public API ──────────────────────────────────────────────────────────

def load_keys() -> dict:
    """Load all stored API keys (decrypted). Returns {} on any error."""
    if not KEYS_FILE.exists():
        return {}
    try:
        f   = _get_fernet()
        raw = KEYS_FILE.read_bytes()
        return json.loads(f.decrypt(raw).decode())
    except InvalidToken:
        logger.error(
            "Could not decrypt keys.enc — wrong ENCRYPTION_KEY? "
            f"Delete {KEYS_FILE} to reset (you will need to re-enter API keys)."
        )
        return {}
    except Exception as exc:
        logger.error(f"load_keys error: {exc}")
        return {}


def save_keys(keys: dict) -> None:
    """Encrypt and save API keys dict."""
    try:
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        f         = _get_fernet()
        encrypted = f.encrypt(json.dumps(keys).encode())
        KEYS_FILE.write_bytes(encrypted)
        logger.debug(f"Saved {len(keys)} API keys (encrypted).")
    except Exception as exc:
        logger.error(f"save_keys error: {exc}")


def set_key(name: str, value: str) -> None:
    """Add or update one API key."""
    keys = load_keys()
    keys[name] = value
    save_keys(keys)
    logger.info(f"API key stored: {name}")


def get_key(name: str, fallback_env: str = "") -> str:
    """Get key from encrypted store first, then os.environ."""
    keys = load_keys()
    if name in keys:
        return keys[name]
    return os.environ.get(fallback_env or name, "")


def delete_key(name: str) -> bool:
    keys = load_keys()
    if name in keys:
        del keys[name]
        save_keys(keys)
        logger.info(f"API key deleted: {name}")
        return True
    return False


def list_keys() -> list:
    return list(load_keys().keys())
