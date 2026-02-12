
import sqlite3
import hashlib
import uuid
from datetime import datetime
from threading import Lock
from typing import List, Dict, Tuple, Optional, Any
from contextlib import contextmanager

DB_PATH = "chat_history.db"

class Database:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """Initialize database with required tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT,
                    mode TEXT DEFAULT 'assistant',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Chat messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokens INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # --- User Management ---

    def create_user(self, username: str, password_hash: str) -> bool:
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- Conversation Management ---

    def create_conversation(self, user_id: int, title: str, mode: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (user_id, title, mode) VALUES (?, ?, ?)",
                (user_id, title, mode)
            )
            conn.commit()
            return cursor.lastrowid

    def get_user_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_conversation(self, conversation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_conversation_messages(self, conversation_id: int):
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM chat_messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.commit()
            
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                 "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                 (conversation_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0


    # --- Message Management ---

    def add_message(self, conversation_id: int, role: str, content: str, tokens: int):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages (conversation_id, role, content, tokens) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, tokens)
            )
            # Update conversation timestamp
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,)
            )
            conn.commit()

    def get_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

db = Database()
