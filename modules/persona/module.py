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

    def build_worker_prompt(self, base: str) -> str:
        """Worker 专用：base + 工作约束"""
        suffix = self.db.build_worker_suffix()
        return base + "\n" + suffix if suffix else base

    def build_persona_prompt(self) -> str:
        """Persona 专用：人设 + 行为风格 + 记忆"""
        return self.db.build_persona_suffix()

    def on_build_system_prompt(self, base_prompt: str) -> str:
        """兼容旧代码：合并版"""
        suffix = self.db.build_prompt_suffix()
        return base_prompt + suffix
