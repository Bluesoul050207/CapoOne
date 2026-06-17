"""
PersonaModule — AI 人格模块，管理长期记忆和行为约束
启动时自动建库 + 写入默认规则（如果首次运行）
"""

from core.module import BaseModule
from core.logger import get_logger
from .db import PersonaDB


class PersonaModule(BaseModule):
    name = "persona"
    version = "0.2.0"
    description = "AI personality: rules, constraints, long-term memory via SQLite"

    def __init__(self, db_path: str = "memory/persona.db"):
        super().__init__()
        self.db = PersonaDB(db_path)

    def on_init(self, registry) -> None:
        super().on_init(registry)
        get_logger().lifecycle(self.name, "init")

    def on_destroy(self) -> None:
        self.db.close()
        get_logger().lifecycle(self.name, "destroy")
        super().on_destroy()

    def on_build_system_prompt(self, base_prompt: str) -> str:
        """在基础 system prompt 后面拼入规则和记忆。"""
        suffix = self.db.build_prompt_suffix()
        return base_prompt + suffix
