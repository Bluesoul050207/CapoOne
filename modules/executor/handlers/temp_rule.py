"""
temp_rule — 对话内临时规则，会话结束自动忘，不写 DB
"""
from .base import ToolHandler
from ..tool_result import ToolResult


class TempRuleHandler(ToolHandler):
    name = "temp_rule"
    description = "设置仅本次对话生效的临时工作规则。放完后告诉模型'这次就这样，下次不用记住'时调用。不写数据库。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "本次对话中需要遵守的临时规则"},
            },
            "required": ["content"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        content = tool_input["content"]
        # 存到当前对话的 temp_rules 列表
        conv = _get_current_conv()
        if conv is not None:
            conv.temp_rules.append(content)
        return ToolResult.success(f"temp rule set: {content}")


# 线程局部的当前对话引用
_conv = None


def set_current_conv(conv):
    global _conv
    _conv = conv


def _get_current_conv():
    return _conv
