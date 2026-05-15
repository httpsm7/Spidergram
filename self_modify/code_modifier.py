"""
self_modify/code_modifier.py
──────────────────────────────
Apply code modifications requested by the user via CEO Brain.

Safety flow:
  1. Read current module
  2. Generate modified version (LLM)
  3. Validate syntax
  4. Write backup
  5. Apply change
  6. Test import
"""

import ast, shutil, importlib, sys
from pathlib import Path
from datetime import datetime
from utils import get_logger
from self_modify.code_reader import read_module, BASE_DIR

logger   = get_logger("self_modify.code_modifier")
BACKUP_DIR = BASE_DIR / "data" / "code_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def validate_syntax(code: str) -> tuple[bool, str]:
    """Check if code is valid Python. Returns (ok, error_message)."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, str(exc)


def backup_module(module_path: str) -> str:
    """Create timestamped backup before modifying. Returns backup path."""
    src    = BASE_DIR / module_path
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest   = BACKUP_DIR / f"{src.stem}_{ts}.py.bak"
    shutil.copy2(src, dest)
    logger.info(f"Backup created: {dest.name}")
    return str(dest)


def apply_modification(module_path: str, new_code: str) -> tuple[bool, str]:
    """
    Safely apply modified code to a module.
    Returns (success, message).
    """
    # Validate syntax first
    ok, err = validate_syntax(new_code)
    if not ok:
        return False, f"Syntax error: {err}"

    full_path = BASE_DIR / module_path
    backup    = backup_module(module_path)

    try:
        full_path.write_text(new_code)
        logger.info(f"Module updated: {module_path}")

        # Test that the module can be imported (basic smoke test)
        mod_name = module_path.replace("/", ".").replace(".py", "")
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        importlib.import_module(mod_name)

        return True, f"Module {module_path} updated successfully. Backup: {Path(backup).name}"
    except Exception as exc:
        # Restore backup on failure
        shutil.copy2(backup, full_path)
        logger.error(f"Modification failed, restored backup: {exc}")
        return False, f"Failed and restored: {exc}"


def rollback(module_path: str) -> tuple[bool, str]:
    """Restore the most recent backup of a module."""
    src   = BASE_DIR / module_path
    backs = sorted(BACKUP_DIR.glob(f"{src.stem}_*.py.bak"))
    if not backs:
        return False, "No backup found."
    latest = backs[-1]
    shutil.copy2(latest, src)
    logger.info(f"Rolled back {module_path} from {latest.name}")
    return True, f"Rolled back to {latest.name}"
