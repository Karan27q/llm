from flask import Blueprint, jsonify, session
from app.views.auth import login_required
from app.database import db_session
from app.models.user import User

users_bp = Blueprint("users", __name__)

@users_bp.route("/api/users/me")
@login_required
def get_current_user():
    user = db_session.query(User).filter(User.id == session["user_id"]).first()
    if user:
        return jsonify({
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })
    return jsonify({"error": "User not found"}), 404
