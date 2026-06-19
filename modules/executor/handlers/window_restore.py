"""
window_restore — 恢复/聚焦窗口
"""
import subprocess, ctypes
from .base import ToolHandler
from ..tool_result import ToolResult


class WindowRestoreHandler(ToolHandler):
    name = "window_restore"
    description = "恢复并聚焦指定窗口。按标题或进程名匹配，把最小化或后台的窗口唤出来。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "窗口标题或进程名关键词，如 'Chrome'、'微信'"},
            },
            "required": ["title"],
        }

    def execute(self, tool_input: dict) -> ToolResult:
        import sys
        if sys.platform != "win32":
            return ToolResult.fail("window_restore only works on Windows")

        title = tool_input["title"].lower()
        restored = []

        try:
            import psutil
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if title in p.info["name"].lower():
                        hwnd = _find_window_by_pid(p.info["pid"])
                        if hwnd:
                            _restore_window(hwnd)
                            restored.append(f"{p.info['name']} ({p.info['pid']})")
                except Exception:
                    pass
        except ImportError:
            pass

        # 也尝试用窗口标题匹配
        if not restored:
            try:
                hwnd = _find_window_by_title(title)
                if hwnd:
                    _restore_window(hwnd)
                    restored.append(f"window matching '{title}'")
            except Exception:
                pass

        if restored:
            return ToolResult.success(f"restored: {', '.join(restored)}")
        return ToolResult.success(f"no window matching '{title}' found — already visible or not running")


def _find_window_by_pid(pid: int):
    """按 PID 找到主窗口句柄"""
    result = []

    def callback(hwnd, lParam):
        import ctypes.wintypes
        _pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(_pid))
        if _pid.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
            result.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None


def _find_window_by_title(title: str):
    """按标题关键词找窗口句柄"""
    result = []

    def callback(hwnd, lParam):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            if title in buf.value.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
                result.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None


def _restore_window(hwnd):
    """恢复 + 聚焦窗口"""
    SW_RESTORE = 9
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
