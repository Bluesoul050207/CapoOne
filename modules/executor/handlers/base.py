"""
ToolHandler — 单个工具的处理器基类
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Union


class ToolHandler(ABC):
    """一个工具 = 一个 handler 子类。
    定义工具的 schema + 执行逻辑。
    """

    # 子类覆盖
    name: str = ""
    description: str = ""

    @abstractmethod
    def input_schema(self) -> dict:
        """返回工具的 JSON Schema（Anthropic 格式）。"""
        ...

    @abstractmethod
    def execute(self, tool_input: dict) -> Union["ToolResult", str]:
        """执行工具。返回 ToolResult(ok,text,error) 或纯字符串（自动视为成功）。"""
        ...

    @staticmethod
    def to_tool_result(raw: Union["ToolResult", str]) -> "ToolResult":
        from modules.executor.tool_result import ToolResult
        return ToolResult.from_any(raw)

    def needs_confirm(self, tool_input: dict) -> tuple[bool, str]:
        """返回 (是否需要确认, 提示消息)。默认不需要。"""
        return False, ""

    def validate(self, tool_input: dict, result: "ToolResult") -> tuple[bool, str]:
        """验证工具执行结果是否真的有效。
        返回 (valid, reason)。默认总是通过。子类覆盖以实现工具特定验证。
        """
        return True, ""

    def to_tool_def(self) -> dict:
        """转为 API 格式的工具定义。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }
