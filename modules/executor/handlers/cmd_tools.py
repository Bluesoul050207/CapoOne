"""
cmd_help / cmd_run — CLI 注册表查询和执行
Agent 通过这两个工具发现和调用所有命令行接口
"""

import json, subprocess
from pathlib import Path
from .base import ToolHandler
from ..tool_result import ToolResult

_REGISTRY_PATH = Path(__file__).parent.parent.parent.parent / "cli_registry.json"


def _load_registry() -> dict:
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class CmdHelpHandler(ToolHandler):
    name = "cmd_help"
    description = "查看可用的 CLI 命令。传 'all' 列出所有类别，传 'music' 看音乐相关命令。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "类别名，如 'music' 'system' 'web'，或 'all'"},
            },
            "required": [],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            reg = _load_registry()
            category = tool_input.get("category", "all")

            if category == "all":
                lines = []
                for cat_key, cat_val in reg.items():
                    name = cat_val.get("name", cat_key)
                    cmds = self._list_commands(cat_val)
                    lines.append(f"## {name} ({cat_key})")
                    for c in cmds:
                        lines.append(f"  {c}")
                return ToolResult.success("\n".join(lines))

            cat = reg.get(category)
            if not cat:
                cats = ", ".join(reg.keys())
                return ToolResult.fail(f"unknown category '{category}'. Available: {cats}")

            lines = [f"## {cat.get('name', category)}"]
            if "install" in cat:
                lines.append(f"  安装: {cat['install']}")
            for c in self._list_commands(cat):
                lines.append(f"  {c}")
            return ToolResult.success("\n".join(lines))
        except Exception as e:
            return ToolResult.fail(f"cmd_help error: {e}")

    def _list_commands(self, cat_val: dict, prefix: str = "") -> list[str]:
        lines = []
        # 有 commands 键 → 直接列出
        if "commands" in cat_val:
            for cmd_name, cmd_info in cat_val["commands"].items():
                key = f"{prefix}.{cmd_name}" if prefix else cmd_name
                if isinstance(cmd_info, dict):
                    lines.append(f"  {key}: {cmd_info.get('desc','')}  [{cmd_info.get('cmd','')[:80]}]")
                else:
                    lines.append(f"  {key}: {cmd_info}")
        # 有子类别 → 递归
        for key, val in cat_val.items():
            if key in ("commands", "name", "binary", "install", "requires"):
                continue
            if isinstance(val, dict):
                name = val.get("name", key)
                sub_prefix = f"{prefix}.{key}" if prefix else key
                lines.append(f"  [{name}]")
                lines.extend(self._list_commands(val, sub_prefix))
        return lines


class CmdRunHandler(ToolHandler):
    name = "cmd_run"
    description = "执行 CLI 注册表中的命令。格式: category.command_name，如 'music.netease.search'"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "命令路径，如 'music.netease.search'"},
                "params": {"type": "string", "description": "JSON 格式的参数，如 '{\"query\":\"瘦子\"}'"},
            },
            "required": ["path"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            reg = _load_registry()
            path = tool_input["path"]
            parts = path.split(".")

            # 参数解析
            params = {}
            params_str = tool_input.get("params", "{}")
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                pass

            # 导航到命令定义
            node = reg
            for part in parts:
                if isinstance(node, dict):
                    if part in node:
                        node = node[part]
                    elif "commands" in node and part in node["commands"]:
                        node = node["commands"][part]
                    else:
                        return ToolResult.fail(f"path '{path}' not found at '{part}'")
                else:
                    return ToolResult.fail(f"invalid path: {path}")

            if not isinstance(node, dict) or "cmd" not in node:
                return ToolResult.fail(f"no executable command at '{path}': {node}")

            cmd_template = node["cmd"]
            # 填参数
            for k, v in params.items():
                cmd_template = cmd_template.replace(f"{{{k}}}", str(v))

            print(f"  [cmd] {cmd_template}", flush=True)
            result = subprocess.run(
                cmd_template, shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
            output = result.stdout.strip()
            if result.stderr:
                output += f"\n[stderr] {result.stderr.strip()}"
            if result.returncode != 0:
                output += f"\n[exit: {result.returncode}]"

            return ToolResult.success(output[:2000] or "(no output)")
        except subprocess.TimeoutExpired:
            return ToolResult.fail("command timed out (30s)")
        except Exception as e:
            return ToolResult.fail(f"cmd_run error: {e}")
