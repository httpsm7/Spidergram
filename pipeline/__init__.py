"""pipeline — Spidergram content production chain (lazy imports)."""

def fetch_for_agent(*a, **kw):
    from .news_fetcher import fetch_for_agent as _f; return _f(*a, **kw)

def get_unused_items(*a, **kw):
    from .news_fetcher import get_unused_items as _f; return _f(*a, **kw)

def deduplicate(*a, **kw):
    from .deduplicator import deduplicate as _f; return _f(*a, **kw)

def is_duplicate(*a, **kw):
    from .deduplicator import is_duplicate as _f; return _f(*a, **kw)

def generate_script(*a, **kw):
    from .script_engine import generate_script as _f; return _f(*a, **kw)

def fetch_images(*a, **kw):
    from .media_fetcher import fetch_images as _f; return _f(*a, **kw)

def fetch_background_video(*a, **kw):
    from .media_fetcher import fetch_background_video as _f; return _f(*a, **kw)

def generate_narration(*a, **kw):
    from .tts_engine import generate_narration as _f; return _f(*a, **kw)

def produce_video(*a, **kw):
    from .video_engine import produce_video as _f; return _f(*a, **kw)

def add_subtitles_moviepy(*a, **kw):
    from .subtitle_engine import add_subtitles_moviepy as _f; return _f(*a, **kw)

def publish(*a, **kw):
    from .publisher import publish as _f; return _f(*a, **kw)
