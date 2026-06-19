import subprocess
from .base import ToolHandler
from ..tool_result import ToolResult

DANGEROUS_COMMANDS = ["rm -rf", "del /f", "format", "shutdown", "restart", "reg delete", ":(){ :|:& };:"]


class RunShellHandler(ToolHandler):
    name = "run_shell"
    description = "执行 shell 命令并返回输出。危险命令会请求确认。30 秒超时。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "description": {"type": "string", "description": "对命令用途的简短描述"},
            },
            "required": ["command"],
        }

    def needs_confirm(self, tool_input: dict) -> tuple[bool, str]:
        cmd = tool_input.get("command", "")
        # 规范化：去多余空格、统一小写
        import re
        normalized = re.sub(r'\s+', ' ', cmd).lower()
        for d in DANGEROUS_COMMANDS:
            d_norm = re.sub(r'\s+', ' ', d).lower()
            if d_norm in normalized:
                return True, f"DANGEROUS: {cmd[:80]}"
        return False, ""

    def execute(self, tool_input: dict) -> ToolResult:
        command = tool_input["command"]

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
                cwd=subprocess.os.getcwd(),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit: {result.returncode}]"
            # exit != 0 视为失败
            if result.returncode != 0:
                return ToolResult.fail(output[:8000] or "(no output)", "command_failed")
            return ToolResult.success(output[:8000] or "(no output)")
        except subprocess.TimeoutExpired:
            return ToolResult.fail("error: command timed out (30s)", "timeout")
        except Exception as e:
            return ToolResult.fail(f"shell error: {e}", "shell_error")
