"""
agent.py — Autonomous Pentest Agent — Main Entry Point
AI-Controlled Security Testing Engine
MilkyWay Intelligence | Author: Sharlix

Usage:
  sudo python3 agent.py -u https://target.com --quick
  sudo python3 agent.py -u https://target.com --deep --creds admin:password
  sudo python3 agent.py -u https://target.com --stealth --tor
  sudo python3 agent.py -f targets.txt --deep --groq-key YOUR_KEY
"""
import asyncio
import argparse
import os
import sys
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")
try:
    import urllib3; urllib3.disable_warnings()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.banner            import print_banner
from core.logger            import Logger
from core.database          import Database
from core.ai_brain          import AIBrain
from core.agent_loop        import AgentLoop
from core.action_dispatcher import ActionDispatcher
from core.session_manager   import SessionManager
from core.chain_detector    import ChainDetector
from core.format_fixer      import FormatFixer
from core.verifier          import Verifier
from protocols.http_client  import HTTPClient
from engines.e01_recon      import ReconEngine
from engines.e02_crawler    import CrawlerEngine
from engines.e05_js_analyzer import JSAnalyzerEngine
from modules.report         import generate_report


def parse_args():
    p = argparse.ArgumentParser(
        description="Autonomous Pentest Agent v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    inp = p.add_mutually_exclusive_group(required=True)
    inp.add_argument("-u", "--url",  help="Single target URL")
    inp.add_argument("-f", "--file", help="File with targets (one per line)")

    p.add_argument("--creds",     help="Login credentials: user:pass")
    p.add_argument("--creds-b",   help="Second user creds for IDOR: user:pass")
    p.add_argument("--login-url", help="Login endpoint URL")
    p.add_argument("--token",     help="Pre-authenticated Bearer token")
    p.add_argument("--cookie",    help="Pre-authenticated cookie: session=abc123")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick",   action="store_true", help="Fast scan")
    mode.add_argument("--deep",    action="store_true", help="Full scan")
    mode.add_argument("--stealth", action="store_true", help="Deep + Tor + slow")
    mode.add_argument("--api",     action="store_true", help="API-only scan")

    p.add_argument("--ollama-model", default="llama3:8b")
    p.add_argument("--groq-key",     help="Groq API key")
    p.add_argument("--no-ai",        action="store_true")
    p.add_argument("--tor",          action="store_true")
    p.add_argument("--proxy",        help="Custom proxy URL")
    p.add_argument("--rate",         type=float, default=10.0)
    p.add_argument("--max-depth",    type=int, default=3)
    p.add_argument("--max-iter",     type=int, default=300)
    p.add_argument("--max-time",     type=int, default=240)
    p.add_argument("-o", "--output", default="results")
    p.add_argument("--no-color",     action="store_true")
    return p.parse_args()


def get_prefix(target: str) -> str:
    domain = FormatFixer.to_domain(target)
    clean  = "".join(c for c in domain if c.isalnum())
    return clean[:3].lower() if clean else "tgt"


async def run_scan(args):
    print_banner()
    logger = Logger(no_color=args.no_color)

    targets = []
    if args.url:
        targets = [args.url]
    else:
        with open(args.file) as f:
            targets = [l.strip() for l in f
                       if l.strip() and not l.startswith("#")]

    mode_str = ("QUICK" if args.quick else
                "DEEP"  if args.deep  else
                "STEALTH" if args.stealth else "API")
    logger.info(f"Targets: {len(targets)}")
    logger.info(f"Mode: {mode_str}")

    for target in targets:
        await scan_target(target, args, logger, mode_str)


async def scan_target(target: str, args, logger: Logger, mode_str: str):
    prefix    = get_prefix(target)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_dir  = os.path.join(args.output, f"{prefix}_{timestamp}")
    os.makedirs(scan_dir, exist_ok=True)

    logger.section(f"TARGET: {target}")
    logger.info(f"Output: {scan_dir}")

    db_path = os.path.join(scan_dir, f"{prefix}_agent.db")
    db      = Database(db_path)

    # ── Proxy / Tor setup ──────────────────────────────────
    proxy   = args.proxy
    stealth = args.stealth

    if args.tor or args.stealth:
        try:
            import socksio  # noqa
            import subprocess
            subprocess.Popen(["service", "tor", "start"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            await asyncio.sleep(3)
            proxy = "socks5://127.0.0.1:9050"
            logger.success("Tor enabled (socks5://127.0.0.1:9050)")
        except ImportError:
            logger.warn("socksio missing — Tor disabled. "
                        "Fix: pip install httpx[socks] socksio")
            proxy = None

    # ── HTTP Client ────────────────────────────────────────
    rate = 3.0 if stealth else float(args.rate)
    http = HTTPClient(proxy=proxy, stealth=stealth,
                      timeout=20, rate_per_sec=rate)

    # ── AI Brain ───────────────────────────────────────────
    groq_key = args.groq_key or os.environ.get("GROQ_API_KEY", "")
    if args.no_ai:
        groq_key = ""
        logger.warn("AI disabled — rule-based mode only")
    ai = AIBrain(logger, ollama_model=args.ollama_model, groq_key=groq_key)

    # ── Session Manager ────────────────────────────────────
    sm = SessionManager(db, logger, http)

    login_url = args.login_url

    if args.token:
        db.upsert_session("user_a", token=args.token)
        logger.success("Token session: user_a")

    elif args.cookie:
        k, v = (args.cookie.split("=", 1) if "=" in args.cookie
                else ("session", args.cookie))
        db.upsert_session("user_a", cookies={k: v})
        logger.success("Cookie session: user_a")

    elif args.creds:
        parts  = args.creds.split(":", 1)
        user   = parts[0]
        passwd = parts[1] if len(parts) > 1 else "password"
        if not login_url:
            login_url = FormatFixer.to_url(target).rstrip("/") + "/login"
        await sm.login(login_url, user, passwd, role="user_a")

    if getattr(args, "creds_b", None):
        parts_b = args.creds_b.split(":", 1)
        u_b = parts_b[0]
        p_b = parts_b[1] if len(parts_b) > 1 else "password"
        if login_url:
            await sm.login(login_url, u_b, p_b, role="user_b")

    # ── PHASE 1: Recon ─────────────────────────────────────
    logger.phase("RECONNAISSANCE")
    recon = ReconEngine(db, logger, http, scan_dir, prefix)
    await recon.run(target)

    logger.info(f"Nodes in graph: {db.node_count()}")
    logger.info(f"Untested nodes: {db.untested_count()}")

    # ── PHASE 2: Crawl ─────────────────────────────────────
    if not args.api:
        logger.phase("CRAWLING")
        session_cookies = sm.get_cookies_for_role("user_a")
        crawler = CrawlerEngine(
            db, logger, scan_dir, prefix,
            proxy=proxy, max_depth=args.max_depth, max_pages=100
        )
        await crawler.run(target, session_cookies=session_cookies)
        logger.info(f"After crawl — nodes: {db.node_count()}, "
                    f"untested: {db.untested_count()}")

    # ── PHASE 2b: JS Analysis ──────────────────────────────
    if not args.api and not args.quick:
        logger.phase("JS ANALYSIS")
        js_engine = JSAnalyzerEngine(db, logger, http, scan_dir, prefix)
        await js_engine.run(target)

    # ── PHASE 3: Baselines ─────────────────────────────────
    logger.phase("BUILDING BASELINES")
    await _build_baselines(db, http, sm, logger)

    # ── PHASE 4: AI Agent Loop ─────────────────────────────
    dispatcher = ActionDispatcher(db, logger, http, sm, ai, scan_dir, prefix)
    chain_det  = ChainDetector(db, ai, logger)

    max_iter = args.max_iter
    if args.quick:
        max_iter = min(max_iter, 80)

    loop = AgentLoop(
        db=db, ai_brain=ai,
        dispatcher=dispatcher,
        chain_detector=chain_det,
        logger=logger,
        max_iterations=max_iter,
        max_time_sec=args.max_time * 60
    )

    start   = time.time()
    summary = await loop.run()
    duration = time.time() - start

    # ── PHASE 5: Report ────────────────────────────────────
    logger.phase("GENERATING REPORT")
    report_path = generate_report(
        db=db, out_dir=scan_dir, prefix=prefix,
        target=target, scan_mode=mode_str,
        duration_sec=duration,
        tor_enabled=bool(proxy and "socks5" in proxy)
    )

    logger.success(f"Report   : {report_path}")
    logger.success(f"Findings : {summary['findings']}")
    logger.success(f"Chains   : {summary['chains']}")
    logger.success(f"Duration : {int(duration)}s")

    await http.close()
    db.close()


async def _build_baselines(db, http: HTTPClient,
                            sm: SessionManager, logger: Logger):
    nodes   = db.get_all_nodes()
    headers = sm.get_headers_for_role("user_a")
    cookies = sm.get_cookies_for_role("user_a")
    to_probe = nodes[:50]
    logger.info(f"Building baselines for {len(to_probe)} endpoints...")

    for node in to_probe:
        url  = node["url"]
        resp = await http.get(url, extra_headers=headers,
                              session_cookies=cookies, retries=1)
        if resp:
            db.save_baseline(
                url=url, method="GET",
                status_code=resp.status_code,
                body_size=len(resp.content),
                resp_time_ms=getattr(resp, "elapsed_ms", 0),
                structure_hash=HTTPClient.structure_hash(resp),
                content_type=resp.headers.get("content-type", ""),
                session_role="user_a"
            )


def main():
    if os.geteuid() != 0:
        print("\n[!] Run as root: sudo python3 agent.py\n")
        sys.exit(1)
    args = parse_args()
    os.makedirs(args.output, exist_ok=True)
    try:
        asyncio.run(run_scan(args))
    except KeyboardInterrupt:
        print("\n[!] Interrupted — partial results saved")
    except Exception as e:
        print(f"\n[-] Fatal error: {e}")
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()
