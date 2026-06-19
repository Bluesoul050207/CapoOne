"""
song_map — 歌名映射独立存储
和 persona.db 完全分离，不进入 system prompt。

用法:
  from modules.persona.song_map import SongMapDB
  db = SongMapDB()
  db.set("用户原始query", "正确歌名")
  name = db.lookup("用户原始query")
"""

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "memory" / "song_map.db"


class SongMapDB:
    """歌名映射 KV 存储：用户说的歌名 → 正确歌名/URL"""

    def __init__(self, db_path: str = str(_DB_PATH)):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_mappings_key ON mappings(key);
        """)
        self.conn.commit()

    def set(self, key: str, value: str):
        """写入或更新映射。拒绝超过 80 字的值（啰嗦说明不是歌名）。"""
        k, v = key.strip(), value.strip()
        if len(v) > 80:
            return  # 拒绝：太长的值不是歌名，是说明文字
        self.conn.execute(
            "INSERT INTO mappings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = datetime('now')",
            (k, v),
        )
        self.conn.commit()

    def get(self, key: str) -> str | None:
        """精确查询"""
        r = self.conn.execute(
            "SELECT value FROM mappings WHERE key = ?", (key.strip(),)
        ).fetchone()
        return r["value"] if r else None

    def lookup(self, query: str) -> str | None:
        """三级匹配查询：精确 → 子串 → CJK模糊"""
        if not query:
            return None
        q = query.strip()

        # 1. 精确匹配
        exact = self.get(q)
        if exact:
            return exact

        # 2. 子串包含
        rows = self.conn.execute("SELECT key, value FROM mappings").fetchall()
        for r in rows:
            k = r["key"].lower()
            ql = q.lower()
            if k in ql or ql in k:
                return r["value"]

        # 3. CJK 模糊（字符重合度）
        qchars = set(q.replace(" ", "").lower())
        if _has_cjk(q) and qchars:
            best_overlap = 0
            best_val = None
            for r in rows:
                kchars = set(r["key"].replace(" ", "").lower())
                if not kchars or len(r["key"]) < 3:
                    continue
                overlap = len(qchars & kchars) / max(len(qchars | kchars), 1)
                if overlap > 0.35 and overlap > best_overlap:
                    best_overlap = overlap
                    best_val = r["value"]
            if best_val:
                return best_val

        return None

    def list_all(self) -> list[dict]:
        """列出所有映射"""
        rows = self.conn.execute(
            "SELECT * FROM mappings ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, key: str):
        """删除一条映射"""
        self.conn.execute("DELETE FROM mappings WHERE key = ?", (key.strip(),))
        self.conn.commit()

    def close(self):
        self.conn.close()


def _has_cjk(text: str) -> bool:
    for ch in text:
        if '一' <= ch <= '鿿' or '぀' <= ch <= 'ヿ' or '가' <= ch <= '힯':
            return True
    return False
