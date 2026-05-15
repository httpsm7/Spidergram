"""
self_modify/code_reader.py
───────────────────────────
Read own source code so the CEO Brain can understand and modify modules.
"""

from pathlib import Path
from utils import get_logger

logger   = get_logger("self_modify.code_reader")
BASE_DIR = Path(__file__).parent.parent

READABLE_DIRS = ["core", "agents", "pipeline", "integrations", "database", "utils"]


def read_module(module_path: str) -> str:
    """Read source code of a specific module. e.g. 'pipeline/video_engine.py'"""
    full = BASE_DIR / module_path
    if not full.exists():
        raise FileNotFoundError(f"Module not found: {module_path}")
    return full.read_text()


def list_modules() -> list[str]:
    """Return relative paths of all .py files in readable dirs."""
    modules = []
    for d in READABLE_DIRS:
        for p in (BASE_DIR / d).rglob("*.py"):
            modules.append(str(p.relative_to(BASE_DIR)))
    return sorted(modules)


def get_module_summary() -> str:
    """Return a compact index of all modules for the CEO Brain."""
    lines = ["Available modules:"]
    for m in list_modules():
        lines.append(f"  • {m}")
    return "\n".join(lines)
