"""
agent_loop — 核心处理逻辑，agent.py 和 server.py 共用

run_turn() 执行一轮对话：API 调 → 工具执行 → 确认 → 润色
返回 typed event dicts，调用方决定怎么展示（print / WebSocket / SSE）
"""

import json
import asyncio
from agent import (
    anthropic_tools_to_openai, anthropic_msgs_to_openai,
    strip_emoji, needs_confirm, _rephrase_with_persona,
)


async def run_turn(
    conv,
    client,
    model: str,
    registry,
    *,
    dual_model: bool = False,
    persona_enabled: bool = True,
    confirm_handler=None,  # async def handler(msg: str) -> bool
) -> list[dict]:
    """
    执行一轮对话。返回 event 列表，每个 event 是 {"type": ..., "text": ...}

    调用方负责：
    - 显示 events（print / WS send / SSE yield）
    - 提供 confirm_handler（input() / WebSocket 异步等待）
    """
    events: list[dict] = []
    openai_tools = anthropic_tools_to_openai(registry.all_tools())

    def emit(evt_type: str, text: str = "", **extra):
        evt = {"type": evt_type, "text": text}
        evt.update(extra)
        events.append(evt)

    prev_failure = False  # 上轮是否失败

    for iteration in range(6):
        if iteration == 0:
            emit("status", "thinking...")

        openai_msgs = anthropic_msgs_to_openai(conv.get_api_messages())
        # 注入 system prompt（OpenAI 格式需手动加）
        if conv.system_prompt:
            from agent import _sanitize
            sp = _sanitize(conv.system_prompt)
            openai_msgs = [{"role": "system", "content": sp}] + openai_msgs

        try:
            response = client.chat.completions.create(
                model=model, messages=openai_msgs,
                tools=openai_tools, stream=True, timeout=60,
            )
        except Exception as e:
            emit("error", f"API error: {e}")
            return events

        assistant_text = ""
        tool_calls: list[dict] = []

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                clean = strip_emoji(delta.content)
                assistant_text += clean
                if not dual_model or not persona_enabled:
                    emit("text", clean)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    while len(tool_calls) <= idx:
                        tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                    if tc_delta.id:
                        tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls[idx]["function"]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

        # ---- 无工具调用：润色 + 结束 ----
        if not tool_calls:
            if dual_model and persona_enabled:
                emit("status", "rephrasing...")
                rephrased = _rephrase_with_persona(assistant_text)
                if not rephrased or not rephrased.strip():
                    rephrased = assistant_text or "(no response)"
                emit("text", rephrased)
            conv.add_assistant_message(assistant_text)
            emit("done")
            return events

        # ---- 执行工具 ----
        anthropic_tcs = []
        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}
            anthropic_tcs.append({"id": tc["id"], "name": tc["function"]["name"], "input": args})

        conv.add_assistant_message(assistant_text, tool_calls=anthropic_tcs)
        tool_results = []
        had_failure = False

        for tc in anthropic_tcs:
            name, inp = tc["name"], tc.get("input", {})
            emit("tool", f"[{name}] {json.dumps(inp, ensure_ascii=False)[:120]}")

            # 确认
            need, msg = needs_confirm(name, inp)
            if need and confirm_handler:
                emit("confirm_needed", msg)
                approved = await confirm_handler(msg)
                if not approved:
                    tool_results.append({"type": "tool_result", "tool_use_id": tc["id"], "content": "cancelled"})
                    continue

            tr = registry.execute_tool(name, inp)
            result_text = tr.text
            if len(result_text) > 4000:
                result_text = result_text[:4000] + "\n... (truncated)"
            brief = result_text[:150].replace('\n', ' ')
            emit("tool_result", brief + ("..." if len(result_text) > 150 else ""),
                 ok=tr.ok, error=tr.error or "", tool=name)
            tool_results.append({"type": "tool_result", "tool_use_id": tc["id"], "content": result_text})
            if not tr.ok:
                had_failure = True

        conv.messages.append({"role": "user", "content": tool_results})

        # 自反思 + 记忆
        if had_failure:
            if iteration < 3:
                conv.messages.append({"role": "user", "content": "失败了。换方法。"})
            prev_failure = True
        else:
            if prev_failure:
                conv.messages.append({"role": "user", "content": "绕弯路成功了。先继续完成用户请求（播放/搜索），再调save_memory记下这次的经验。"})
                prev_failure = False
            elif iteration >= 2:
                conv.messages.append({"role": "user", "content": "这一步够吗？不够就扩大范围再试。"})

        conv.trim()

    emit("error", "max tool iterations")
    return events


