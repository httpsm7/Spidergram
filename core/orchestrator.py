"""
core/orchestrator.py
─────────────────────
Central Orchestrator.

Responsibilities:
  • Run agent pipelines on schedule
  • Process the TaskQueue (retry failed tasks)
  • Sync analytics nightly
  • Listen for Telegram commands
  • Send daily report via Telegram
"""

import json, time, threading, schedule
from datetime import datetime

from agents import load_all_agents, get_agent
from database.models import TaskQueue, PostLog, db
from config.settings import POSTS_PER_DAY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils import get_logger

import requests

logger = get_logger("core.orchestrator")

TELEGRAM_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_last_update_id = 0


# ── Telegram helpers ────────────────────────────────────────────────────

def _tg_send(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            requests.get(f"{TELEGRAM_BASE}/sendMessage",
                         params={"chat_id": TELEGRAM_CHAT_ID,
                                 "text": chunk, "parse_mode": "HTML"},
                         timeout=10)
    except Exception as exc:
        logger.warning(f"Telegram send failed: {exc}")


def _tg_get_updates() -> list[dict]:
    global _last_update_id
    try:
        r = requests.get(f"{TELEGRAM_BASE}/getUpdates",
                         params={"offset": _last_update_id + 1, "timeout": 10},
                         timeout=15)
        r.raise_for_status()
        updates = r.json().get("result", [])
        if updates:
            _last_update_id = updates[-1]["update_id"]
        return updates
    except Exception:
        return []


# ── Task runner ────────────────────────────────────────────────────────

def _process_task(task: TaskQueue) -> None:
    """Execute one queued task."""
    agent = get_agent(task.agent_id)
    if not agent:
        with db:
            task.status = "failed"
            task.error  = "Agent not found"
            task.save()
        return

    with db:
        task.status     = "running"
        task.attempts  += 1
        task.updated_at = datetime.now()
        task.save()

    try:
        payload = json.loads(task.payload or "{}")
        if task.task_type == "run_pipeline":
            log = agent.run_pipeline(dry_run=payload.get("dry_run", False))
            status = "done" if log and log.status == "success" else "failed"
            error  = log.error if log else "no log"
        elif task.task_type == "sync_analytics":
            agent.sync_analytics()
            status, error = "done", ""
        else:
            status, error = "failed", f"Unknown task type: {task.task_type}"

        with db:
            task.status     = status
            task.error      = error
            task.updated_at = datetime.now()
            task.save()

    except Exception as exc:
        with db:
            task.status     = "failed"
            task.error      = str(exc)
            task.updated_at = datetime.now()
            task.save()
        logger.error(f"Task {task.id} failed: {exc}")


def flush_task_queue(max_tasks: int = 20) -> None:
    """Process up to max_tasks pending tasks."""
    pending = list(
        TaskQueue.select()
        .where(TaskQueue.status.in_(["pending", "failed"]),
               TaskQueue.attempts < 3)
        .order_by(TaskQueue.priority, TaskQueue.created_at)
        .limit(max_tasks)
    )
    if not pending:
        return
    logger.info(f"Processing {len(pending)} queued tasks.")
    for task in pending:
        _process_task(task)


# ── Scheduled jobs ─────────────────────────────────────────────────────

def _run_all_agents(dry_run: bool = False) -> None:
    """Enqueue pipeline runs for every active agent."""
    agents = load_all_agents()
    for aid, agent in agents.items():
        agent.enqueue("run_pipeline", {"dry_run": dry_run}, priority=3)
    flush_task_queue()


def _sync_all_analytics() -> None:
    agents = load_all_agents()
    for agent in agents.values():
        agent.enqueue("sync_analytics", priority=8)
    flush_task_queue()


def _nightly_report() -> None:
    from datetime import date
    with db:
        total   = PostLog.select().count()
        success = PostLog.select().where(PostLog.status=="success").count()
        today   = PostLog.select().where(
            PostLog.posted_at >= datetime.combine(date.today(), datetime.min.time())
        ).count()
    report = (
        f"🕷 <b>Spidergram Nightly Report</b> — {date.today()}\n\n"
        f"📊 Today's posts: <b>{today}</b>\n"
        f"✅ All-time success: {success} / {total}\n"
        f"❌ All-time failed:  {total - success}"
    )
    _tg_send(report)
    logger.info("Nightly report sent.")


def _handle_telegram_commands() -> None:
    updates = _tg_get_updates()
    for update in updates:
        msg  = update.get("message", {})
        text = msg.get("text", "").strip()
        if not text.startswith("/"):
            continue
        parts = text.split(maxsplit=1)
        cmd   = parts[0].lower()
        arg   = parts[1] if len(parts) > 1 else ""

        if cmd == "/status":
            agents = list(load_all_agents().values())
            lines  = [f"<b>Agents ({len(agents)})</b>"] + [
                f"▶️ {a.name} ({a.niche})" for a in agents
            ]
            _tg_send("\n".join(lines))
        elif cmd == "/run":
            agent = get_agent(arg.strip())
            if agent:
                agent.enqueue("run_pipeline", priority=1)
                _tg_send(f"▶ Pipeline queued for {agent.name}")
            else:
                _tg_send(f"Agent not found: {arg}")
        elif cmd == "/report":
            _nightly_report()
        elif cmd == "/help":
            _tg_send("/status /run <agent_id> /report /help")


# ── Main loop ──────────────────────────────────────────────────────────

def setup_schedule(posting_times: list[str] = None) -> None:
    times = posting_times or ["09:00", "13:00", "18:00", "21:00"]
    for t in times:
        schedule.every().day.at(t).do(_run_all_agents)
        logger.info(f"Scheduled agent run at {t}")
    schedule.every().day.at("00:05").do(_nightly_report)
    schedule.every().day.at("00:10").do(_sync_all_analytics)
    schedule.every(5).minutes.do(flush_task_queue)
    schedule.every(30).seconds.do(_handle_telegram_commands)


def run_loop() -> None:
    from database import init_db
    init_db()
    load_all_agents()
    setup_schedule()
    logger.info("Orchestrator running — press Ctrl-C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(15)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped.")
    finally:
        schedule.clear()
