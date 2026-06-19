"""
process_list / process_kill / process_start — 进程管理
"""

import subprocess
from .base import ToolHandler
from ..tool_result import ToolResult


class ProcessListHandler(ToolHandler):
    name = "process_list"
    description = "列出运行中的进程。可按名称筛选。返回 PID、名称、内存占用。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "可选，按名称筛选，如 'python'"},
            },
            "required": [],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import psutil
            filt = tool_input.get("filter", "").lower()
            procs = []
            for p in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    name = p.info["name"] or ""
                    if filt and filt not in name.lower():
                        continue
                    mem = p.info["memory_info"]
                    mem_mb = round(mem.rss / 1024 / 1024, 1) if mem else 0
                    procs.append((p.info["pid"], name, mem_mb))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            procs.sort(key=lambda x: -x[2])  # 按内存降序
            lines = [f"{pid:7d}  {name[:40]:40s}  {mem:7.1f} MB" for pid, name, mem in procs[:30]]
            return ToolResult.success(
                f"{len(procs)} processes:\n" + "\n".join(lines) if lines else "no matching processes"
            )
        except Exception as e:
            return ToolResult.fail(f"process list failed: {e}", str(e))


class ProcessKillHandler(ToolHandler):
    name = "process_kill"
    description = "终止进程。按 PID 或进程名。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "PID 数字或进程名，如 'notepad' 或 '1234'"},
            },
            "required": ["target"],
        }

    def needs_confirm(self, tool_input: dict) -> tuple[bool, str]:
        return True, f"kill process: {tool_input.get('target', '?')}"

    def execute(self, tool_input: dict) -> ToolResult:
        import psutil
        target = tool_input["target"].strip()
        killed = []

        try:
            # 尝试作为 PID
            if target.isdigit():
                pid = int(target)
                p = psutil.Process(pid)
                p.terminate()
                return ToolResult.success(f"killed PID {pid} ({p.name()})")

            # 按名称批量杀
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if p.info["name"] and target.lower() in p.info["name"].lower():
                        p.terminate()
                        killed.append(f"{p.info['pid']} ({p.info['name']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed:
                return ToolResult.success(f"killed {len(killed)}: {', '.join(killed[:10])}")
            return ToolResult.fail(f"no process matching '{target}' found")
        except psutil.NoSuchProcess:
            return ToolResult.fail(f"PID {target} not found")
        except psutil.AccessDenied:
            return ToolResult.fail(f"access denied for {target}", "access_denied")
        except Exception as e:
            return ToolResult.fail(f"kill failed: {e}", str(e))


class ProcessStartHandler(ToolHandler):
    name = "process_start"
    description = "启动应用程序。传 .exe 路径或系统命令。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "可执行文件路径或系统命令，如 'notepad' 或 'C:\\app.exe'"},
            },
            "required": ["path"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        path = tool_input["path"]
        import os as _os
        import subprocess as _sp

        # 绝对路径 → startfile
        if _os.path.exists(path):
            try:
                _os.startfile(path)
                return ToolResult.success(f"started: {path}")
            except Exception as e:
                return ToolResult.fail(f"start failed: {e}", str(e))

        # 常见应用路径查找
        common = {
            "wechat": [r"D:\Chatsoftware\Weixin\Weixin.exe", r"C:\Program Files\Tencent\WeChat\WeChat.exe"],
            "微信": [r"D:\Chatsoftware\Weixin\Weixin.exe", r"C:\Program Files\Tencent\WeChat\WeChat.exe"],
            "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
            "notepad": ["notepad.exe"],
            "cmd": ["cmd.exe"],
        }
        key = path.lower().replace(".exe", "").strip()
        if key in common:
            for p in common[key]:
                try:
                    if _os.path.exists(p):
                        _os.startfile(p)
                        return ToolResult.success(f"started: {p}")
                    else:
                        _sp.Popen(p, shell=True)
                        return ToolResult.success(f"started (shell): {p}")
                except Exception:
                    continue

        # PATH 里的程序
        try:
            _sp.Popen(path, shell=True)
            return ToolResult.success(f"started (shell): {path}")
        except Exception as e:
            return ToolResult.fail(f"start failed: {path} not found. try full path.", str(e))
