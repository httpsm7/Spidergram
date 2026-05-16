"""
agents/agent_template.py
─────────────────────────
Base Agent class. All 5 news agents inherit from this.
Each agent has: config, memory, task queue access, pipeline runner.
"""

import json
from datetime import datetime
from database.models import (
    AgentMemory, TaskQueue, PostLog, Analytics, db, NewsItem
)
from pipeline import (
    fetch_for_agent, get_unused_items,
    generate_script, fetch_images, fetch_background_video,
    generate_narration, produce_video, add_subtitles_moviepy, publish,
)
from integrations.instagram import get_insights
from utils import get_logger


class BaseAgent:
    def __init__(self, config: dict):
        self.config   = config
        self.id       = config["id"]
        self.name     = config["name"]
        self.niche    = config["niche"]
        self.log      = get_logger(f"agent.{self.id}")
        self._memory  = None

    # ── Memory ─────────────────────────────────────────────────────────

    @property
    def memory(self) -> dict:
        if self._memory is None:
            self._memory = self._load_memory()
        return self._memory

    def _load_memory(self) -> dict:
        rec = AgentMemory.select().where(AgentMemory.agent_id == self.id).first()
        return json.loads(rec.memory_json) if rec else {}

    def save_memory(self) -> None:
        with db:
            rec, _ = AgentMemory.get_or_create(agent_id=self.id)
            rec.memory_json = json.dumps(self.memory, default=str)
            rec.updated_at  = datetime.now()
            rec.save()

    def remember(self, key: str, value) -> None:
        self.memory[key] = value
        self.save_memory()

    # ── Task Queue ─────────────────────────────────────────────────────

    def enqueue(self, task_type: str, payload: dict = None, priority: int = 5) -> TaskQueue:
        with db:
            task = TaskQueue.create(
                agent_id  = self.id,
                task_type = task_type,
                payload   = json.dumps(payload or {}),
                priority  = priority,
            )
        self.log.debug(f"Task enqueued: {task_type} (id={task.id})")
        return task

    def next_task(self) -> TaskQueue | None:
        return (TaskQueue
                .select()
                .where(TaskQueue.agent_id == self.id,
                       TaskQueue.status == "pending")
                .order_by(TaskQueue.priority, TaskQueue.created_at)
                .first())

    def _mark_task(self, task: TaskQueue, status: str, error: str = "") -> None:
        with db:
            task.status     = status
            task.updated_at = datetime.now()
            task.error      = error
            task.save()

    # ── Full Pipeline Runner ───────────────────────────────────────────

    def run_pipeline(self, dry_run: bool = False) -> PostLog | None:
        """
        Execute the full 10-step content pipeline for this agent.
        Returns PostLog record or None.
        """
        self.log.info(f"{'[DRY RUN] ' if dry_run else ''}Running pipeline for: {self.name}")

        try:
            # Step 1-3: Fetch + dedup + filter
            fetch_for_agent(self.config)
            categories = self.config.get("news_categories", ["general"])
            items      = get_unused_items(self.id, categories[0], limit=1)
            if not items:
                self.log.warning("No unused news items available.")
                return None
            news = items[0]

            # Step 4: Script
            script = generate_script(news, self.config)
            if not script:
                return None

            # Step 5: Media
            keywords   = self.config.get("news_keywords", [self.niche])
            images     = fetch_images(keywords, count=4)
            bg_video   = "" if images else fetch_background_video(keywords)

            # Step 6: Voice
            audio = generate_narration(script, self.config.get("voice_style", "professional"))

            # Step 7: Video
            video_path = produce_video(
                script       = script,
                image_paths  = images,
                audio_path   = audio,
                bg_video     = bg_video,
                headline     = news.title,
            )
            if not video_path:
                self.log.error("Video production returned empty path.")
                return None

            # Step 8: Subtitles
            video_path = add_subtitles_moviepy(video_path, script.body,
                                               audio_duration=55.0)

            # Step 9-10: Caption + Publish
            if dry_run:
                self.log.info(f"[DRY RUN] Would publish: {news.title[:60]}")
                self.log.info(f"  Caption: {script.caption[:80]}")
                return None

            log = publish(
                agent_config = self.config,
                video_path   = video_path,
                caption      = script.caption,
                hashtags     = script.hashtags,
                news_title   = news.title,
            )

            # Mark news as used
            with db:
                news.used = True
                news.save()

            # Update memory with last post info
            self.remember("last_post_at", datetime.now().isoformat())
            self.remember("last_post_title", news.title)

            return log

        except Exception as exc:
            self.log.exception(f"Pipeline error: {exc}")
            return None

    # ── Analytics Sync ─────────────────────────────────────────────────

    def sync_analytics(self) -> None:
        """Pull Instagram Insights for recent successful posts."""
        token = self.config.get("access_token", "")
        if not token:
            return
        posts = (PostLog.select()
                 .where(PostLog.agent_id == self.id, PostLog.status == "success")
                 .order_by(PostLog.posted_at.desc())
                 .limit(10))
        for post in posts:
            ins = get_insights(post.media_id, token)
            if ins:
                with db:
                    Analytics.create(
                        post        = post,
                        likes       = ins.get("likes",       0),
                        comments    = ins.get("comments",    0),
                        saves       = ins.get("saved",       0),
                        impressions = ins.get("impressions", 0),
                        reach       = ins.get("reach",       0),
                        views       = ins.get("plays",       0),
                    )
        self.log.info(f"Analytics synced for {self.name}")

    def __repr__(self):
        return f"<Agent id={self.id} name={self.name} niche={self.niche}>"
