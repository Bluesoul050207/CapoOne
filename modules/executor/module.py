"""
ExecutorModule — 执行器模块，负责所有电脑操作
"""

from __future__ import annotations
import time
from core.module import BaseModule
from core.logger import get_logger
from .handlers import ALL_HANDLERS
from .tool_result import ToolResult


class ExecutorModule(BaseModule):
    name = "executor"
    version = "0.2.0"
    description = "Computer operations: read/write files, list dirs, run shell commands, search content"

    def __init__(self):
        super().__init__()
        self.handlers: dict[str, object] = {}

    def on_init(self, registry) -> None:
        super().on_init(registry)
        # 实例化所有工具 handler
        for cls in ALL_HANDLERS:
            inst = cls()
            self.handlers[inst.name] = inst
        get_logger().lifecycle(self.name, "init")

    def on_destroy(self) -> None:
        self.handlers.clear()
        get_logger().lifecycle(self.name, "destroy")
        super().on_destroy()

    # ---- 工具注册 ----

    def register_tools(self) -> list[dict]:
        return [h.to_tool_def() for h in self.handlers.values()]

    def execute_tool(self, tool_name: str, tool_input: dict) -> "ToolResult":
        handler = self.handlers.get(tool_name)
        if handler is None:
            raise NotImplementedError(f"executor doesn't handle '{tool_name}'")

        t0 = time.time()
        raw = handler.execute(tool_input)
        tr = handler.to_tool_result(raw)
        elapsed = (time.time() - t0) * 1000

        get_logger().tool_call(tool_name, tool_input, tr.text, elapsed)
        return tr

    def needs_confirm(self, tool_name: str, tool_input: dict) -> tuple[bool, str]:
        handler = self.handlers.get(tool_name)
        if handler:
            return handler.needs_confirm(tool_input)
        return False, ""
