from pathlib import Path
from .base import ToolHandler
from ..tool_result import ToolResult


class WriteFileHandler(ToolHandler):
    name = "write_file"
    description = "写入文件（创建或覆盖）。需要用户确认。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件的绝对路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["file_path", "content"],
        }

    def needs_confirm(self, tool_input: dict) -> tuple[bool, str]:
        return True, f"write: {tool_input.get('file_path', '?')}"

    def execute(self, tool_input: dict) -> ToolResult:
        file_path = tool_input["file_path"]
        content = tool_input["content"]

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.success(f"wrote {file_path} ({len(content)} chars)")
        except PermissionError:
            return ToolResult.fail(f"write permission denied: {file_path}", "access_denied")
        except Exception as e:
            return ToolResult.fail(f"write failed: {e}", "write_error")

    def validate(self, tool_input: dict, result: "ToolResult") -> tuple[bool, str]:
        """验证文件确实被写入"""
        if result.ok:
            file_path = tool_input.get("file_path", "")
            if file_path:
                from pathlib import Path
                if not Path(file_path).exists():
                    return False, "file_not_created"
                if Path(file_path).stat().st_size == 0:
                    return False, "file_empty"
        return True, ""
