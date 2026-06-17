"""
clipboard_read / clipboard_write — 剪贴板读写
Agent 和应用之间传数据的桥梁
"""

from .base import ToolHandler
from ..tool_result import ToolResult


class ClipboardReadHandler(ToolHandler):
    name = "clipboard_read"
    description = "读取剪贴板中的文本内容。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import pyperclip
            text = pyperclip.paste()
            if not text:
                return ToolResult.success("(clipboard empty)")
            return ToolResult.success(text)
        except Exception as e:
            return ToolResult.fail(f"clipboard read failed: {e}", str(e))


class ClipboardWriteHandler(ToolHandler):
    name = "clipboard_write"
    description = "将文本写入剪贴板。写完后用户可以 Ctrl+V 粘贴。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要写入剪贴板的文本"},
            },
            "required": ["text"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        text = tool_input["text"]
        try:
            import pyperclip
            pyperclip.copy(text)
            return ToolResult.success(f"copied to clipboard ({len(text)} chars)")
        except Exception as e:
            return ToolResult.fail(f"clipboard write failed: {e}", str(e))
