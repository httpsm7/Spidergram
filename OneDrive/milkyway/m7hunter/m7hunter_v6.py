#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════
#   M7HUNTER v6.0 — Bug Bounty Automation Framework (Upgraded)
#   Fixes: findings=0 bug, CEO errors, IDOR FPs, LFI FPs, SSRF injection
#   New: CSRF, Race Condition, NoSQL, Chain Engine, Burp Export
#   Multi-session: --userA --userB for IDOR testing
#   MilkyWay Intelligence | Author: Sharlix
# ═══════════════════════════════════════════════════════════════════

import os, sys, argparse, time, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.banner   import print_banner
from core.logger   import Logger
from core.utils    import check_root

def _sigint(sig, frame):
    print("\n\033[93m[!] Interrupted — saving state...\033[0m")
    sys.exit(0)
signal.signal(signal.SIGINT, _sigint)


def parse_args():
    p = argparse.ArgumentParser(
        prog="m7hunter",
        description="M7HUNTER v6.0 — Bug Bounty Automation Framework",
        epilog="""
Examples:
  sudo m7hunter -u target.com --deep
  sudo m7hunter -u target.com --deep --cookie "session=abc123"
  sudo m7hunter -u target.com --deep --userA "sess_a=x" --userB "sess_b=y"
  sudo m7hunter -u target.com --fast --confidence 0.7
  sudo m7hunter --dashboard
  sudo m7hunter --brain
"""
    )

    # Input
    inp = p.add_mutually_exclusive_group()
    inp.add_argument("-u", metavar="URL",  dest="url",  help="Target domain/URL")
    inp.add_argument("-f", metavar="FILE", dest="file", help="File with targets")

    # Modes
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--fast",       action="store_true")
    modes.add_argument("--deep",       action="store_true")
    modes.add_argument("--stealth",    action="store_true")
    modes.add_argument("--custom",     action="store_true")
    modes.add_argument("--continuous", action="store_true")

    # Step flags
    for step in ["subdomain","dns","probe","ports","crawl","nuclei","xss",
                 "sqli","cors","lfi","ssrf","redirect","takeover","screenshot",
                 "wpscan","github","cloud","ssti","jwt","graphql","host_header",
                 "idor","xxe","smuggling","csrf","race","nosql"]:
        p.add_argument(f"--{step}", action="store_true")

    # Auth — multi-session support
    p.add_argument("--cookie",         metavar="STR",   help="Auth cookie")
    p.add_argument("--userA",          metavar="COOKIE",help="Attacker session (IDOR testing)")
    p.add_argument("--userB",          metavar="COOKIE",help="Victim session (IDOR testing)")
    p.add_argument("--userA-file",     metavar="FILE",  help="Attacker cookie file",
                   dest="cookie_file")
    p.add_argument("--userB-file",     metavar="FILE",  help="Victim cookie file",
                   dest="userB_file")
    p.add_argument("--authorization",  metavar="TOKEN", help="Bearer/auth token")
    p.add_argument("--headers",        metavar="FILE",  help="Custom headers file")
    p.add_argument("--sessions-file",  metavar="FILE",  help="Named sessions JSON",
                   dest="sessions_file")

    # Scope
    p.add_argument("--scope",   metavar="FILE")
    p.add_argument("--exclude", metavar="FILE")

    # Performance
    p.add_argument("-o","--output",    metavar="DIR")
    p.add_argument("-t","--threads",   metavar="N",  type=int, default=50)
    p.add_argument("--rate",           metavar="N",  type=int, default=1000)
    p.add_argument("--timeout",        metavar="N",  type=int, default=300)
    p.add_argument("--proxy",          metavar="URL")
    p.add_argument("--resume",         action="store_true")
    p.add_argument("--no-color",       action="store_true")

    # Confidence threshold
    p.add_argument("--confidence",     metavar="F",  type=float, default=0.8,
                   help="Min confidence threshold (default: 0.8)")

    # Config
    p.add_argument("-c","--config",    metavar="FILE")
    p.add_argument("--wordlist",       metavar="FILE")

    # Tor
    p.add_argument("--tor",            action="store_true")

    # Notifications
    p.add_argument("--telegram-token", metavar="TOKEN")
    p.add_argument("--telegram-chat",  metavar="ID")
    p.add_argument("--discord-webhook",metavar="URL")
    p.add_argument("--telegram-bot",   action="store_true")

    # API keys
    p.add_argument("--github-token",   metavar="TOKEN")
    p.add_argument("--shodan-key",     metavar="KEY")
    p.add_argument("--vt-key",         metavar="KEY")
    p.add_argument("--wpscan-token",   metavar="TOKEN")
    p.add_argument("--censys-id",      metavar="ID")
    p.add_argument("--censys-secret",  metavar="KEY")
    p.add_argument("--interactsh-url", metavar="URL")

    # V6 features
    p.add_argument("--osint",          action="store_true")
    p.add_argument("--phase1-only",    action="store_true", dest="phase1_only")
    p.add_argument("--proof",          action="store_true")
    p.add_argument("--risk-score",     action="store_true")
    p.add_argument("--ai-model",       metavar="MODEL", default="mistral")
    p.add_argument("--auto-exploit",   action="store_true")
    p.add_argument("--exploit-threads",metavar="N", type=int, default=10)
    p.add_argument("--interval",       metavar="SEC", type=int, default=3600)

    # Reports
    p.add_argument("--export-burp",    action="store_true", dest="export_burp",
                   help="Export Burp Suite XML")
    p.add_argument("--export-md",      action="store_true", dest="export_md",
                   help="Export Markdown report")

    # Platform
    p.add_argument("--dashboard",      action="store_true")
    p.add_argument("--dashboard-port", metavar="PORT", type=int, default=8719)
    p.add_argument("--setup-vscode",   action="store_true")

    # Maintenance
    p.add_argument("--install",        action="store_true")
    p.add_argument("--update",         action="store_true")
    p.add_argument("--check",          action="store_true")
    p.add_argument("--analyze",        action="store_true")
    p.add_argument("--brain",          action="store_true")
    p.add_argument("--check-tools",    action="store_true", dest="check_tools")
    p.add_argument("--open-your-brain",action="store_true", dest="open_brain")
    p.add_argument("--setup-ai",       action="store_true")
    p.add_argument("--setup-brain",    action="store_true", dest="setup_brain")

    return p.parse_args()


def main():
    check_root()
    print_banner()
    args = parse_args()
    log  = Logger(no_color=args.no_color)

    # Maintenance modes
    if args.install:
        from core.installer import ToolInstaller
        ToolInstaller(log).install_all(); sys.exit(0)

    if args.update:
        from core.installer import ToolInstaller
        ToolInstaller(log).update_all(); sys.exit(0)

    if args.check:
        from core.installer import ToolInstaller
        ToolInstaller(log).check_only(); sys.exit(0)

    if args.analyze:
        from ai.analyzer import M7Analyzer
        M7Analyzer().run(); sys.exit(0)

    if getattr(args,'brain',False):
        from ai.brain import M7Brain
        b = M7Brain()
        if b.authenticate(): b.interactive_mode()
        sys.exit(0)

    if getattr(args,'open_brain',False):
        from ai.brain_viewer import BrainViewer
        BrainViewer().run(); sys.exit(0)

    if getattr(args,'setup_brain',False):
        from ai.secure_db import SecureDB
        db = SecureDB()
        db._setup_first_run(); sys.exit(0)

    if getattr(args,'setup_vscode',False):
        from integrations.vscode import setup_vscode
        setup_vscode("."); sys.exit(0)

    if getattr(args,'setup_ai',False):
        from ai.offline.ollama_engine import OfflineAI as OllamaAI
        if OllamaAI.install_ollama():
            log.success("Ollama installed")
            OllamaAI.pull_model(args.ai_model)
        sys.exit(0)

    if getattr(args,'dashboard',False) and not args.url and not args.file:
        from web.dashboard import Dashboard
        Dashboard(log=log, port=args.dashboard_port,
                  results_dir=args.output or "results").start(blocking=True)
        sys.exit(0)

    if getattr(args,'telegram_bot',False):
        tg_token = getattr(args,'telegram_token',None)
        if not tg_token:
            log.error("--telegram-bot requires --telegram-token TOKEN")
            sys.exit(1)
        from integrations.telegram_bot import TelegramBot
        TelegramBot(token=tg_token, log=log).run()
        sys.exit(0)

    # Validate target
    if not args.url and not args.file:
        log.error("No target! Use -u <domain> or -f <file>")
        sys.exit(1)

    if args.stealth:
        args.tor = True

    # Warn if no auth provided
    if not getattr(args,'cookie',None) and not getattr(args,'authorization',None):
        log.warn("No --cookie provided — authenticated endpoints won't be scanned")
        log.warn("Add: --cookie 'session=your_session_value' for authenticated scan")

    # Multi-session info
    if getattr(args,'userA',None) and getattr(args,'userB',None):
        args.cookie   = args.userA
        args.cookie_b = args.userB
        log.success("Multi-session IDOR testing enabled (userA + userB)")
    elif getattr(args,'userA',None):
        args.cookie = args.userA

    # Pre-flight
    from core.installer import ToolInstaller
    ToolInstaller(log).check_only()

    # Dashboard background
    if getattr(args,'dashboard',False):
        from web.dashboard import Dashboard
        Dashboard(log=log, port=args.dashboard_port,
                  results_dir=args.output or "results").start_background()

    # Tor
    tor = None
    if args.tor:
        from core.tor_manager import TorManager
        tor = TorManager(log); tor.start()

    # OOB
    oob = None
    try:
        from engines.interactsh import InteractshClient
        oob = InteractshClient(custom_url=getattr(args,'interactsh_url',None), log=log)
        oob.start()
    except Exception: pass

    # Offline AI
    offline_ai = None
    try:
        from ai.offline_ai import OfflineAI
        offline_ai = OfflineAI(log=log)
        log.success(f"Offline AI: {offline_ai.get_status()}")
    except Exception: pass

    # Notifier
    notifier = None
    tg_token = getattr(args,'telegram_token',None)
    tg_chat  = getattr(args,'telegram_chat',None)
    if tg_token and tg_chat:
        from core.notifier import Notifier
        notifier = Notifier(telegram_token=tg_token, telegram_chat=tg_chat, log=log)

    # Targets
    targets = []
    if args.url:
        targets = [args.url.strip()]
    elif args.file:
        if not os.path.isfile(args.file):
            log.error(f"File not found: {args.file}")
            sys.exit(1)
        with open(args.file) as f:
            targets = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    scope_list = []
    if getattr(args,'scope',None) and os.path.isfile(args.scope):
        with open(args.scope) as f:
            scope_list = [l.strip() for l in f if l.strip()]
        log.info(f"Scope: {len(scope_list)} entries")

    log.success(f"Targets: {len(targets)}")
    if getattr(args,'userA',None) or getattr(args,'userB',None):
        log.info("Mode: Multi-session (IDOR testing active)")

    def run_all():
        from core.pipeline_v5 import PipelineV6
        reports = []
        for i, target in enumerate(targets, 1):
            log.section(f"TARGET {i}/{len(targets)}: {target}")
            pipeline = PipelineV6(
                target               = target,
                args                 = args,
                tor                  = tor,
                oob                  = oob,
                notifier             = notifier,
                log                  = log,
                scope_list           = scope_list,
                offline_ai           = offline_ai,
                confidence_threshold = getattr(args,'confidence', 0.8),
            )
            report = pipeline.run()
            if report:
                reports.append(report)
                # Burp export
                if getattr(args,'export_burp',False):
                    try:
                        from reporting.report_generator import ReportGeneratorV6
                        gen   = ReportGeneratorV6(pipeline)
                        paths = gen.generate_all()
                        log.success(f"Burp XML → {paths.get('burp','?')}")
                        log.success(f"Markdown → {paths.get('markdown','?')}")
                    except Exception as e:
                        log.warn(f"Report gen failed: {e}")
        return reports

    if getattr(args,'continuous',False):
        log.section(f"CONTINUOUS — every {args.interval}s")
        n = 0
        while True:
            n += 1
            log.info(f"Run #{n}")
            run_all()
            log.info(f"Next in {args.interval}s...")
            time.sleep(args.interval)
    else:
        reports = run_all()
        log.section("COMPLETE")
        for r in reports:
            log.success(f"Report → {r}")

    if oob:
        try: oob.stop()
        except Exception: pass
    if tor:
        tor.stop()


if __name__ == "__main__":
    main()
