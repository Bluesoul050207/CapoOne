"""
SessionLogger — JSONL 结构化日志，一行一条记录，方便回溯和搜索

格式: {"ts":"2026-06-15T20:30:00","session":"abc123","type":"tool_call","tool":"write_file","input":{...},"output":"...","duration_ms":45}

日志类型:
  tool_call    — 工具调用
  chat         — 用户输入 / AI 回复
  confirm      — 审批操作
  error        — 异常
  lifecycle    — 模块加载/卸载
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, timezone


class SessionLogger:
    """每个会话一个实例，写入独立的 JSONL 文件。"""

    def __init__(self, session_id: str, log_dir: str = "logs"):
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._file = None

    def _ensure_open(self):
        if self._file is None:
            path = self.log_dir / f"{self.session_id}.jsonl"
            self._file = open(path, "a", encoding="utf-8")

    def _write(self, entry: dict):
        self._ensure_open()
        entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
        entry.setdefault("session", self.session_id)
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    # ---- 公开方法 ----

    def tool_call(self, tool_name: str, tool_input: dict, output: str, duration_ms: float = 0):
        self._write({
            "type": "tool_call",
            "tool": tool_name,
            "input": tool_input,
            "output": output[:500],
            "duration_ms": round(duration_ms, 1),
        })

    def chat(self, role: str, content: str):
        self._write({
            "type": "chat",
            "role": role,
            "content": content[:1000],
        })

    def confirm(self, message: str, approved: bool):
        self._write({
            "type": "confirm",
            "message": message,
            "approved": approved,
        })

    def error(self, message: str, detail: str = ""):
        self._write({
            "type": "error",
            "message": message,
            "detail": detail[:1000],
        })

    def lifecycle(self, module_name: str, action: str):
        self._write({
            "type": "lifecycle",
            "module": module_name,
            "action": action,
        })

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


# ---- 全局日志工厂 ----

_logger: SessionLogger | None = None


def get_logger(session_id: str = "default") -> SessionLogger:
    global _logger
    if _logger is None or _logger.session_id != session_id:
        if _logger:
            _logger.close()
        _logger = SessionLogger(session_id)
    return _logger
