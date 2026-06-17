from .base import ToolHandler


class ReadFileHandler(ToolHandler):
    name = "read_file"
    description = "读取文件内容，返回带行号的结果。可指定起始行和行数。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件的绝对路径"},
                "offset": {"type": "integer", "description": "起始行号，默认 0"},
                "limit": {"type": "integer", "description": "读取行数，默认 100"},
            },
            "required": ["file_path"],
        }

    def execute(self, tool_input: dict) -> str:
        file_path = tool_input["file_path"]
        offset = int(tool_input.get("offset", 0))
        limit = int(tool_input.get("limit", 100))

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            result = "".join(f"{offset + i + 1:4d}| {line}" for i, line in enumerate(selected))
            if offset + limit < total:
                result += f"\n... ({total - offset - limit} more lines)"
            return result or "(empty)"
        except FileNotFoundError:
            return f"file not found: {file_path}"
        except PermissionError:
            return f"permission denied: {file_path}"
        except Exception as e:
            return f"error: {e}"
