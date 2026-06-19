"""
move_file — 文件移动/重命名/复制
"""
import shutil
from pathlib import Path
from .base import ToolHandler
from ..tool_result import ToolResult


class MoveFileHandler(ToolHandler):
    name = "move_file"
    description = "移动或重命名文件/文件夹。可跨目录移动，自动创建目标目录。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹的绝对路径"},
                "destination": {"type": "string", "description": "目标路径。同目录不同名=重命名，不同目录=移动"},
            },
            "required": ["source", "destination"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        src = tool_input["source"]
        dst = tool_input["destination"]

        try:
            src_path = Path(src)
            if not src_path.exists():
                return ToolResult.fail(f"source not found: {src}", "file_not_found")

            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst))

            action = "renamed" if src_path.parent == Path(dst).parent else "moved"
            return ToolResult.success(f"{action}: {src} -> {dst}")
        except PermissionError:
            return ToolResult.fail(f"permission denied: {src}", "access_denied")
        except Exception as e:
            return ToolResult.fail(f"move failed: {e}", "move_error")
