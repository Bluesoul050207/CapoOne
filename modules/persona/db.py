"""
PersonaDB — SQLite 数据库，存 AI 的约束、偏好和长期记忆

两张表:
  rules    — 行为约束（"禁止 emoji"、"用中文回复" 等）
  memories — 长期记忆（"用户是机械革命笔记本"、"项目在 D:\agent" 等）
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime


_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
DEFAULT_DB_PATH = str(_PROJECT_ROOT / "memory" / "persona.db")


class PersonaDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                content TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO profile (id, content) VALUES (1, '');
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL DEFAULT 'constraint',
                content TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type, enabled);
            CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
        """)
        self.conn.commit()

    # ---- Profile ----

    def get_profile(self) -> str:
        r = self.conn.execute("SELECT content FROM profile WHERE id = 1").fetchone()
        return r[0] if r else ""

    def set_profile(self, content: str):
        self.conn.execute("UPDATE profile SET content = ? WHERE id = 1", (content,))
        self.conn.commit()

    # ---- Rules ----

    def add_rule(self, content: str, rule_type: str = "constraint", priority: int = 0) -> int:
        c = self.conn.execute(
            "INSERT INTO rules (rule_type, content, priority) VALUES (?, ?, ?)",
            (rule_type, content, priority),
        )
        self.conn.commit()
        return c.lastrowid

    def get_rules(self, rule_type: str = None, enabled_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM rules"
        conds = []
        params = []
        if enabled_only:
            conds.append("enabled = 1")
        if rule_type:
            conds.append("rule_type = ?")
            params.append(rule_type)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY priority DESC, id ASC"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def update_rule(self, rule_id: int, **kwargs) -> None:
        allowed = {"content", "rule_type", "priority", "enabled"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)
        if sets:
            sets.append("updated_at = datetime('now')")
            params.append(rule_id)
            self.conn.execute(f"UPDATE rules SET {', '.join(sets)} WHERE id = ?", params)
            self.conn.commit()

    def delete_rule(self, rule_id: int) -> None:
        self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self.conn.commit()

    # ---- Memories ----

    def set_memory(self, key: str, value: str, category: str = "general") -> None:
        self.conn.execute(
            "INSERT INTO memories (key, value, category) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "category = excluded.category, updated_at = datetime('now')",
            (key, value, category),
        )
        self.conn.commit()

    def get_memory(self, key: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchone()
        return dict(r) if r else None

    def get_all_memories(self, category: str = None) -> list[dict]:
        if category:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY key", (category,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM memories ORDER BY key").fetchall()
        return [dict(r) for r in rows]

    def delete_memory(self, key: str) -> None:
        self.conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        self.conn.commit()

    # ---- System Prompt 拼接 ----

    def build_prompt_suffix(self) -> str:
        """拼出追加到 system prompt 的内容：设定 > 约束 > 记忆"""
        parts = []

        # 1. 角色设定（最高优先级，非列表，直接陈述）
        profile = self.get_profile()
        if profile.strip():
            parts.append(f"你是{profile}。")

        # 2. 行为约束
        rules = self.get_rules(enabled_only=True)
        if rules:
            if parts:
                parts.append("")
            parts.append("行为约束：")
            for r in rules:
                parts.append(f"- {r['content']}")

        # 3. 已知信息
        memories = self.get_all_memories()
        if memories:
            if parts:
                parts.append("")
            parts.append("已知信息：")
            for m in memories:
                parts.append(f"- {m['key']}: {m['value']}")

        if parts:
            parts.insert(0, "")
        return "\n".join(parts)

    def close(self):
        self.conn.close()


# ---- 共享记忆查询 ----

def lookup_memory(query: str) -> str | None:
    """在 persona.db 中查找与 query 最匹配的记忆值。
    优先精确 key 匹配 → 子串匹配。
    返回匹配的值，没有则返回 None。
    """
    try:
        db = PersonaDB()
        mems = db.get_all_memories()
        best = None
        for m in mems:
            if m["key"] == query:
                return m["value"]
            if m["key"] in query or query in m["key"]:
                if best is None:
                    best = m["value"]
        return best
    except Exception:
        return None


# ---- 默认初始化 ----

def init_default_rules(db: PersonaDB):
    """首次运行时写入默认规则"""
    defaults = [
        ("constraint", "禁止使用任何 emoji 表情符号。这是硬性规则。", 10),
        ("constraint", "回复直接、简短、不装。像和同事说话一样。", 5),
        ("constraint", "手里有工具就自己动手，别让用户去干你能做的事。", 5),
        ("behavior", "用户发什么就干什么，干完给结果，别废话。", 3),
        ("behavior", "做错了就认，不知道就说不知道。", 3),
    ]
    existing = db.get_rules(enabled_only=False)
    if not existing:
        for rtype, content, priority in defaults:
            db.add_rule(content, rtype, priority)
