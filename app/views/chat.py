from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.views.auth import login_required
from app.services.chat_service import ChatService
from app.services.ai_service import AIService
from datetime import datetime

chat_bp = Blueprint("chat", __name__)
chat_service = ChatService()
ai_service = AIService()

@chat_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat.dashboard"))
    return redirect(url_for("auth.login"))

@chat_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@chat_bp.route("/api/conversations", methods=["GET"])
@login_required
def get_conversations():
    try:
        conversations = chat_service.get_user_conversations(session["user_id"])
        # Convert SQLAlchemy objects to dictionaries
        conv_list = []
        for c in conversations:
            conv_list.append({
                "id": c.id,
                "user_id": c.user_id,
                "title": c.title,
                "mode": c.mode,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None
            })
        return jsonify({"conversations": conv_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chat_bp.route("/api/conversation/new", methods=["POST"])
@login_required
def new_conversation():
    try:
        data = request.json or {}
        mode = data.get("mode", "assistant")
        
        if mode not in ai_service.prompt_templates:
            return jsonify({"error": "Invalid mode"}), 400
        
        title = f"{mode.title()} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        conv = chat_service.create_conversation(session["user_id"], title, mode, request.remote_addr)
        
        return jsonify({
            "success": True,
            "conversation_id": conv.id,
            "mode": mode
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chat_bp.route("/api/conversation/<int:conversation_id>", methods=["DELETE"])
@login_required
def delete_conversation(conversation_id):
    try:
        success = chat_service.delete_conversation(conversation_id, session["user_id"], request.remote_addr)
        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Conversation not found or unauthorized"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chat_bp.route("/chat/<int:conversation_id>")
@login_required
def chat_page(conversation_id):
    conversation = chat_service.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return redirect(url_for("chat.dashboard"))
    
    return render_template("chat.html", conversation_id=conversation_id)

@chat_bp.route("/api/chat/<int:conversation_id>/history", methods=["GET"])
@login_required
def get_history(conversation_id):
    conversation = chat_service.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403
    
    messages = chat_service.get_messages(conversation_id, session["user_id"])
    if messages is None:
        return jsonify({"error": "Unauthorized"}), 403
        
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "role": msg.role,
            "parts": [msg.content]
        })
        
    return jsonify({"messages": formatted_messages, "mode": conversation.mode})

@chat_bp.route("/api/chat/<int:conversation_id>/clear", methods=["POST"])
@login_required
def clear_conversation(conversation_id):
    success = chat_service.clear_conversation_messages(conversation_id, session["user_id"], request.remote_addr)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to clear conversation or unauthorized"}), 500
