<<<<<<< HEAD
"""utils — Shared utilities (safe lazy imports)."""

def get_logger(name="spidergram"):
    from .logger import get_logger as _f; return _f(name)

# Expose logger at module level safely
try:
    from .logger import logger, get_logger
except Exception:
    import logging
    logger = logging.getLogger("spidergram")
    def get_logger(name="spidergram"): return logging.getLogger(name)

def md5(*a, **kw):
    from .helpers import md5 as _f; return _f(*a, **kw)

def sha256(*a, **kw):
    from .helpers import sha256 as _f; return _f(*a, **kw)

def unique_id(*a, **kw):
    from .helpers import unique_id as _f; return _f(*a, **kw)

def download_file(*a, **kw):
    from .helpers import download_file as _f; return _f(*a, **kw)

def retry(*a, **kw):
    from .helpers import retry as _f; return _f(*a, **kw)

def load_json(*a, **kw):
    from .helpers import load_json as _f; return _f(*a, **kw)

def save_json(*a, **kw):
    from .helpers import save_json as _f; return _f(*a, **kw)

def upload_cloudinary(*a, **kw):
    from .helpers import upload_cloudinary as _f; return _f(*a, **kw)

def set_key(*a, **kw):
    from .security import set_key as _f; return _f(*a, **kw)

def get_key(*a, **kw):
    from .security import get_key as _f; return _f(*a, **kw)

def list_keys(*a, **kw):
    from .security import list_keys as _f; return _f(*a, **kw)

def delete_key(*a, **kw):
    from .security import delete_key as _f; return _f(*a, **kw)
=======
from .logger   import logger, get_logger   # noqa
from .helpers  import md5, sha256, unique_id, download_file, retry, load_json, save_json, upload_cloudinary  # noqa
from .security import set_key, get_key, list_keys, delete_key  # noqa
>>>>>>> 7b1b7349c1d54f6c346dac412232596c219e252b
