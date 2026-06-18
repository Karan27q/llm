from functools import wraps
from flask import session, redirect, url_for, abort
from app.database import db_session
from app.models.user import User

def role_required(*roles):
    """
    Decorator to restrict route access to specific roles.
    Example: @role_required('admin', 'moderator')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            
            user = db_session.query(User).filter(
                User.id == session["user_id"],
                User.deleted_at.is_(None)
            ).first()
            
            if not user or user.role not in roles:
                # 403 Forbidden if the role is not authorized
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
