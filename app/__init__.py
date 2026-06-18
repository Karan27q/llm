import os
import datetime
import threading
from flask import Flask, session, request, jsonify
from app.config import Config
from app.database import db_session, init_db
from app.extensions import limiter

def create_app():
    # Configure template folder to be in the workspace root
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    
    app = Flask(__name__, template_folder=template_dir)
    app.config.from_object(Config)
    
    # Session Expiration Configuration (15 minutes of inactivity)
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=15)
    
    # Configure Secure Cookie Settings
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # SESSION_COOKIE_SECURE is enabled if running on HTTPS (or production)
    app.config['SESSION_COOKIE_SECURE'] = os.getenv("FLASK_ENV") == "production"
    
    # Initialize extensions
    limiter.init_app(app)
    
    # Initialize database (automatically runs migrations)
    init_db()
    
    # Set session as permanent at startup to trigger lifetime limit
    @app.before_request
    def make_session_permanent():
        session.permanent = True
    
    # Security Headers after_request middleware
    @app.after_request
    def apply_security_headers(response):
        # Content Security Policy (CSP)
        # Allows styles and scripts from our domains and trusted CDNs
        csp_policies = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com cdnjs.cloudflare.com",
            "font-src 'self' fonts.gstatic.com cdnjs.cloudflare.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-ancestors 'none'"
        ]
        response.headers['Content-Security-Policy'] = "; ".join(csp_policies)
        
        # HTTP Strict Transport Security (HSTS)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME-type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    # Register blueprints
    from app.views.auth import auth_bp
    from app.views.chat import chat_bp
    from app.views.ai import ai_bp
    from app.views.users import users_bp
    from app.views.admin import admin_bp
    from app.views.audit import audit_bp
    
    app.register_blueprint(auth_bp, url_prefix="")
    app.register_blueprint(chat_bp, url_prefix="")
    app.register_blueprint(ai_bp, url_prefix="")
    app.register_blueprint(users_bp, url_prefix="")
    app.register_blueprint(admin_bp, url_prefix="")
    app.register_blueprint(audit_bp, url_prefix="")
    
    # Teardown database session
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()
        
    # Rate Monitoring System - 429 Error Handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        from app.services.audit_service import AuditService
        from flask_limiter.util import get_remote_address
        
        ip = get_remote_address()
        user_id = session.get("user_id")
        details = f"Rate limit exceeded: {e.description}. Route: {request.path}"
        
        audit_service = AuditService()
        audit_service.log_event(
            user_id=user_id,
            action="RATE_LIMIT_EXCEEDED",
            ip_address=ip,
            details=details
        )
        
        return jsonify({
            "success": False,
            "error": "Rate Limit Exceeded",
            "message": "Too many requests. Please slow down."
        }), 429
        
    return app

class LazyWSGIApp:
    """
    A thread-safe, lazy-loading WSGI application wrapper.
    Ensures the Flask application is only created on the first request,
    avoiding premature initialization of databases or Alembic migrations
    during simple imports (e.g., from command line tools or Alembic cli).
    """
    def __init__(self):
        self._app = None
        self._lock = threading.Lock()

    def __call__(self, environ, start_response):
        if self._app is None:
            with self._lock:
                if self._app is None:
                    self._app = create_app()
        return self._app(environ, start_response)

# Expose 'app' as a package-level variable to satisfy Gunicorn 'app:app' targets
app = LazyWSGIApp()
