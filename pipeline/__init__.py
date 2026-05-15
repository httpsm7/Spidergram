"""pipeline package — full content production chain."""
from .news_fetcher   import fetch_for_agent, get_unused_items  # noqa
from .deduplicator   import deduplicate, is_duplicate           # noqa
from .script_engine  import generate_script                     # noqa
from .media_fetcher  import fetch_images, fetch_background_video # noqa
from .tts_engine     import generate_narration                  # noqa
from .video_engine   import produce_video                       # noqa
from .subtitle_engine import add_subtitles_moviepy              # noqa
from .publisher      import publish                             # noqa
