"""
main.py  —  Spidergram v3 Entry Point
─────────────────────────────────────
Usage:
  python main.py                   Run pipeline once (all agents)
  python main.py --scheduled       Start scheduler (blocking)
  python main.py --dashboard       Start Flask dashboard only
  python main.py --both            Scheduler + dashboard (recommended)
  python main.py --chat            Interactive CEO Brain terminal chat
  python main.py --dry-run         Full pipeline, no actual IG post
  python main.py --agent <id>      Run one specific agent
  python main.py --install-models  Register Modelfiles with Ollama
  python main.py --report          Generate nightly report
  python main.py --help            Show this help
"""

import argparse
import sys
import threading
from pathlib import Path

# ── Bootstrap sys.path first (MUST be before any project imports) ─────
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Also add parent in case running from subdir
parent = str(BASE_DIR.parent)
if parent not in sys.path:
    sys.path.insert(1, parent)

# ── Verify critical packages ──────────────────────────────────────────
def _check_deps():
    missing = []
    required = ['flask', 'peewee', 'cryptography', 'dotenv', 'requests']
    aliases  = {'dotenv': 'python_dotenv'}
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(aliases.get(pkg, pkg))
    if missing:
        print(f"[ERROR] Missing packages: {', '.join(missing)}")
        print(f"  Fix: pip install {' '.join(missing)} --break-system-packages")
        sys.exit(1)

_check_deps()

from database import init_db
from agents import load_all_agents, get_agent
from utils.logger import get_logger

logger = get_logger("main")


def _bootstrap():
    """Initialise DB + load agents."""
    init_db()
    load_all_agents()


def run_once(dry_run: bool = False):
    """Run pipeline once for all agents."""
    _bootstrap()
    from core.orchestrator import run_once as _once
    _once(dry_run=dry_run)


def run_scheduled(dry_run: bool = False):
    """Start blocking scheduler."""
    _bootstrap()
    from core.orchestrator import run_loop
    run_loop(dry_run=dry_run)


def run_dashboard():
    """Start the Flask web dashboard."""
    _bootstrap()
    try:
        from ui.web_dashboard.app import start_dashboard
        start_dashboard()
    except ImportError as e:
        logger.error(f"Dashboard import failed: {e}")
        logger.error("Check that ui/__init__.py and ui/web_dashboard/__init__.py exist.")
        logger.error(f"sys.path = {sys.path[:4]}")
        sys.exit(1)


def run_both(dry_run: bool = False):
    """Start scheduler in background + dashboard in foreground."""
    _bootstrap()
    try:
        from core.orchestrator import run_loop
        from ui.web_dashboard.app import start_dashboard
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        logger.error(f"Ensure you are running from: {BASE_DIR}")
        logger.error("Run: pip install -r requirements.txt --break-system-packages")
        sys.exit(1)

    t = threading.Thread(target=run_loop, args=(dry_run,), daemon=True)
    t.start()
    logger.info("Orchestrator started in background thread.")
    start_dashboard()


def run_chat():
    """Interactive terminal chat with CEO Brain."""
    _bootstrap()
    try:
        from ui.chat_interface.chat import run_chat as _chat
        _chat()
    except ImportError as e:
        logger.error(f"Chat import failed: {e}")


def install_models():
    """Register all Modelfiles with local Ollama."""
    mf_dir = BASE_DIR / "modelfiles"
    if not mf_dir.exists():
        logger.error("modelfiles/ directory not found.")
        return
    import subprocess
    for mf in mf_dir.glob("Modelfile.*"):
        name = mf.stem.replace("Modelfile.", "").lower()
        logger.info(f"Installing model: {name}")
        result = subprocess.run(
            ["ollama", "create", name, "-f", str(mf)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info(f"  OK: {name}")
        else:
            logger.warning(f"  Failed: {name} — {result.stderr[:80]}")


def run_report():
    """Generate nightly report."""
    _bootstrap()
    try:
        from core.orchestrator import generate_report
        generate_report()
    except (ImportError, AttributeError) as e:
        logger.warning(f"Report generator not available: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Spidergram v3 — Autonomous AI Instagram Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--scheduled",      action="store_true", help="Start scheduler")
    parser.add_argument("--dashboard",      action="store_true", help="Start web dashboard")
    parser.add_argument("--both",           action="store_true", help="Scheduler + dashboard")
    parser.add_argument("--chat",           action="store_true", help="Terminal CEO chat")
    parser.add_argument("--dry-run",        action="store_true", help="No real IG posting")
    parser.add_argument("--agent",          type=str,            help="Run specific agent ID")
    parser.add_argument("--install-models", action="store_true", help="Install Ollama models")
    parser.add_argument("--report",         action="store_true", help="Generate report")
    args = parser.parse_args()

    logger.info(f"Spidergram v3 starting | cwd={BASE_DIR}")

    if args.install_models:
        install_models()
    elif args.scheduled:
        run_scheduled(dry_run=args.dry_run)
    elif args.dashboard:
        run_dashboard()
    elif args.both:
        run_both(dry_run=args.dry_run)
    elif args.chat:
        run_chat()
    elif args.report:
        run_report()
    elif args.agent:
        _bootstrap()
        agent = get_agent(args.agent)
        if not agent:
            logger.error(f"Agent '{args.agent}' not found.")
            sys.exit(1)
        agent.run(dry_run=args.dry_run)
    else:
        run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
