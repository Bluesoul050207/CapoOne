"""
save_rule / save_memory — 对话中自动记住用户偏好
Lain 听到"以后……"时主动调用，写入 persona.db 永久生效
"""

import sys, os
from pathlib import Path
from .base import ToolHandler
from ..tool_result import ToolResult

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.persona.db import PersonaDB


class SaveRuleHandler(ToolHandler):
    name = "save_rule"
    description = "永久保存一条行为规则到人格系统。当用户说'以后…''每次…''记住…'时调用。"

    def needs_confirm(self, tool_input: dict) -> tuple[bool, str]:
        return True, f"save rule: {tool_input.get('content', '?')[:80]}"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "规则内容，如'用户说xx时回复oo'"},
                "rule_type": {"type": "string", "description": "constraint 约束 或 behavior 行为"},
            },
            "required": ["content"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        content = tool_input["content"]
        rule_type = tool_input.get("rule_type", "behavior")
        try:
            db = PersonaDB()
            # 冲突检测：查重已有规则
            existing = db.get_rules(enabled_only=False)
            for r in existing:
                if content.strip() == r["content"].strip():
                    return ToolResult.success(f"rule already exists as #{r['id']}: {content}")
            rid = db.add_rule(content, rule_type, 5)
            return ToolResult.success(f"rule #{rid} saved: {content}")
        except Exception as e:
            return ToolResult.fail(f"save_rule failed: {e}", "db_error")


class SaveMemoryHandler(ToolHandler):
    name = "save_memory"
    description = "永久保存一条事实记忆。当用户说'记住xxx是yyy'时调用。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "记忆标签"},
                "value": {"type": "string", "description": "记忆内容"},
            },
            "required": ["key", "value"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        key = tool_input["key"]
        value = tool_input["value"]

        # 关键词检测：只在用户明确说"记住"类词语时才真写
        trigger_words = ["记住", "记下来", "别忘了", "以后记住了", "存一下", "记着", "keep in mind", "remember"]
        user_said_remember = False
        try:
            from .temp_rule import _get_current_conv
            conv = _get_current_conv()
            if conv:
                for m in reversed(conv.messages):
                    if m["role"] == "user" and isinstance(m.get("content"), str):
                        if any(w in m["content"] for w in trigger_words):
                            user_said_remember = True
                        break
        except Exception:
            user_said_remember = True  # 拿不到对话就放行

        if not user_said_remember:
            return ToolResult.success(f"(not saved — 用户没说要记住)")

        try:
            db = PersonaDB()
            old = db.get_memory(key)
            if old:
                old_val = old["value"]
                if value.strip() not in old_val:
                    value = old_val + "\n" + value
            db.set_memory(key, value)
            if old:
                return ToolResult.success(f"memory updated: {key}")
            return ToolResult.success(f"memory saved: {key}")
        except Exception as e:
            return ToolResult.fail(f"save_memory failed: {e}", "db_error")
