from flask import Blueprint, render_template, request, jsonify
from app.views.decorators import role_required
from app.database import db_session
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import ChatMessage
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

admin_bp = Blueprint("admin", __name__)
audit_service = AuditService()
auth_service = AuthService()

@admin_bp.route("/admin/dashboard")
@role_required("admin")
def dashboard():
    try:
        users_count = db_session.query(User).filter(User.deleted_at.is_(None)).count()
        conversations_count = db_session.query(Conversation).filter(Conversation.deleted_at.is_(None)).count()
        messages_count = db_session.query(ChatMessage).filter(ChatMessage.deleted_at.is_(None)).count()
        rate_limits_count = db_session.query(AuditLog).filter(AuditLog.action == "RATE_LIMIT_EXCEEDED").count()
        
        stats = {
            "users_count": users_count,
            "conversations_count": conversations_count,
            "messages_count": messages_count,
            "rate_limits_count": rate_limits_count
        }
        
        # Get recent logs (50 events)
        logs = audit_service.get_logs(limit=50)
        
        # Get all users for administration
        users = db_session.query(User).filter(User.deleted_at.is_(None)).all()
        
        return render_template("admin_dashboard.html", stats=stats, logs=logs, users=users)
    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        stats = {
            "users_count": 0,
            "conversations_count": 0,
            "messages_count": 0,
            "rate_limits_count": 0
        }
        return render_template("admin_dashboard.html", stats=stats, logs=[], users=[])

@admin_bp.route("/api/admin/user/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def change_role(user_id):
    data = request.json or {}
    new_role = data.get("role", "")
    
    if auth_service.change_user_role(user_id, new_role):
        return jsonify({"success": True, "message": f"User role updated to '{new_role}'."})
    return jsonify({"success": False, "message": "Failed to update role. Invalid role or user not found."}), 400

@admin_bp.route("/api/admin/user/<int:user_id>/unlock", methods=["POST"])
@role_required("admin")
def unlock_user(user_id):
    if auth_service.unlock_user(user_id):
        return jsonify({"success": True, "message": "User account unlocked successfully."})
    return jsonify({"success": False, "message": "Failed to unlock user."}), 400
