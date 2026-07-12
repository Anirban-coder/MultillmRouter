"""
Stores conversation history per session_id in a local SQLite file.
This is what makes failover "seamless" — when we switch providers,
we replay this exact history into the new provider's call.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sessions.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            messages TEXT NOT NULL
        )
    """)
    return conn


def get_history(session_id: str) -> list[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT messages FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []


def save_history(session_id: str, messages: list[dict]):
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO sessions (session_id, messages) VALUES (?, ?)
        ON CONFLICT(session_id) DO UPDATE SET messages = excluded.messages
        """,
        (session_id, json.dumps(messages)),
    )
    conn.commit()
    conn.close()


def append_message(session_id: str, role: str, content: str) -> list[dict]:
    history = get_history(session_id)
    history.append({"role": role, "content": content})
    save_history(session_id, history)
    return history
