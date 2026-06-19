"""
window_list / window_minimize — 窗口管理
Windows 原生命令实现，无需额外依赖
"""
import subprocess
from .base import ToolHandler
from ..tool_result import ToolResult


class WindowListHandler(ToolHandler):
    name = "window_list"
    description = "列出当前所有可见窗口的标题。可按关键词过滤。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "可选，按标题关键词过滤，如 'Chrome'"},
            },
            "required": [],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import sys
            if sys.platform != "win32":
                return ToolResult.fail("window_list only works on Windows")

            # PowerShell 获取窗口列表
            ps = """powershell -Command "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize | Out-String -Width 200" """
            r = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=10)
            output = r.stdout.strip()
            if not output:
                return ToolResult.success("(no visible windows)")

            filt = tool_input.get("filter", "").lower()
            if filt:
                lines = output.split("\n")
                header = "\n".join(lines[:3]) if len(lines) >= 3 else ""
                filtered = [l for l in lines if filt in l.lower()]
                output = header + "\n" + "\n".join(filtered) if filtered else f"no window matching '{filt}'"

            return ToolResult.success(output[:3000])
        except Exception as e:
            return ToolResult.fail(f"window_list failed: {e}", "window_error")


class WindowMinimizeHandler(ToolHandler):
    name = "window_minimize"
    description = "最小化指定窗口。按标题关键词匹配。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "窗口标题关键词，如 'Chrome' 或 '微信'"},
            },
            "required": ["title"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import sys
            if sys.platform != "win32":
                return ToolResult.fail("window_minimize only works on Windows")

            title = tool_input["title"]
            # PowerShell 最小化窗口
            ps = f"""powershell -Command "$ws = New-Object -ComObject Shell.Application; $ws.Windows() | Where-Object {{$_.LocationName -like '*{title}*'}} | ForEach-Object {{$_.Visible = $false}}" """
            subprocess.run(ps, shell=True, capture_output=True, timeout=10)

            # 也尝试用进程名
            ps2 = f'powershell -Command "(Get-Process *{title}* -ErrorAction SilentlyContinue).MainWindowHandle | ForEach-Object {{ $sig = \'[DllImport(\\\"user32.dll\\\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);\'; Add-Type -MemberDefinition $sig -Name Win32 -Namespace Win32; [Win32.Win32]::ShowWindow($_, 6) }}"'
            subprocess.run(ps2, shell=True, capture_output=True, timeout=10)

            return ToolResult.success(f"minimized windows matching '{title}'")
        except Exception as e:
            return ToolResult.fail(f"window_minimize failed: {e}", "window_error")
