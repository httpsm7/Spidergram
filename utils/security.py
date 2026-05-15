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

logger = get_logger("utils.security")

KEYS_FILE = DATA_DIR / "db" / "keys.enc"


def _ensure_db_dir():
    """Ensure the keys directory exists."""
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _get_fernet() -> Fernet:
    """Return Fernet instance. Raises clear error if ENCRYPTION_KEY is missing."""
    key = ENCRYPTION_KEY

    if not key:
        logger.error("ENCRYPTION_KEY is missing in .env file!")
        raise RuntimeError(
            "ENCRYPTION_KEY not found in .env. "
            "Please generate one and add it to your .env file.\n"
            "Run: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    # Convert to bytes
    if isinstance(key, str):
        key_bytes = key.encode()
    else:
        key_bytes = key

    # Ensure it's valid 32-byte base64 for Fernet
    try:
        if len(key_bytes) != 44:  # Fernet key length after base64
            key_bytes = base64.urlsafe_b64encode(key_bytes[:32].ljust(32, b'\0'))
        return Fernet(key_bytes)
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        raise RuntimeError("Invalid ENCRYPTION_KEY in .env file.") from e


def load_keys() -> dict:
    """Load all stored API keys (decrypted)."""
    _ensure_db_dir()
    if not KEYS_FILE.exists():
        return {}

    try:
        f = _get_fernet()
        raw = KEYS_FILE.read_bytes()
        decrypted = f.decrypt(raw).decode()
        return json.loads(decrypted)
    except InvalidToken:
        logger.error("Invalid token — encryption key may have changed.")
        return {}
    except Exception as exc:
        logger.error(f"Could not decrypt keys file: {exc}")
        return {}


def save_keys(keys: dict) -> None:
    """Encrypt and persist API keys dict."""
    _ensure_db_dir()
    f = _get_fernet()
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
    """Retrieve a key: encrypted store first, then environment."""
    keys = load_keys()
    if name in keys:
        return keys[name]

    env_val = os.getenv(fallback_env or name, "")
    return env_val


def delete_key(name: str) -> bool:
    """Delete a key."""
    keys = load_keys()
    if name in keys:
        del keys[name]
        save_keys(keys)
        logger.info(f"API key deleted: {name}")
        return True
    return False


def list_keys() -> list[str]:
    """Return key names only."""
    return list(load_keys().keys())
