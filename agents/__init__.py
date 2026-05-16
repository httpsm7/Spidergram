"""agents — Agent registry (safe lazy imports)."""

def load_all_agents(*a, **kw):
    from .agent_manager import load_all_agents as _f; return _f(*a, **kw)

def get_agent(*a, **kw):
    from .agent_manager import get_agent as _f; return _f(*a, **kw)

def list_agents(*a, **kw):
    from .agent_manager import list_agents as _f; return _f(*a, **kw)

def create_agent(*a, **kw):
    from .agent_manager import create_agent as _f; return _f(*a, **kw)

def edit_agent(*a, **kw):
    from .agent_manager import edit_agent as _f; return _f(*a, **kw)

def delete_agent(*a, **kw):
    from .agent_manager import delete_agent as _f; return _f(*a, **kw)

def set_agent_credentials(*a, **kw):
    from .agent_manager import set_agent_credentials as _f; return _f(*a, **kw)
