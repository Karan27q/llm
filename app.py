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
from dotenv import load_dotenv
import os
import json
import hashlib
from datetime import datetime
from functools import wraps
from typing import List, Dict, Generator

from db import Database

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Configure Google Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_GEMINI_API_KEY not found in .env file")

# --- LangChain Setup ---
# Initialize the Chat Model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.7
)

# Initialize Database
db = Database()

# Prompt Templates for different modes
PROMPT_TEMPLATES = {
    "assistant": ChatPromptTemplate.from_messages([
        ("system", "You are a helpful, harmless, and honest AI assistant. Your goal is to provide accurate and useful information to the user."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ]),
    "tutor": ChatPromptTemplate.from_messages([
        ("system", "You are an expert tutor. Explain concepts clearly and simply, using analogies when helpful. Verify the user's understanding by asking follow-up questions."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ]),
    "code_expert": ChatPromptTemplate.from_messages([
        ("system", "You are a senior software engineer. Provide efficient, clean, and well-documented code. Explain your logic and potential trade-offs. Always prefer modern best practices."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ]),
    "creative": ChatPromptTemplate.from_messages([
        ("system", "You are a creative writer and storyteller. Be imaginative, descriptive, and engaging. Feel free to use metaphors and vivid imagery."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
}

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def estimate_tokens(text):
    # Simple estimation: 1 token ~= 4 chars
    return len(text) // 4

def get_langchain_history(conversation_id):
    """
    Retrieves history from DB and converts to LangChain Message objects.
    We limit context to approx last 20 messages for efficiency, 
    but for a real app you might use a specific WindowMemory or SummaryMemory.
    """
    db_messages = db.get_messages(conversation_id, limit=20)
    history = []
    
    # db.get_messages returns newest last. 
    # Verify order: it usually returns older -> newer
    
    for msg in db_messages:
        role = msg['role']
        content = msg['content']
        if role == 'user':
            history.append(HumanMessage(content=content))
        elif role == 'model':
            history.append(AIMessage(content=content))
            
    return history

# ------------------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------------------

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
        # Convert row objects to dicts
        return jsonify({"conversations": [dict(c) for c in conversations]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversation/new", methods=["POST"])
@login_required
def new_conversation():
    try:
        data = request.json
        mode = data.get("mode", "assistant")
        
        if mode not in PROMPT_TEMPLATES:
            return jsonify({"error": "Invalid mode"}), 400
        
        title = f"{mode.title()} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
# ROUTES: CHAT API & STREAMING (LANGCHAIN)
# ============================================================================

@app.route("/api/chat/<int:conversation_id>/history", methods=["GET"])
@login_required
def get_history(conversation_id):
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403
    
    messages = db.get_messages(conversation_id)
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
    Handle chat with streaming response using LangChain.
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

    # 2. Get Context (LangChain objects)
    history = get_langchain_history(conversation_id)
    
    # Exclude the message we just added (if get_messages includes it, which it likely does).
    # Actually, we want previous history for the chain input. The user's new input is distinct.
    # If get_langchain_history includes the latest user message, pop it or separate it.
    # Our simple implementation retrieves all, including the one we just added.
    # Correct logic: History = All messages EXCEPT the last one (which is current input).
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_msg:
        history = history[:-1]

    # 3. Create Chain
    mode = conversation["mode"]
    prompt = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["assistant"])
    
    # Combine prompt | model | parser
    chain = prompt | llm | StrOutputParser()
    
    # 4. Stream Response
    def generate():
        full_response = ""
        try:
            # LangChain .stream() yield chunks
            for chunk in chain.stream({"history": history, "input": user_msg}):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\\n\\n"
            
            # End of stream
            # 5. Save Model Response
            db.add_message(conversation_id, "model", full_response, estimate_tokens(full_response))
            yield f"data: {json.dumps({'done': True})}\\n\\n"
            
        except Exception as e:
            print(f"Error generating response: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\\n\\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route("/api/chat/<int:conversation_id>/clear", methods=["POST"])
@login_required
def clear_conversation(conversation_id):
    conversation = db.get_conversation(conversation_id, session["user_id"])
    if not conversation:
        return jsonify({"error": "Unauthorized"}), 403
    
    if db.clear_conversation_messages(conversation_id):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to clear conversation"}), 500


@app.route("/api/modes")
def get_modes():
    modes = {
        key: {"name": key.replace('_', ' ').title()} # Dynamically generate name from key
        for key in PROMPT_TEMPLATES.keys()
    }
    return jsonify({"modes": modes})


if __name__ == "__main__":
    # Create DB tables if they don't exist
    # The Database class _init_db handles this on instantiation, but we ensure it's called
    db._init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
