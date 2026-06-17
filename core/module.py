"""
BaseModule — 所有模块的基类

模块生命周期:
  __init__() → on_init() → 运行中 → on_destroy()
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseModule(ABC):
    """模块基类。每个功能模块继承这个。"""

    # 模块元信息（子类覆盖）
    name: str = "unnamed"
    version: str = "0.1.0"
    description: str = ""

    def __init__(self):
        self._initialized = False

    # ---- 生命周期 ----

    def on_init(self, registry: "ModuleRegistry") -> None:
        """模块加载时调用。registry 是全局模块注册器，可在此获取其他模块的引用。"""
        self._initialized = True

    def on_destroy(self) -> None:
        """模块卸载时调用。清理资源。"""
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ---- 工具注册（Executor 等模块用） ----

    def register_tools(self) -> list[dict]:
        """子类覆盖，返回本模块提供的工具列表。
        每个工具是一个 dict，包含 name, description, input_schema。
        """
        return []

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """子类覆盖，执行一个工具并返回结果字符串。"""
        raise NotImplementedError(f"tool '{tool_name}' not handled by {self.name}")

    # ---- 可选的 API 消息钩子 ----

    def on_before_api_call(self, messages: list[dict]) -> list[dict]:
        """在发往 LLM 之前修改消息列表。Persona 模块用这个注入约束。"""
        return messages

    def on_build_system_prompt(self, base_prompt: str) -> str:
        """构建最终 system prompt 时调用。Persona 模块用这个拼入约束和记忆。"""
        return base_prompt
