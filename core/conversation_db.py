"""
ConversationDB — 对话持久化，关了重开接着聊

表:
  sessions — 会话列表
  messages — 消息记录（JSON 存储）
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = "memory/conversation.db"


class ConversationDB:
    def __init__(self, db_path: str = DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, id);
        """)
        self.conn.commit()

    # ---- Sessions ----

    def create_session(self, name: str = None) -> int:
        name = name or datetime.now().strftime("%m-%d %H:%M")
        c = self.conn.execute("INSERT INTO sessions (name) VALUES (?)", (name,))
        self.conn.commit()
        return c.lastrowid

    def list_sessions(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.*, COUNT(m.id) as msg_count FROM sessions s "
            "LEFT JOIN messages m ON s.id = m.session_id "
            "GROUP BY s.id ORDER BY s.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, sid: int):
        self.conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        self.conn.commit()

    def touch_session(self, sid: int):
        self.conn.execute("UPDATE sessions SET updated_at = datetime('now') WHERE id = ?", (sid,))
        self.conn.commit()

    # ---- Messages ----

    def save_message(self, sid: int, role: str, content: str):
        # 清理非法 Unicode 代理字符
        clean = content.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (sid, role, clean),
        )
        self.touch_session(sid)
        self.conn.commit()

    def load_messages(self, sid: int, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id LIMIT ?",
            (sid, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()


# 全局单例
_db: ConversationDB | None = None


def get_conv_db() -> ConversationDB:
    global _db
    if _db is None:
        _db = ConversationDB()
    return _db
