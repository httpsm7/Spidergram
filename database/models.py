"""
database/models.py
───────────────────
SQLite schema for Spidergram v2.
Tables: NewsItem, GeneratedScript, UsedMedia, PostLog, Analytics, AgentMemory, TaskQueue
"""

from datetime import datetime
from peewee import (
    SqliteDatabase, Model,
    CharField, TextField, IntegerField, FloatField,
    BooleanField, DateTimeField, ForeignKeyField, AutoField,
)
from config.settings import DB_PATH

db = SqliteDatabase(str(DB_PATH), pragmas={"journal_mode": "wal", "foreign_keys": 1})


class BaseModel(Model):
    class Meta:
        database = db


# ── News ───────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    id          = AutoField()
    hash        = CharField(unique=True, index=True)   # sha256 of title
    title       = TextField()
    description = TextField(default="")
    url         = CharField(default="")
    source      = CharField(default="")
    category    = CharField(default="general")
    language    = CharField(default="en")
    published   = DateTimeField(null=True)
    fetched_at  = DateTimeField(default=datetime.now)
    used        = BooleanField(default=False)

    class Meta:
        table_name = "news_items"


# ── Scripts ────────────────────────────────────────────────────────────

class GeneratedScript(BaseModel):
    id          = AutoField()
    news        = ForeignKeyField(NewsItem, backref="scripts", on_delete="CASCADE")
    agent_id    = CharField()
    hook        = TextField(default="")     # first 2s hook line
    body        = TextField(default="")     # full narration script
    caption     = TextField(default="")     # Instagram caption
    hashtags    = TextField(default="")
    created_at  = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "generated_scripts"


# ── Media ──────────────────────────────────────────────────────────────

class UsedMedia(BaseModel):
    id          = AutoField()
    pexels_id   = CharField(index=True)
    media_type  = CharField(default="photo")  # photo | video
    url         = CharField()
    local_path  = CharField(default="")
    used_count  = IntegerField(default=1)
    last_used   = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "used_media"


# ── Post Logs ──────────────────────────────────────────────────────────

class PostLog(BaseModel):
    id           = AutoField()
    agent_id     = CharField(index=True)
    ig_user_id   = CharField(default="")
    media_id     = CharField(default="")   # Instagram media ID
    video_path   = CharField(default="")
    caption      = TextField(default="")
    hashtags     = TextField(default="")
    status       = CharField(default="pending")   # pending|success|failed
    error        = TextField(default="")
    posted_at    = DateTimeField(default=datetime.now)
    news_title   = TextField(default="")

    class Meta:
        table_name = "post_logs"


# ── Analytics ──────────────────────────────────────────────────────────

class Analytics(BaseModel):
    id          = AutoField()
    post        = ForeignKeyField(PostLog, backref="analytics", on_delete="CASCADE")
    likes       = IntegerField(default=0)
    comments    = IntegerField(default=0)
    saves       = IntegerField(default=0)
    impressions = IntegerField(default=0)
    reach       = IntegerField(default=0)
    views       = IntegerField(default=0)
    synced_at   = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "analytics"


# ── Agent Memory ───────────────────────────────────────────────────────

class AgentMemory(BaseModel):
    id         = AutoField()
    agent_id   = CharField(unique=True, index=True)
    memory_json = TextField(default="{}")   # JSON blob
    updated_at  = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "agent_memory"


# ── Task Queue ─────────────────────────────────────────────────────────

class TaskQueue(BaseModel):
    id          = AutoField()
    agent_id    = CharField(index=True)
    task_type   = CharField()          # run_pipeline | fetch_news | post | report
    payload     = TextField(default="{}")
    status      = CharField(default="pending")   # pending|running|done|failed
    priority    = IntegerField(default=5)        # 1=highest, 10=lowest
    attempts    = IntegerField(default=0)
    created_at  = DateTimeField(default=datetime.now)
    updated_at  = DateTimeField(default=datetime.now)
    error       = TextField(default="")

    class Meta:
        table_name = "task_queue"
        indexes    = (
            (("status", "priority", "created_at"), False),
        )


# ── Init ───────────────────────────────────────────────────────────────

ALL_TABLES = [NewsItem, GeneratedScript, UsedMedia, PostLog, Analytics, AgentMemory, TaskQueue]

def init_db() -> None:
    with db:
        db.create_tables(ALL_TABLES, safe=True)
