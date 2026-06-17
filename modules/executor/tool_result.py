"""
ToolResult — 工具执行的统一返回类型
所有 handler 返回 str 或 ToolResult，ExecutorModule 自动归一化
"""

from __future__ import annotations
from typing import Union


class ToolResult:
    """工具执行结果：ok 标识成败，text 给 LLM，error 给人看"""
    __slots__ = ("ok", "text", "error")

    def __init__(self, ok: bool, text: str = "", error: str | None = None):
        self.ok = ok
        self.text = text
        self.error = error

    @classmethod
    def success(cls, text: str) -> "ToolResult":
        return cls(True, text)

    @classmethod
    def fail(cls, text: str, error: str | None = None) -> "ToolResult":
        return cls(False, text, error)

    @staticmethod
    def from_any(result: "ToolResult | str") -> "ToolResult":
        """归一化：str 自动转 ok=True"""
        if isinstance(result, ToolResult):
            return result
        return ToolResult(ok=True, text=str(result))

    def __str__(self):
        return self.text

    def __bool__(self):
        return self.ok


ToolResultLike = Union[ToolResult, str]
