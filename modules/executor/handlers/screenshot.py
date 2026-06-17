"""
screenshot — 截屏存图
"""

import time
from pathlib import Path
from .base import ToolHandler
from ..tool_result import ToolResult


class ScreenshotHandler(ToolHandler):
    name = "screenshot"
    description = "截取当前屏幕，保存为 PNG 文件。"

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import pyautogui
            img = pyautogui.screenshot()
            save_dir = Path("memory/screenshots")
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            path = save_dir / f"screen_{ts}.png"
            img.save(str(path))
            size = img.size
            return ToolResult.success(f"screenshot saved: {path} ({size[0]}x{size[1]})")
        except ImportError:
            return ToolResult.fail("pyautogui not installed")
        except Exception as e:
            return ToolResult.fail(f"screenshot failed: {e}", str(e))
