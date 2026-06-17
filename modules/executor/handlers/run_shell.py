import subprocess
from .base import ToolHandler

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
        cmd = tool_input.get("command", "").lower()
        for d in DANGEROUS_COMMANDS:
            if d in cmd:
                return True, f"DANGEROUS: {tool_input['command'][:80]}"
        return False, ""

    def execute(self, tool_input: dict) -> str:
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
            return output[:8000] or "(no output)"
        except subprocess.TimeoutExpired:
            return "error: command timed out (30s)"
        except Exception as e:
            return f"error: {e}"
