import os
import sqlite3
from pathlib import Path
from typing import List, Dict

DB_PATH = os.getenv("DATABASE_PATH", "bot_data.sqlite3")


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id_id ON messages(user_id, id)")
    connection.commit()
    return connection


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True) if str(Path(DB_PATH).parent) != "." else None
    with connect() as connection:
        pass


def add_message(user_id: int, role: str, content: str):
    with connect() as connection:
        connection.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )


def get_history(user_id: int, limit: int = 12) -> List[Dict[str, str]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


def clear_history(user_id: int):
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


def get_stats():
    with connect() as connection:
        users = connection.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages"
        ).fetchone()[0]
        messages = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return users, messages
