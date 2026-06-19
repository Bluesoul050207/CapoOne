"""
token_tracker — Token 用量与成本追踪（TODO: 未来实现）

设计思路:
  - 每次 API 调用后记录 model、token 数、预估成本
  - 按会话/按天/按模型汇总
  - 价格从 config.py 读取

数据结构:
  {
    "session_id": "xxx",
    "model": "deepseek-chat",
    "timestamp": "2026-06-19T20:00:00",
    "prompt_tokens": 1500,
    "completion_tokens": 300,
    "estimated_cost_usd": 0.000735
  }

存储: SQLite (可复用 conversation.db 或独立 token_usage.db)

集成点: core/agent_loop.py 的 API 调用后从 response.usage 取 token 数

TODO:
  - [ ] 实现 TokenTracker 类
  - [ ] 在 agent_loop.run_turn() 中记录每次调用
  - [ ] /tokens CLI 命令查看用量
  - [ ] 成本告警阈值
"""

from config import PRICING


class TokenTracker:
    """Token 用量追踪器（空壳，待实现）"""

    def __init__(self, db_path: str = "memory/token_usage.db"):
        self.db_path = db_path
        self._total_input = 0
        self._total_output = 0
        self._cost = 0.0

    def record(self, model: str, prompt_tokens: int, completion_tokens: int):
        """记录一次 API 调用"""
        self._total_input += prompt_tokens
        self._total_output += completion_tokens
        pricing = PRICING.get(model, {"input": 0, "output": 0})
        cost = (prompt_tokens / 1_000_000) * pricing["input"] + \
               (completion_tokens / 1_000_000) * pricing["output"]
        self._cost += cost

    def summary(self) -> str:
        return f"tokens: {self._total_input} in / {self._total_output} out | ${self._cost:.4f}"


# 全局单例（预留）
_tracker: TokenTracker | None = None


def get_tracker() -> TokenTracker:
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker
