from flask import session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

def get_user_or_ip_key():
    """Identify request origin by User ID if authenticated, falling back to IP."""
    try:
        if "user_id" in session:
            return f"user_{session['user_id']}"
    except Exception:
        pass
    return get_remote_address()

limiter = Limiter(
    key_func=get_user_or_ip_key,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
