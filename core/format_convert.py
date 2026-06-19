"""
format_convert — Anthropic ↔ OpenAI 格式转换
agent.py 和 agent_loop.py 共用
"""

import json
import re


# emoji 过滤：模型输出的 emoji 在这直接干掉
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF"   # 杂项符号、表情、补充
    "\U0001FA00-\U0001FAFF"    # 扩展表情
    "\U0001F600-\U0001F64F"    # 表情符号
    "\U0001F680-\U0001F6FF"    # 交通符号
    "\U0001F1E0-\U0001F1FF"    # 国家旗帜
    "\U00002600-\U000027BF"    # 杂项符号
    "\U0000FE00-\U0000FE0F"    # 变体选择器
    "\U0000200D"               # 零宽连字符
    "]", flags=re.UNICODE)


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def _sanitize(text: str) -> str:
    """清理非法 Unicode 代理字符"""
    if not text:
        return text
    return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")


def anthropic_tools_to_openai(anthropic_tools: list) -> list:
    """将 Anthropic 工具定义转为 OpenAI function calling 格式"""
    openai_tools = []
    for tool in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            }
        })
    return openai_tools


def anthropic_msgs_to_openai(anthropic_msgs: list) -> list:
    """将 Anthropic 格式的消息转为 OpenAI 格式"""
    openai_msgs = []
    for msg in anthropic_msgs:
        role = msg["role"]
        content = _sanitize(msg.get("content")) if isinstance(msg.get("content"), str) else msg.get("content")

        if role == "user":
            if isinstance(content, str):
                openai_msgs.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # 多模态消息（文本 + 图片 + tool_result）
                openai_blocks = []
                has_tool_results = False
                tool_msgs = []

                for block in content:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "text":
                            openai_blocks.append({"type": "text", "text": block["text"]})
                        elif btype == "image":
                            src = block["source"]
                            openai_blocks.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{src['media_type']};base64,{src['data']}"
                                }
                            })
                        elif btype == "tool_result":
                            has_tool_results = True
                            tool_msgs.append({
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": block["content"],
                            })

                if has_tool_results:
                    # 工具结果作为独立的 tool 消息
                    openai_msgs.extend(tool_msgs)
                elif openai_blocks:
                    openai_msgs.append({"role": "user", "content": openai_blocks})

        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                # Anthropic 格式 {id, name, input} → OpenAI 格式 {id, type, function}
                openai_tcs = []
                for tc in tool_calls:
                    openai_tcs.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("input", {}), ensure_ascii=False),
                        }
                    })
                msg_out = {"role": "assistant", "content": None, "tool_calls": openai_tcs}
            else:
                msg_out = {"role": "assistant", "content": content or None}
            openai_msgs.append(msg_out)

    return openai_msgs
