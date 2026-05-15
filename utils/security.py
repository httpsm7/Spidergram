"""
utils/security.py
──────────────────
Encrypted API key storage using Fernet symmetric encryption.
Keys are stored in data/db/keys.enc — never in plain text outside .env.
"""

import base64
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from config.settings import DATA_DIR, ENCRYPTION_KEY
from utils.logger import get_logger

logger   = get_logger("utils.security")
KEYS_FILE = DATA_DIR / "db" / "keys.enc"


def _get_fernet() -> Fernet:
    key = ENCRYPTION_KEY
    if not key:
        # Auto-generate and persist to .env on first run
        key = Fernet.generate_key().decode()
        logger.warning("No ENCRYPTION_KEY found — generated new key. Add to .env!")
        _write_env_key(key)
    key_bytes = key.encode() if isinstance(key, str) else key
    # Fernet requires 32-byte urlsafe base64
    if len(key_bytes) != 44:
        key_bytes = base64.urlsafe_b64encode(key_bytes[:32].ljust(32, b"0"))
    return Fernet(key_bytes)


def _write_env_key(key: str) -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        content = env_path.read_text()
        if "ENCRYPTION_KEY=" in content:
            lines = [
                f"ENCRYPTION_KEY={key}" if l.startswith("ENCRYPTION_KEY=") else l
                for l in content.splitlines()
            ]
            env_path.write_text("\n".join(lines))
        else:
            with open(env_path, "a") as f:
                f.write(f"\nENCRYPTION_KEY={key}\n")


def load_keys() -> dict:
    """Load all stored API keys (decrypted)."""
    if not KEYS_FILE.exists():
        return {}
    try:
        f   = _get_fernet()
        raw = KEYS_FILE.read_bytes()
        return json.loads(f.decrypt(raw).decode())
    except (InvalidToken, Exception) as exc:
        logger.error(f"Could not decrypt keys file: {exc}")
        return {}


def save_keys(keys: dict) -> None:
    """Encrypt and persist API keys dict."""
    f         = _get_fernet()
    encrypted = f.encrypt(json.dumps(keys).encode())
    KEYS_FILE.write_bytes(encrypted)
    logger.debug(f"Saved {len(keys)} API keys (encrypted).")


def set_key(name: str, value: str) -> None:
    """Add or update a single API key."""
    keys = load_keys()
    keys[name] = value
    save_keys(keys)
    logger.info(f"API key stored: {name}")


def get_key(name: str, fallback_env: str = "") -> str:
    """Retrieve a key: encrypted store first, then os.environ."""
    keys = load_keys()
    if name in keys:
        return keys[name]
    env_val = os.getenv(fallback_env or name, "")
    return env_val


def delete_key(name: str) -> bool:
    keys = load_keys()
    if name in keys:
        del keys[name]
        save_keys(keys)
        logger.info(f"API key deleted: {name}")
        return True
    return False


def list_keys() -> list[str]:
    """Return key names (not values) for display."""
    return list(load_keys().keys())
