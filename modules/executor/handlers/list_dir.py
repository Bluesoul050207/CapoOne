import os
import fnmatch
from pathlib import Path
from datetime import datetime
from .base import ToolHandler


class ListDirHandler(ToolHandler):
    name = "list_directory"
    description = "列出目录中的文件和子目录，可按文件名模式过滤。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径，默认当前工作目录"},
                "pattern": {"type": "string", "description": "可选的 glob 模式，如 *.py"},
            },
            "required": [],
        }

    def execute(self, tool_input: dict) -> str:
        path = tool_input.get("path", os.getcwd())
        pattern = tool_input.get("pattern", "*")

        try:
            entries = sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            if pattern != "*":
                entries = [e for e in entries if fnmatch.fnmatch(e.name, pattern)]

            lines = []
            for e in entries:
                tag = "[D]" if e.is_dir() else "[F]"
                try:
                    size = e.stat().st_size
                    mtime = datetime.fromtimestamp(e.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    size = 0
                    mtime = "?"
                name = f"{e.name}/" if e.is_dir() else e.name
                lines.append(f"{tag} {name}  ({size:>8,} bytes, {mtime})")
            return "\n".join(lines) if lines else "(empty)"
        except Exception as e:
            return f"error: {e}"
