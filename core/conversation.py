"""
conversation — 对话历史管理
Conversation 类 + token 计数工具
"""

import json


# ---- Token 计数 ----

def count_tokens(text: str) -> int:
    """粗略估算 token 数：中文 1 字≈1.5 token，英文 1 词≈1.3 token"""
    chinese = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - chinese
    return int(chinese * 1.5 + other / 3.5)


def estimate_messages_tokens(messages: list) -> int:
    """估算消息列表的总 token 数"""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += count_tokens(str(block.get("text", block.get("content", ""))))
        # tool_calls
        for tc in m.get("tool_calls", []):
            total += count_tokens(json.dumps(tc.get("input", {}), ensure_ascii=False))
    return total


# ---- Conversation ----

class Conversation:
    """管理对话历史和记忆"""

    def __init__(self, system_prompt: str, max_messages: int = 32):
        self.system_prompt = system_prompt
        self.max_messages = max_messages
        self.messages: list[dict] = []
        self.temp_rules: list[str] = []  # 对话内临时规则，会话结束忘

    def add_user_message(self, content: str | list):
        """添加用户消息，支持文本或图片"""
        if isinstance(content, str):
            self.messages.append({
                "role": "user",
                "content": content
            })
        else:
            # 多模态消息（文本 + 图片）
            self.messages.append({
                "role": "user",
                "content": content
            })

    def add_assistant_message(self, content: str, tool_calls: list | None = None):
        """添加助手消息"""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_use_id: str, result: str):
        """添加工具执行结果"""
        self.messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result
            }]
        })

    def get_api_messages(self) -> list[dict]:
        """获取发送给 API 的消息列表，自动截断旧消息"""
        return self.messages[-self.max_messages:]

    def token_usage(self) -> int:
        """估算当前历史消息的总 token 数"""
        return estimate_messages_tokens(self.messages)

    def trim(self):
        """消息太多时保留后半段"""
        if len(self.messages) > self.max_messages:
            keep = self.max_messages // 2
            self.messages = self.messages[-keep:]
        # 清理开头的孤立 tool 消息（assistant 被裁了）
        while self.messages:
            content = self.messages[0].get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                self.messages.pop(0)
            else:
                break
