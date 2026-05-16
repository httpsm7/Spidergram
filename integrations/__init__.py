<<<<<<< HEAD
"""integrations — External API wrappers (lazy imports)."""

def fetch_top_headlines(*a, **kw):
    from .newsapi import fetch_top_headlines as _f; return _f(*a, **kw)

def fetch_everything(*a, **kw):
    from .newsapi import fetch_everything as _f; return _f(*a, **kw)

def fetch_top_news(*a, **kw):
    from .gnews import fetch_top_news as _f; return _f(*a, **kw)

def search_photos(*a, **kw):
    from .pexels import search_photos as _f; return _f(*a, **kw)

def search_videos(*a, **kw):
    from .pexels import search_videos as _f; return _f(*a, **kw)

def get_best_video_file(*a, **kw):
    from .pexels import get_best_video_file as _f; return _f(*a, **kw)

def get_photo_url(*a, **kw):
    from .pexels import get_photo_url as _f; return _f(*a, **kw)

def generate_speech(*a, **kw):
    from .elevenlabs import generate_speech as _f; return _f(*a, **kw)

def grok_chat(*a, **kw):
    from .grok import chat as _f; return _f(*a, **kw)

def publish_image(*a, **kw):
    from .instagram import publish_image as _f; return _f(*a, **kw)

def publish_reel(*a, **kw):
    from .instagram import publish_reel as _f; return _f(*a, **kw)

def get_insights(*a, **kw):
    from .instagram import get_insights as _f; return _f(*a, **kw)
=======
from .newsapi    import fetch_top_headlines, fetch_everything  # noqa
from .gnews      import fetch_top_news                         # noqa
from .pexels     import search_photos, search_videos, get_best_video_file, get_photo_url  # noqa
from .elevenlabs import generate_speech                        # noqa
from .grok       import chat as grok_chat                      # noqa
from .instagram  import publish_image, publish_reel, get_insights  # noqa
>>>>>>> 7b1b7349c1d54f6c346dac412232596c219e252b
