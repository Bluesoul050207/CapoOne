"""
system_status — 系统状态速览：CPU/内存/磁盘/电池
"""
from .base import ToolHandler
from ..tool_result import ToolResult


class SystemStatusHandler(ToolHandler):
    name = "system_status"
    description = "查看系统运行状态：CPU占用、内存、磁盘空间、电池电量。"

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, tool_input: dict) -> ToolResult:
        try:
            import psutil

            lines = []

            # CPU
            cpu = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            lines.append(f"CPU: {cpu}% ({cpu_count} cores)")

            # 内存
            mem = psutil.virtual_memory()
            lines.append(f"Memory: {mem.percent}% used ({_gb(mem.used)}/{_gb(mem.total)} GB)")

            # 磁盘
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    if usage.total > 1_000_000_000:  # 只显示 >1GB 的分区
                        lines.append(f"Disk {part.device} ({part.mountpoint}): {usage.percent}% used ({_gb(usage.free)} GB free)")
                except Exception:
                    pass

            # 电池（笔记本）
            batt = psutil.sensors_battery()
            if batt:
                status = "charging" if batt.power_plugged else "discharging"
                lines.append(f"Battery: {batt.percent}% ({status})")
            else:
                lines.append("Battery: (no battery / desktop)")

            # 运行时间
            import time
            boot = psutil.boot_time()
            uptime = time.time() - boot
            h, m = int(uptime // 3600), int((uptime % 3600) // 60)
            lines.append(f"Uptime: {h}h {m}m")

            return ToolResult.success("\n".join(lines))
        except ImportError:
            return ToolResult.fail("psutil not installed. pip install psutil")
        except Exception as e:
            return ToolResult.fail(f"system_status failed: {e}", "status_error")


def _gb(bytes_val: int) -> str:
    return f"{bytes_val / (1024**3):.1f}"
