"""
ModuleRegistry — 模块管理器，负责加载/卸载/查询模块

用法:
  reg = ModuleRegistry()
  reg.load(ExecutorModule())
  reg.load(PersonaModule())
  reg.init_all()
  ...
  reg.destroy_all()
"""

from __future__ import annotations
from typing import TypeVar

from .module import BaseModule

M = TypeVar("M", bound=BaseModule)


class ModuleRegistry:
    """全局模块注册器。整个应用只有一个实例。"""

    def __init__(self):
        self._modules: dict[str, BaseModule] = {}
        self._initialized = False

    # ---- 加载/卸载 ----

    def load(self, module: BaseModule) -> None:
        """加载一个模块。同名模块会被替换。"""
        if module.name in self._modules:
            old = self._modules[module.name]
            old.on_destroy()
        self._modules[module.name] = module
        if self._initialized:
            module.on_init(self)

    def unload(self, name: str) -> None:
        """卸载一个模块。"""
        if name in self._modules:
            self._modules[name].on_destroy()
            del self._modules[name]

    def init_all(self) -> None:
        """初始化所有已加载的模块。应用启动时调用一次。"""
        self._initialized = True
        for mod in self._modules.values():
            if not mod.is_initialized:
                mod.on_init(self)

    def destroy_all(self) -> None:
        """销毁所有模块。应用退出时调用一次。"""
        for mod in reversed(list(self._modules.values())):
            mod.on_destroy()
        self._modules.clear()
        self._initialized = False

    # ---- 查询 ----

    def get(self, name: str) -> BaseModule | None:
        """按名称获取模块。"""
        return self._modules.get(name)

    def require(self, name: str) -> BaseModule:
        """按名称获取模块，不存在就抛异常。"""
        mod = self.get(name)
        if mod is None:
            raise KeyError(f"module '{name}' not loaded")
        return mod

    def list(self) -> list[str]:
        """列出所有已加载模块的名称。"""
        return list(self._modules.keys())

    # ---- 聚合操作（跨模块） ----

    def all_tools(self) -> list[dict]:
        """收集所有模块注册的工具，合并为一个列表。"""
        tools = []
        for mod in self._modules.values():
            tools.extend(mod.register_tools())
        return tools

    def execute_tool(self, tool_name: str, tool_input: dict) -> "ToolResult":
        """遍历所有模块，找到能处理该工具的模块并执行。"""
        from modules.executor.tool_result import ToolResult
        for mod in self._modules.values():
            try:
                raw = mod.execute_tool(tool_name, tool_input)
                return ToolResult.from_any(raw)
            except NotImplementedError:
                continue
        return ToolResult(ok=False, text=f"unknown tool: {tool_name}", error="unknown_tool")

    def validate_tool(self, tool_name: str, tool_input: dict, result: "ToolResult") -> tuple[bool, str]:
        """执行工具结果验证。遍历所有模块找到对应 handler 并调用 validate()。"""
        for mod in self._modules.values():
            if hasattr(mod, 'handlers') and tool_name in mod.handlers:
                handler = mod.handlers[tool_name]
                if hasattr(handler, 'validate'):
                    return handler.validate(tool_input, result)
        return True, ""

    def build_system_prompt(self, base: str) -> str:
        """依次调用每个模块的 on_build_system_prompt 钩子。"""
        prompt = base
        for mod in self._modules.values():
            prompt = mod.on_build_system_prompt(prompt)
        return prompt
