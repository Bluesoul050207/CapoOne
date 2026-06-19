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


# ============================================================
# RECOVERY 字典 — 工具失败时根据错误标签自动注入恢复指令
# 不用 AI 自己想，直接告诉它下一步该做什么
# ============================================================

RECOVERY = {
    "low_match": (
        "用 web_search 查这首歌的原名/英文名 → 查到后立刻调 ncm_play 播放。"
        "只调工具不解释，不要说你找到了但不动手。"
    ),
    "file_not_found": (
        "文件没找到。用 list_directory 在附近目录找 → 找到后重读。"
        "如果还找不到就直接告诉用户文件不存在。"
    ),
    "no_matches": "没搜到结果。扩大搜索范围或缩短关键词重试。",
    "access_denied": "权限不够。换个路径或方式再试。如果确实不行就告诉用户需要管理员权限。",
    "unknown_tool": "这个工具不存在。用 cmd_help 看可用工具列表，选一个替代方案。",
    "timeout": "命令超时了。简化操作或拆成小步骤再试。",
    "not_found": "没找到目标。检查一下参数是否正确，或者换个搜索方式。",
}

# 当 RECOVERY 没匹配到且是连续失败时，注入这条通用反思
FALLBACK_RECOVERY = "上一步失败了。用其他方法再试一次，换工具、换参数、换顺序都行。"


def _get_recovery(error_tag: str) -> str | None:
    """根据错误标签返回针对性恢复指令。精确匹配优先，再尝试子串匹配。"""
    if not error_tag:
        return None
    tag = error_tag.lower().strip()
    if tag in RECOVERY:
        return RECOVERY[tag]
    for key, val in RECOVERY.items():
        if key in tag:
            return val
    return None


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
        error_tags: list[str] = []  # 收集所有失败的错误标签

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
                if tr.error:
                    error_tags.append(tr.error)

        conv.messages.append({"role": "user", "content": tool_results})

        # ---- 反思注入：基于错误标签的智能恢复 ----
        if had_failure:
            # 1. 先尝试用 RECOVERY 字典匹配针对性恢复指令
            recovery_msgs: list[str] = []
            for err_tag in error_tags:
                rec = _get_recovery(err_tag)
                if rec and rec not in recovery_msgs:
                    recovery_msgs.append(rec)

            if recovery_msgs:
                # 有针对性恢复指令 → 注入
                injection = "上一步失败的修复方案：" + " ".join(recovery_msgs)
                conv.messages.append({"role": "user", "content": injection})
            elif iteration < 3:
                # 没有匹配的恢复指令 → 通用反思
                conv.messages.append({"role": "user", "content": FALLBACK_RECOVERY})
            else:
                # 第4轮还在失败 → 问用户
                conv.messages.append({"role": "user", "content": "连续失败多次。告诉用户发生了什么，让用户决定下一步。"})
            prev_failure = True
        else:
            # 工具成功
            if prev_failure:
                # 上次失败这次成功 → 鼓励记经验
                conv.messages.append({
                    "role": "user",
                    "content": "这次成功了。先继续完成用户请求（播放/打开/搜索），完成后用 save_memory 或 save_rule 记下这次的经验教训。"
                })
                prev_failure = False
            elif iteration >= 3:
                # 多轮工具调用后还没结束 → 推一把
                conv.messages.append({
                    "role": "user",
                    "content": "已经调用多次工具了。该给用户一个结论了——总结你找到的信息，不要继续搜索。"
                })

        conv.trim()

    emit("error", "max tool iterations")
    return events
