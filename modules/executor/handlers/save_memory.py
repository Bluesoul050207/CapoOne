"""
save_rule / save_memory — 对话中自动记住用户偏好
Lain 听到"以后……"时主动调用，写入 persona.db 永久生效
"""

import sys, os
from pathlib import Path
from .base import ToolHandler

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from modules.persona.db import PersonaDB


class SaveRuleHandler(ToolHandler):
    name = "save_rule"
    description = "永久保存一条行为规则到人格系统。当用户说'以后…''每次…''记住…'时调用。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "规则内容，如'用户说xx时回复oo'"},
                "rule_type": {"type": "string", "description": "constraint 约束 或 behavior 行为"},
            },
            "required": ["content"],
        }

    def execute(self, tool_input: dict) -> str:
        content = tool_input["content"]
        rule_type = tool_input.get("rule_type", "behavior")
        db = PersonaDB()
        rid = db.add_rule(content, rule_type, 5)
        return f"rule #{rid} saved: {content}"


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

    def execute(self, tool_input: dict) -> str:
        key = tool_input["key"]
        value = tool_input["value"]
        db = PersonaDB()
        db.set_memory(key, value)
        return f"memory saved: {key} = {value}"
