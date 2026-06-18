import html
import re
import json
from flask import Blueprint, request, jsonify, session, Response, stream_with_context
from pydantic import ValidationError
from app.views.auth import login_required
from app.services.chat_service import ChatService
from app.services.ai_service import AIService
from app.services.audit_service import AuditService
from app.extensions import limiter
from app.schemas import ChatMessageSchema

ai_bp = Blueprint("ai", __name__)
chat_service = ChatService()
ai_service = AIService()
audit_service = AuditService()

def detect_prompt_injection(message: str) -> bool:
    """Scan messages for common prompt injection patterns."""
    patterns = [
        r"ignore (all )?previous instructions",
        r"system override",
        r"you must now act as",
        r"bypass (all )?guidelines",
        r"forget all (your )?guidelines",
        r"developer mode enabled",
        r"you are now in developer mode",
        r"respond only with"
    ]
    for pattern in patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True
    return False

@ai_bp.route("/api/chat/<int:conversation_id>/stream", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def stream_chat(conversation_id):
    conversation = chat_service.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json or {}
    try:
        # Pydantic input validation (limits size to 4000 chars)
        validated_data = ChatMessageSchema(**data)
    except ValidationError as e:
        return jsonify({"success": False, "message": e.errors()}), 400

    user_msg = validated_data.message.strip()

    # Sanitization
    user_msg_sanitized = html.escape(user_msg)

    # Prompt Injection Shield
    if detect_prompt_injection(user_msg):
        # Log prompt injection attempt
        audit_service.log_event(
            user_id=session["user_id"],
            action="PROMPT_INJECTION_ATTEMPT",
            ip_address=request.remote_addr,
            details=f"Blocked prompt injection message on conversation {conversation_id}: {user_msg[:100]}"
        )
        return jsonify({
            "success": False, 
            "error": "Security Blocked", 
            "message": "Potential prompt injection attempt detected. Request blocked."
        }), 400

    # 1. Save User Message
    chat_service.add_message(conversation_id, session["user_id"], "user", user_msg_sanitized, ai_service.estimate_tokens(user_msg_sanitized))

    # 2. Get Context (LangChain objects)
    history = ai_service.get_langchain_history(conversation_id, user_msg_sanitized)
    
    # 3. Create Chain
    mode = conversation.mode
    chain = ai_service.get_chain(mode)
    
    # 4. Stream Response
    def generate():
        full_response = ""
        try:
            # LangChain .stream() yields chunks
            for chunk in chain.stream({"history": history, "input": user_msg_sanitized}):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # End of stream
            # 5. Save Model Response
            chat_service.add_message(conversation_id, session["user_id"], "model", full_response, ai_service.estimate_tokens(full_response))
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            print(f"Error generating response: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@ai_bp.route("/api/modes")
def get_modes():
    return jsonify({"modes": ai_service.get_modes()})
