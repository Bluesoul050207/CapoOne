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
from config import RECOVERY, FALLBACK_RECOVERY


# ============================================================
# POST_TOOL_HINTS — 工具成功后自动注入的"下一步"指令
# 和 system prompt 形成双重保险：模型记得最好，忘了代码兜底
# ============================================================

POST_TOOL_HINTS = {
    # web_search 成功后必须读全文
    "web_search": (
        "搜到结果了。现在用 web_fetch 读最相关的 1-2 个链接全文。"
        "不读全文不许总结回答。读完再说话。"
    ),
    # web_fetch 读完后可以总结了
    "web_fetch": (
        "读完内容了。现在总结回答用户的问题。"
        "如果信息还不够，继续搜或读更多链接。够了就别拖。"
    ),
    # cmd_help 查完直接告诉模型该用哪个工具
    "cmd_help": (
        "放歌/播放/音乐相关 → 只用 ncm_play，不要用 cmd_run。"
        "ncm_play 内部自动搜索+播放，不需要你手动搜 API。"
    ),
}

# 绕弯路成功后提醒记经验
EXPERIENCE_REMINDER = (
    "这次成功了但之前绕了弯路。用 save_memory 或 save_rule 记下经验，下次直接走捷径。"
)


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
    fallback_client=None,   # 备用客户端（主模型挂了自动切）
    fallback_model: str = "",
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

    # 首轮发射模型标识（前端可显示"正在用 xxx 思考..."）
    emit("model", model)

    prev_failure = False  # 上轮是否失败
    active_client = client
    active_model = model

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
            response = active_client.chat.completions.create(
                model=active_model, messages=openai_msgs,
                tools=openai_tools, stream=True, timeout=60,
            )
        except Exception as e:
            # 故障转移：主模型挂了，尝试备用
            if fallback_client and fallback_model and active_client is not fallback_client:
                emit("status", f"failover: {active_model} -> {fallback_model}")
                try:
                    active_client = fallback_client
                    active_model = fallback_model
                    response = active_client.chat.completions.create(
                        model=active_model, messages=openai_msgs,
                        tools=openai_tools, stream=True, timeout=60,
                    )
                except Exception as e2:
                    emit("error", f"API error (primary + fallback): {e2}")
                    return events
            else:
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
        ncm_fail_queries: list[str] = []   # 失败的原始 query
        ncm_ok_queries: list[str] = []     # 成功的 query

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

            # 工具结果验证器：ok=True 但结果可能不对 → 自动标失败
            if tr.ok:
                try:
                    valid, reason = registry.validate_tool(name, inp, tr)
                    if not valid:
                        tr = type(tr)(ok=False, text=tr.text, error=reason or "validation_failed")
                except Exception:
                    pass  # 验证本身出错不影响主流程

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
                if name == "ncm_play":
                    ncm_fail_queries.append(inp.get("query", ""))
            elif name == "ncm_play":
                ncm_ok_queries.append(inp.get("query", ""))

        conv.messages.append({"role": "user", "content": tool_results})

        # ---- ncm_play 自动记忆：仅恢复链存（失败→纠正→成功） ----
        # 不存首次成功——模型可能理解错，污染映射
        try:
            from modules.persona.song_map import SongMapDB
            sdb = SongMapDB()
            for sq in ncm_ok_queries:
                if sq:
                    for fail_q in ncm_fail_queries:
                        if fail_q and fail_q != sq:
                            sdb.set(fail_q, sq)  # 原始失败 query → 纠正后成功 query
        except Exception:
            pass

        # ---- 工具成功后的"下一步"注入（双重保险） ----
        if not had_failure:
            hints = []
            for tc in anthropic_tcs:
                tool_name = tc["name"]
                if tool_name in POST_TOOL_HINTS:
                    hint = POST_TOOL_HINTS[tool_name]
                    if hint not in hints:
                        hints.append(hint)
            if hints:
                conv.messages.append({"role": "user", "content": " ".join(hints)})

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
                    "content": EXPERIENCE_REMINDER,
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
