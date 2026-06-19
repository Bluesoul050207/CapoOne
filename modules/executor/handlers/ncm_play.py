"""
ncm_play — 网易云一键搜播
搜索走网易云API，拿originalId后cmd start唤起桌面端
"""

import subprocess, json
import urllib.request, urllib.parse
from .base import ToolHandler
from ..tool_result import ToolResult


class NcmPlayHandler(ToolHandler):
    name = "ncm_play"
    description = "搜索网易云歌曲并用桌面端播放。只需传歌名，内部完成搜索→播放。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "歌名，如'瘦子 丁世光'"},
            },
            "required": ["query"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        query = tool_input["query"]

        # 记忆查询：查 song_map.db 中是否有歌名映射
        # URL 映射：保留原始 query 搜 API，URL 作为兜底
        fallback_url = None
        original_query = query
        try:
            from modules.persona.song_map import SongMapDB
            cached = SongMapDB().lookup(query)
            if cached:
                clean = cached.strip()
                if 2 < len(clean) <= 80 and clean != query:
                    if clean.startswith("http"):
                        fallback_url = clean  # URL 作兜底，不替 query
                    else:
                        query = clean  # 歌名直接替换
        except Exception:
            pass

        # 0. 如果原始 query 是网易云链接（直接贴的）→ 信任，跳过搜索
        import re
        if original_query.startswith("http"):
            url_match = re.search(r'music\.163\.com/song\?id=(\d+)', original_query)
            if url_match:
                oid = url_match.group(1)
                music_url = f"https://music.163.com/song?id={oid}"
                subprocess.run(f'cmd /c start "" "{music_url}"', shell=True, timeout=10)
                return ToolResult.success(f"playing: {music_url}")

        # 1. 搜索 — 网易云公开搜索API
        try:
            url = f"https://music.163.com/api/search/get?s={urllib.parse.quote(query)}&type=1&limit=5"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://music.163.com",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if fallback_url:
                subprocess.run(f'cmd /c start "" "{fallback_url}"', shell=True, timeout=10)
                return ToolResult.success(f"playing (fallback): {fallback_url}")
            return ToolResult.fail(f"API search failed: {e}")

        # 2. 解析 + 匹配度检查
        songs = data.get("result", {}).get("songs", [])
        if not songs:
            if fallback_url:
                subprocess.run(f'cmd /c start "" "{fallback_url}"', shell=True, timeout=10)
                return ToolResult.success(f"playing (fallback): {fallback_url}")
            return ToolResult.fail(f"no results for: {query} — 可能是翻译名或拼写不对，试试web_search查原名")
        song = songs[0]
        name = song.get("name", "?")

        # 相似度：歌名和查询的关键字重合度
        qchars = set(query.replace(" ", ""))
        nchars = set(name.replace(" ", ""))
        overlap = len(qchars & nchars) / max(len(qchars), 1)
        if overlap < 0.15 and len(query) >= 4:
            if fallback_url:
                subprocess.run(f'cmd /c start "" "{fallback_url}"', shell=True, timeout=10)
                return ToolResult.success(f"playing (fallback): {fallback_url}")
            artists = ", ".join(a.get("name", "?") for a in song.get("artists", []))
            return ToolResult.fail(
                f"最佳匹配'{name} - {artists}'与'{query}'重合度仅{int(overlap*100)}%。可能是翻译名，请web_search查原名后重新ncm_play。",
                "low_match"
            )
        artists = ", ".join(a.get("name", "?") for a in song.get("artists", []))
        oid = song.get("id", "")

        if not oid:
            return ToolResult.fail("no song id")

        # 3. 唤起桌面
        music_url = f"https://music.163.com/song?id={oid}"
        subprocess.run(
            f'cmd /c start "" "{music_url}"',
            shell=True, timeout=10,
        )

        return ToolResult.success(f"playing: {name} - {artists} ({music_url})")

    def validate(self, tool_input: dict, result: "ToolResult") -> tuple[bool, str]:
        """验证播放的歌名和用户搜的是否匹配"""
        query = tool_input.get("query", "")
        text = result.text
        # 从结果中提取歌名
        if text.startswith("playing:"):
            song_part = text[8:].split("(")[0].strip()  # "晴天 - 周杰伦"
            song_name = song_part.split(" - ")[0].strip()
            qchars = set(query.replace(" ", ""))
            schars = set(song_name.replace(" ", ""))
            if qchars and schars:
                overlap = len(qchars & schars) / max(len(qchars), 1)
                if overlap < 0.2:
                    return False, f"low_match: '{song_name}' vs '{query}' overlap={int(overlap*100)}%"
        return True, ""
