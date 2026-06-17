import os
import re
import fnmatch
from .base import ToolHandler


class SearchHandler(ToolHandler):
    name = "search_content"
    description = "在目录中递归搜索匹配的文本（支持正则表达式）。最多返回 50 条结果。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "要搜索的文本或正则表达式"},
                "directory": {"type": "string", "description": "搜索的根目录"},
                "file_pattern": {"type": "string", "description": "文件过滤，如 *.py"},
            },
            "required": ["pattern", "directory"],
        }

    def execute(self, tool_input: dict) -> str:
        pattern = tool_input["pattern"]
        directory = tool_input["directory"]
        file_pattern = tool_input.get("file_pattern", "*")

        try:
            matches = []
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if not fnmatch.fnmatch(f, file_pattern):
                        continue
                    file_path = os.path.join(root, f)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                            for i, line in enumerate(fp, 1):
                                if re.search(pattern, line, re.IGNORECASE):
                                    rel = os.path.relpath(file_path, directory)
                                    matches.append(f"{rel}:{i}: {line.strip()[:120]}")
                                if len(matches) > 50:
                                    matches.append("... (truncated, showing first 50)")
                                    break
                    except (PermissionError, OSError):
                        continue
                    if len(matches) > 50:
                        break
            return "\n".join(matches) if matches else f"no matches for '{pattern}'"
        except Exception as e:
            return f"search error: {e}"
