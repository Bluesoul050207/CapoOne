"""
ncm_play — 网易云一键搜播
搜索走网易云API，拿originalId后cmd start唤起桌面端
支持查询净化 + 自动多试
"""

import subprocess, json, re
import urllib.request, urllib.parse
from .base import ToolHandler
from ..tool_result import ToolResult


class NcmPlayHandler(ToolHandler):
    name = "ncm_play"
    description = "搜索网易云歌曲并用桌面端播放。只需传歌名，内部自动多试+净化查询。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "歌名，如'瘦子 丁世光'"},
            },
            "required": ["query"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            return self._do_execute(tool_input)
        except Exception as e:
            return ToolResult.fail(f"ncm_play crashed: {e}", "crash")

    def _do_execute(self, tool_input: dict) -> ToolResult:
        query = tool_input["query"]
        original_query = query

        # 记忆查询
        exact_url = None
        try:
            from modules.persona.song_map import SongMapDB
            cached = SongMapDB().lookup(query)
            if cached:
                clean = cached.strip().strip('"').strip("'")
                if 2 < len(clean) <= 80 and clean != query:
                    if clean.startswith("http"):
                        exact_url = clean  # URL → 精确匹配，跳过搜索
                    else:
                        query = clean  # 歌名 → 替换后搜索
        except Exception:
            pass

        # song_map 返回了 URL → 直接播放，不搜 API（用户手动确认过的）
        if exact_url:
            _kill_netease()
            subprocess.run(f'cmd /c start "" "{exact_url}"', shell=True, timeout=10)
            return ToolResult.success(f"playing: {exact_url}")

        # 直接贴的链接 → 跳过搜索
        if original_query.startswith("http"):
            m = re.search(r'music\.163\.com/song\?id=(\d+)', original_query)
            if m:
                _kill_netease()
                music_url = f"https://music.163.com/song?id={m.group(1)}"
                subprocess.run(f'cmd /c start "" "{music_url}"', shell=True, timeout=10)
                return ToolResult.success(f"playing: {music_url}")

        # 构建多试查询列表（原始 + 净化变体）
        queries = _build_queries(query)

        # 自动多试
        for i, q in enumerate(queries):
            result = _try_search(q)
            if result is not None:
                return result

        # 全失败
        if fallback_url:
            subprocess.run(f'cmd /c start "" "{fallback_url}"', shell=True, timeout=10)
            return ToolResult.success(f"playing (fallback): {fallback_url}")
        return ToolResult.fail(
            f"所有查询均失败: {queries[:3]}。请web_search查原名。", "low_match")

    def validate(self, tool_input: dict, result: "ToolResult") -> tuple[bool, str]:
        query = tool_input.get("query", "")
        text = result.text
        if text.startswith("playing:"):
            song_part = text[8:].split("(")[0].strip()
            song_name = song_part.split(" - ")[0].strip()
            qchars = set(query.replace(" ", ""))
            schars = set(song_name.replace(" ", ""))
            if qchars and schars:
                overlap = len(qchars & schars) / max(len(qchars), 1)
                if overlap < 0.2:
                    return False, f"low_match: '{song_name}' vs '{query}'"
        return True, ""


def _try_search(query: str) -> ToolResult | None:
    """尝试一次搜索。成功返回 result，不够匹配返回 None（继续试下个）"""
    try:
        url = f"https://music.163.com/api/search/get?s={urllib.parse.quote(query)}&type=1&limit=5"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    songs = data.get("result", {}).get("songs", [])
    if not songs:
        return None

    song = songs[0]
    name = song.get("name", "?")
    qchars = set(query.replace(" ", "").lower())
    nchars = set(name.replace(" ", "").lower())
    overlap = len(qchars & nchars) / max(len(qchars), 1) if qchars else 0

    # 匹配度 ok 或短 query（可能是英文歌名）→ 播放
    if overlap >= 0.12 or len(query) < 4:
        artists = ", ".join(a.get("name", "?") for a in song.get("artists", []))
        oid = song.get("id", "")
        if oid:
            music_url = f"https://music.163.com/song?id={oid}"
            _kill_netease()
            subprocess.run(f'cmd /c start "" "{music_url}"', shell=True, timeout=10)
            return ToolResult.success(f"playing: {name} - {artists} ({music_url})")

    # 不够匹配 → 继续试下一个 query
    return None


def _build_queries(query: str) -> list[str]:
    """从原始 query 构建多个搜索尝试，去噪净化"""
    results = []
    q = query.strip()
    results.append(q)

    # 去括号/书名号（括号里的是乐队名不是歌名）
    cleaned = re.sub(r'[（(《<［\[].*?[)）》>］\]]', '', q).strip()
    if cleaned and cleaned != q:
        results.append(cleaned)

    # 只取空格前半段（通常歌名在空格前）
    if ' ' in q:
        parts = q.split()
        if len(parts[0]) >= 2:
            results.append(parts[0].strip())

    # 去特殊字符留纯文字
    plain = re.sub(r'[^\w一-鿿぀-ヿㇰ-ㇿ -]', '', q).strip()
    if plain and plain not in results:
        results.append(plain)

    return results[:3]


def _kill_netease():
    """杀掉网易云进程，解决网页桥接失效问题"""
    try:
        import subprocess
        subprocess.run('taskkill /f /im cloudmusic.exe 2>nul', shell=True, timeout=5)
    except Exception:
        pass
