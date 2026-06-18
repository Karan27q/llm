import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from threading import Lock
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

load_dotenv()

class Database:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    @property
    def db_url(self):
        return os.getenv("DATABASE_URL")

    def _init_db(self):
        """Initialize database with required tables."""
        url = self.db_url
        if not url:
            print("WARNING: DATABASE_URL not set in environment.")
            return

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
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
                        id SERIAL PRIMARY KEY,
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
        url = self.db_url
        if not url:
            raise ValueError("DATABASE_URL is not set.")
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
        finally:
            conn.close()

    # --- User Management ---

    def create_user(self, username: str, password_hash: str) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                        (username, password_hash)
                    )
                conn.commit()
            return True
        except psycopg2.IntegrityError:
            return False

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE username = %s", (username,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE id = %s", (user_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    # --- Conversation Management ---

    def create_conversation(self, user_id: int, title: str, mode: str) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO conversations (user_id, title, mode) VALUES (%s, %s, %s) RETURNING id",
                    (user_id, title, mode)
                )
                row = cursor.fetchone()
                conn.commit()
                return row['id']

    def get_user_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
                    (user_id,)
                )
                return [dict(row) for row in cursor.fetchall()]

    def get_conversation(self, conversation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM conversations WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id)
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def delete_conversation_messages(self, conversation_id: int):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM chat_messages WHERE conversation_id = %s",
                    (conversation_id,)
                )
            conn.commit()
            
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                     "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                     (conversation_id, user_id)
                )
                deleted = cursor.rowcount > 0
            conn.commit()
            return deleted


    # --- Message Management ---

    def add_message(self, conversation_id: int, role: str, content: str, tokens: int):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO chat_messages (conversation_id, role, content, tokens) VALUES (%s, %s, %s, %s)",
                    (conversation_id, role, content, tokens)
                )
                cursor.execute(
                    "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (conversation_id,)
                )
            conn.commit()

    def get_messages(self, conversation_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if limit:
                    query = """
                        SELECT * FROM (
                            SELECT * FROM chat_messages 
                            WHERE conversation_id = %s 
                            ORDER BY timestamp DESC
                            LIMIT %s
                        ) AS sub ORDER BY timestamp ASC
                    """
                    cursor.execute(query, (conversation_id, limit))
                else:
                    query = "SELECT * FROM chat_messages WHERE conversation_id = %s ORDER BY timestamp ASC"
                    cursor.execute(query, (conversation_id,))
                return [dict(row) for row in cursor.fetchall()]

db = Database()
