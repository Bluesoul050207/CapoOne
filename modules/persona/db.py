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

    def set_memory(self, key: str, value: str, category: str = "general", target: str = "both") -> None:
        self.conn.execute(
            "INSERT INTO memories (key, value, category, target) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "category = excluded.category, target = excluded.target, updated_at = datetime('now')",
            (key, value, category, target),
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

    def build_worker_suffix(self) -> str:
        """Worker 模型 (DS/Qwen) 的 prompt 后缀：工作约束 + 用户记忆"""
        parts = []

        # 1. 工作约束
        rules = self.get_rules(rule_type="constraint", enabled_only=True)
        if rules:
            parts.append("工作约束：")
            for r in rules:
                parts.append(f"- {r['content']}")

        # 2. 用户记忆（Worker: 只读 both + worker）
        memories = self.get_all_memories()
        worker_memories = [m for m in memories
            if m.get("category","general") not in ("song","internal")
            and m.get("target","both") in ("both","worker")]
        if worker_memories:
            if parts:
                parts.append("")
            parts.append("已知信息：")
            for m in worker_memories:
                parts.append(f"- {m['key']}: {m['value']}")

        return "\n".join(parts) if parts else ""

    def build_persona_suffix(self) -> str:
        """Persona 模型 (GLM) 的 prompt 后缀：人设 + 行为风格 + 用户记忆"""
        parts = []

        # 1. 角色设定
        profile = self.get_profile()
        if profile.strip():
            parts.append(f"你是{profile}。")

        # 2. 行为风格
        rules = self.get_rules(rule_type="behavior", enabled_only=True)
        if rules:
            if parts:
                parts.append("")
            parts.append("行为风格：")
            for r in rules:
                parts.append(f"- {r['content']}")

        # 3. 用户记忆（Persona: 只读 both + persona）
        memories = self.get_all_memories()
        persona_memories = [m for m in memories
            if m.get("category","general") not in ("song","internal")
            and m.get("target","both") in ("both","persona")]
        if persona_memories:
            if parts:
                parts.append("")
            parts.append("已知信息：")
            for m in persona_memories:
                parts.append(f"- {m['key']}: {m['value']}")

        if parts:
            parts.insert(0, "")
        return "\n".join(parts)

    def build_prompt_suffix(self) -> str:
        """兼容旧代码：返回合并版"""
        worker = self.build_worker_suffix()
        persona = self.build_persona_suffix()
        parts = []
        if worker:
            parts.append(worker)
        if persona:
            parts.append(persona)
        return "\n".join(parts)

    def close(self):
        self.conn.close()


# ---- 共享记忆查询 ----

def lookup_memory(query: str, fuzzy: bool = True) -> str | None:
    """在 persona.db 中查找与 query 最匹配的记忆值。
    三级匹配：精确 key → 子串包含 → 字符重合度（中日文混用也能找到）。
    返回匹配的值，没有则返回 None。
    """
    try:
        db = PersonaDB()
        mems = db.get_all_memories()
        if not mems:
            return None

        qchars = set(query.replace(" ", "").lower())

        # 第一级：精确 key 匹配
        for m in mems:
            if m["key"].lower() == query.lower():
                return _clean_value(m["value"])

        # 第二级：子串包含匹配
        best_sub = None
        for m in mems:
            k = m["key"].lower()
            q = query.lower()
            if k in q or q in k:
                if best_sub is None:
                    best_sub = m["value"]
        if best_sub:
            return _clean_value(best_sub)

        # 第三级：字符重合度模糊匹配（仅对中日文生效，英文走精确/子串足够）
        if fuzzy and qchars and _has_cjk(query):
            best_overlap = 0
            best_val = None
            for m in mems:
                kchars = set(m["key"].replace(" ", "").lower())
                if not kchars or len(m["key"]) < 3:
                    continue
                overlap = len(qchars & kchars) / max(len(qchars | kchars), 1)  # Jaccard
                if overlap > 0.35 and overlap > best_overlap:
                    best_overlap = overlap
                    best_val = m["value"]
            if best_val:
                return _clean_value(best_val)

        return None
    except Exception:
        return None


def _has_cjk(text: str) -> bool:
    """检查文本是否包含中日韩字符"""
    for ch in text:
        if '一' <= ch <= '鿿' or '぀' <= ch <= 'ヿ' or '가' <= ch <= '힯':
            return True
    return False


def _clean_value(value: str) -> str | None:
    """清理记忆值：从说明文字中提取核心内容（歌名、URL 或简短值）"""
    if not value:
        return None
    text = value.strip()

    # 短值直接返回
    if len(text) < 200:
        return text

    # 长值：尝试提取有用信息
    import re
    # 1. 查找包含 " - " 的歌名行（如 "结束バンド - 転がる岩、君に朝が降る"）
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if " - " in line and len(line) < 150:
            return line
    # 2. 查找网易云 URL
    url_match = re.search(r'https://music\.163\.com/song\?id=\d+', text)
    if url_match:
        return url_match.group()
    # 3. 取第一行
    first_line = lines[0].strip()
    if len(first_line) < 200:
        return first_line
    return first_line[:200]


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
