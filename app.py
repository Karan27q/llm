"""
Advanced LLM Chatbot System with User Authentication
=====================================================

FEATURES:
✓ User authentication (signup/login/logout)
✓ Multi-mode prompt system (Assistant, Tutor, Code Expert, Creative)
✓ Context window management (smart token usage)
✓ Dashboard with conversation history
✓ Session-based persistence with SQLite
✓ Streaming Responses (Server-Sent Events)

ARCHITECTURE:
Users -> Auth System -> Dashboard -> Chat with Mode Selection -> 
Context Manager -> LLM API -> Streaming Response -> Database

DATABASE SCHEMA:
Managed by db.py
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, stream_with_context
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from functools import wraps
from typing import List, Dict, Generator

from db import Database

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Configure Google Gemini API
genai.configure(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "temperature": 0.7,
        "top_p": 0.9,
        "max_output_tokens": 4000,
    }
)

# Initialize Database
db = Database()

# Prompt modes: Different system prompts for different use cases
PROMPT_MODES = {
    "assistant": {
        "name": "Assistant",
        "system": """You are a helpful, friendly assistant. 
1. Be clear and concise
2. Ask clarifying questions if needed
3. Provide accurate information
4. Be honest about limitations
5. Maintain conversation context"""
    },
    "tutor": {
        "name": "Tutor",
        "system": """You are an expert tutor. Your role is to help users learn:
1. Explain concepts step-by-step
2. Use examples and analogies
3. Ask questions to check understanding
4. Encourage the learner
5. Adapt to learning level
6. Provide practice problems"""
    },
    "code_expert": {
        "name": "Code Expert",
        "system": """You are an expert programmer. Help with code:
1. Write clean, efficient code
2. Follow best practices (SOLID, DRY, KISS)
3. Explain technical decisions
4. Suggest optimizations
5. Review for security and performance
6. Use appropriate language idioms"""
    },
    "creative": {
        "name": "Creative Writer",
        "system": """You are a creative writing assistant:
1. Encourage imaginative thinking
2. Help with storytelling and character development
3. Provide writing tips and techniques
4. Offer constructive feedback
5. Inspire and motivate
6. Adapt to different genres/styles"""
    }
}


# ============================================================================
# AUTHENTICATION UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash: str, password: str) -> bool:
    return stored_hash == hash_password(password)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# MESSAGE MANAGEMENT & CONTEXT WINDOW LOGIC
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ~ 4 characters)."""
    return len(text) // 4


def get_context_window_messages(conversation_id: int, max_tokens: int = 6000) -> List[Dict]:
    """Smart context window management."""
    raw_messages = db.get_messages(conversation_id)
    
    # Format for Gemini API
    all_messages = [{"role": msg["role"], "parts": [msg["content"]]} for msg in raw_messages]
    
    # Simple strategy: Keep all if fits, otherwise truncate from beginning
    # In a real app, you'd want smarter summarization
    total_tokens = sum(estimate_tokens(msg["parts"][0]) for msg in all_messages)
    
    if total_tokens <= max_tokens:
        return all_messages
        
    context = []
    current_tokens = 0
    for msg in reversed(all_messages):
        msg_tokens = estimate_tokens(msg["parts"][0])
        if current_tokens + msg_tokens > max_tokens:
            break
        context.insert(0, msg)
        current_tokens += msg_tokens
            
    return context


# ============================================================================
# ROUTES: AUTHENTICATION
# ============================================================================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.json
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400
        
        password_hash = hash_password(password)
        if db.create_user(username, password_hash):
            return jsonify({"success": True, "message": "User created successfully"})
        return jsonify({"success": False, "message": "Username already exists"}), 400
    
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        user = db.get_user_by_username(username)
        if user and verify_password(user['password_hash'], password):
            session["user_id"] = user['id']
            session["username"] = user['username']
            return jsonify({"success": True, "message": "Logged in successfully"})
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================================
# ROUTES: DASHBOARD & CONVERSATIONS
# ============================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/conversations", methods=["GET"])
@login_required
def get_conversations():
    try:
        conversations = db.get_user_conversations(session["user_id"])
        # Convert row objects to dicts if needed, though db.py returns dicts or rows
        # db.py methods return list of dicts or Row objects. 
        # Row objects are close enough to dicts for jsonify in recent Flask, 
        # but let's ensure they are serializable.
        return jsonify({"conversations": [dict(c) for c in conversations]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversation/new", methods=["POST"])
@login_required
def new_conversation():
    try:
        data = request.json
        mode = data.get("mode", "assistant")
        
        if mode not in PROMPT_MODES:
            return jsonify({"error": "Invalid mode"}), 400
        
        title = f"{PROMPT_MODES[mode]['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        conv_id = db.create_conversation(session["user_id"], title, mode)
        
        return jsonify({
            "success": True,
            "conversation_id": conv_id,
            "mode": mode
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversation/<int:conversation_id>", methods=["DELETE"])
@login_required
def delete_conversation(conversation_id):
    try:
        success = db.delete_conversation(conversation_id, session["user_id"])
        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Conversation not found or unauthorized"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat/<int:conversation_id>")
@login_required
def chat_page(conversation_id):
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return redirect(url_for("dashboard"))
    
    return render_template("chat.html", conversation_id=conversation_id)


# ============================================================================
# ROUTES: CHAT API & STREAMING
# ============================================================================

@app.route("/api/chat/<int:conversation_id>/history", methods=["GET"])
@login_required
def get_history(conversation_id):
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403
    
    messages = db.get_messages(conversation_id)
    # Transform for frontend if necessary, or just send as is
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "role": msg["role"],
            "parts": [msg["content"]]
        })
        
    return jsonify({"messages": formatted_messages, "mode": conversation["mode"]})


@app.route("/api/chat/<int:conversation_id>/stream", methods=["POST"])
@login_required
def stream_chat(conversation_id):
    """
    Handle chat with streaming response (Server-Sent Events).
    """
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # 1. Save User Message
    db.add_message(conversation_id, "user", user_msg, estimate_tokens(user_msg))

    # 2. Get Context
    chat_history = get_context_window_messages(conversation_id)

    # 3. Prepare Prompt
    system_prompt = PROMPT_MODES[conversation["mode"]]["system"]
    
    # 4. Stream Response
    def generate():
        full_response = ""
        try:
            # Build full history for Gemini
            full_history = []
            full_history.append({"role": "model", "parts": [system_prompt]})
            full_history.extend(chat_history)
            
            # Streaming call
            response = model.generate_content(full_history, stream=True)
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    # Send chunk data
                    yield f"data: {json.dumps({'content': chunk.text})}\\n\\n"
            
            # End of stream
            # 5. Save Model Response
            db.add_message(conversation_id, "model", full_response, estimate_tokens(full_response))
            yield f"data: {json.dumps({'done': True})}\\n\\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\\n\\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route("/api/chat/<int:conversation_id>/clear", methods=["POST"])
@login_required
def clear_conversation(conversation_id):
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403
        
    db.delete_conversation_messages(conversation_id)
    return jsonify({"status": "Cleared"})


@app.route("/api/modes")
def get_modes():
    modes = {
        key: {"name": value["name"]}
        for key, value in PROMPT_MODES.items()
    }
    return jsonify({"modes": modes})


if __name__ == "__main__":
    app.run(debug=True)
