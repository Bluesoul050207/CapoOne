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
            return ToolResult.fail(f"API search failed: {e}")

        # 2. 解析
        songs = data.get("result", {}).get("songs", [])
        if not songs:
            return ToolResult.fail(f"no results for: {query}")
        song = songs[0]
        name = song.get("name", "?")
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
