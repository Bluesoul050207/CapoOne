"""
app_map — 应用别名映射，process_start 启动前自动查
存 memory/app_map.json，你手动编辑即可
"""
import json
from pathlib import Path

_MAP_PATH = Path(__file__).parent.parent.parent.parent / "memory" / "app_map.json"


def load_map() -> dict:
    """加载别名→路径映射"""
    if _MAP_PATH.exists():
        try:
            return json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def lookup(name: str) -> str | None:
    """查找别名对应的路径。大小写不敏感。"""
    m = load_map()
    key = name.lower().strip()
    # 精确匹配
    if key in m:
        return m[key]
    # 子串匹配
    for k, v in m.items():
        if k in key or key in k:
            return v
    return None
