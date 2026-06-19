"""
quick_note — 快捷备忘，追加到 notes.md
"""
from pathlib import Path
from datetime import datetime
from .base import ToolHandler
from ..tool_result import ToolResult


class QuickNoteHandler(ToolHandler):
    name = "quick_note"
    description = "快速记录一条备忘，追加到 memory/notes.md。自动带时间戳。可用于记灵感、TODO、提醒。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "备忘内容"},
            },
            "required": ["content"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        content = tool_input["content"]
        try:
            note_dir = Path(__file__).parent.parent.parent.parent / "memory"
            note_dir.mkdir(parents=True, exist_ok=True)
            note_path = note_dir / "notes.md"

            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"\n## {ts}\n{content}\n"

            with open(note_path, "a", encoding="utf-8") as f:
                f.write(entry)

            return ToolResult.success(f"noted: {content[:100]}")
        except Exception as e:
            return ToolResult.fail(f"note failed: {e}", "write_error")
