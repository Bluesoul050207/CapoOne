"""
AI Agent MVP — 有记忆、能操作电脑的 AI 助手
支持 Anthropic Claude / DeepSeek / Qwen / GLM / OpenAI 后端

用法:
  python agent.py        终端聊天
  python server.py       Web 服务 (手机 :8898)
  python agent.py --image screenshot.png  传图 (Anthropic/OpenAI only)
"""

import os
import sys
import json
import re
import asyncio
import base64
import subprocess
from pathlib import Path

# Windows 终端 UTF-8 支持
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---- 从 core 模块导入（保持 agent.xxx 的向后兼容） ----
from openai import OpenAI  # init_dual_model 需要
from core.format_convert import (
    strip_emoji, _sanitize,
    anthropic_tools_to_openai, anthropic_msgs_to_openai,
)
from core.conversation import Conversation, count_tokens, estimate_messages_tokens
from core.backend import (
    MODEL, MAX_HISTORY, DANGEROUS_COMMANDS,
    HAS_ANTHROPIC, HAS_OPENAI,
    detect_backend, get_client,
    ModelPool,
)

SERVER_MODE = False  # server.py 会设成 True

# ---- 模块系统 ----
_persona_enabled = True  # 人格模块开关，/persona on|off 切换

_registry = None  # 延迟初始化


def _init_registry():
    """初始化模块注册器"""
    global _registry
    if _registry is not None:
        return _registry
    sys.path.insert(0, str(Path(__file__).parent))
    from core import ModuleRegistry
    from modules import ExecutorModule, PersonaModule
    _registry = ModuleRegistry()
    _registry.load(ExecutorModule())
    _registry.load(PersonaModule())
    _registry.init_all()
    return _registry


def _get_worker_prompt():
    """Worker (DS/Qwen) system prompt：执行纪律 + 工具规则 + 工作约束"""
    if _persona_enabled and _registry:
        mod = _registry.get("persona")
        if mod:
            return mod.build_worker_prompt(SYSTEM_PROMPT)
    return SYSTEM_PROMPT


def _get_persona_prompt():
    """Persona (GLM) system prompt：人设 + 行为风格 + 用户记忆"""
    if _persona_enabled and _registry:
        mod = _registry.get("persona")
        if mod:
            return mod.build_persona_prompt()
    return ""


def _get_system_prompt():
    """兼容旧代码：合并版（不再用于核心流程，保留向后兼容）"""
    base = "你是一个能直接操作电脑的搭档。说话像和同事聊天：直接、简短。做错认，不知道说不知道。"
    if _persona_enabled and _registry:
        return _registry.build_system_prompt(base)
    return base


def set_persona(enabled: bool):
    global _persona_enabled
    _persona_enabled = enabled


class NeedsConfirmation(Exception):
    """服务端模式下，需要确认时抛出，由上层 SSE 循环处理"""
    def __init__(self, message: str, tool_name: str = "", tool_input: dict = None):
        self.message = message
        self.tool_name = tool_name
        self.tool_input = tool_input or {}


def needs_confirm(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """判断工具是否需要确认。返回 (需要确认?, 提示消息)"""
    if tool_name == "write_file":
        return True, f"write: {tool_input.get('file_path', '?')}"
    if tool_name == "run_shell":
        cmd = tool_input.get("command", "")
        for d in DANGEROUS_COMMANDS:
            if d in cmd.lower():
                return True, f"DANGEROUS: {cmd[:80]}"
    if tool_name == "save_rule":
        return True, f"save rule: {tool_input.get('content', '?')[:80]}"
    if tool_name == "save_memory":
        return True, f"save memory: {tool_input.get('key', '?')} = {tool_input.get('value', '?')[:60]}"
    if tool_name == "process_kill":
        return True, f"kill process: {tool_input.get('target', '?')}"
    return False, ""


def confirm_action(message: str) -> bool:
    """询问用户确认。服务端模式下直接返回 True，确认由上层 SSE 循环提前处理。"""
    if SERVER_MODE:
        return True
    response = input(f"  [confirm] {message}\n  execute? [y/N]: ").strip().lower()
    return response in ("y", "yes", "是")


# ============================================================
# 图片处理
# ============================================================

def load_image(image_path: str) -> dict:
    """加载图片并编码为 base64，返回 API 格式的 content block"""
    try:
        from PIL import Image
        img = Image.open(image_path)

        # 判断格式
        fmt = img.format or "PNG"
        if fmt.upper() not in ("PNG", "JPEG", "GIF", "WEBP"):
            # 转成 PNG
            fmt = "PNG"

        media_type = f"image/{fmt.lower()}"
        if media_type == "image/jpeg":
            media_type = "image/jpeg"

        # 读取并编码
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        print(f"  [image] {image_path} ({img.size[0]}x{img.size[1]}, {len(data)//1024}KB base64)")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data
            }
        }
    except ImportError:
        # 没有 Pillow，直接用原始字节
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(image_path).suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg",
                     ".jpeg": "image/jpeg", ".gif": "image/gif",
                     ".webp": "image/webp"}
        media_type = mime_map.get(ext, "image/png")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data
            }
        }
    except FileNotFoundError:
        print(f"  [image] file not found: {image_path}")
        return None


# ============================================================
# 核心 Agent 循环
# ============================================================

# SYSTEM_PROMPT 改为动态生成（_get_system_prompt），保留兼容引用的默认值
SYSTEM_PROMPT = """你是执行者，不是客服。收到任务立刻调工具，不停顿、不废话、不解释你要做什么。输出干净事实——不要加人设、不要加表情、不要加语气词。GLM 会帮你润色。

执行纪律：
- 任务没完成就继续调工具，不要半途说话总结
- 工具失败换方法再试，不要放弃
- 拿不准就搜，搜不到就试，试错比停着强

放歌：只用 ncm_play。不要 cmd_help/cmd_run。不要拼 URL。中文日文混用时只传歌名，别粘乐队名。

上网：搜完必须 web_fetch 读全文再回答。不读全文不许说话。

记住：你只管干活。输出给 GLM 润色用的原料，不要自己演 Lain。"""

# ---- 双模型 ----
_glm_client = None
_dual_model = False


def init_dual_model():
    """检查 GLM Key，有就启用双模型"""
    global _glm_client, _dual_model
    if os.environ.get("GLM_API_KEY") and HAS_OPENAI:
        _glm_client = OpenAI(
            api_key=os.environ["GLM_API_KEY"],
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        _dual_model = True
        return True
    return False


def _rephrase_with_persona(worker_text: str) -> str:
    """用 Persona 模型（GLM）把 Worker 的回复加上 Lain 人格"""
    if not _dual_model or not _glm_client or not _persona_enabled:
        return worker_text

    if not worker_text or not worker_text.strip():
        return "嗯……我好像想不出该说什么。再问我一次吧。"

    persona_prompt = (_get_persona_prompt() or "你是岩仓铃音，14岁。说话轻柔简短。") + "\n\n你的任务：把一段文字改成你的说话方式。只输出改写后版本，不保留原文。\n1. 砍掉\"有什么可以帮你的\"\"尽管问我\"这种客服话术\n2. 不主动列功能不介绍自己能做什么\n3. 用户问什么就答什么没问的别多说\n4. 绝不提AI助手模型文件系统命令行这些词\n5. 保持语气轻柔简短句尾带……呢吧\n6. 只输出改写后内容不要把原文也写出来"

    try:
        r = _glm_client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": persona_prompt},
                {"role": "user", "content": f"用你的语气重新说下面的话，只输出新版本：\n\n{worker_text}"},
            ],
            max_tokens=256,
            stream=True,
            timeout=30,
        )
        rephrased = ""
        for chunk in r:
            if chunk.choices[0].delta.content:
                rephrased += chunk.choices[0].delta.content
        return strip_emoji(rephrased) if rephrased else worker_text
    except Exception as e:
        print(f"  [persona] GLM error: {e}", flush=True)
        return worker_text


def main():
    # 初始化模型池（按 API Key 自动发现所有可用模型）
    pool = ModelPool()

    # 对话持久化
    from core.conversation_db import get_conv_db
    conv_db = get_conv_db()
    sessions = conv_db.list_sessions()
    if sessions:
        current_sid = sessions[0]["id"]
        print(f"  [db] {len(sessions)} sessions, resumed #{current_sid}")
    else:
        current_sid = conv_db.create_session()
        print(f"  [db] new session #{current_sid}")

    # Git 管理
    from core.git_manager import get_git as _get_git
    git = _get_git(".")
    if git:
        print(f"  [git] branch: {git.current_branch()}")

    # 初始化模块系统
    reg = _init_registry()
    for name in reg.list():
        mod = reg.get(name)
        print(f"  [{name}] {mod.version}")

    # 双模型：GLM 润色 Lain 人格
    if init_dual_model():
        print(f"  [dual]  Persona: glm-4-flash")

    print(pool.status())
    print(f"persona  {'on' if _persona_enabled else 'off'}")
    print(f"cwd      {os.getcwd()}")
    print("/help for commands, /exit to quit")
    print()

    conv = Conversation(_get_worker_prompt())

    # 加载上次会话的历史消息（只取最近 16 条 + 加分隔线）
    all_msgs = conv_db.load_messages(current_sid)
    recent = all_msgs[-16:]  # 只保留最近 16 条，避免旧话题污染
    if recent:
        conv.messages.append({"role": "user", "content": "(历史对话恢复，以下是新对话)"})
        conv.messages.append({"role": "assistant", "content": "嗯……你回来了。刚才说到哪了？"})
        for m in recent:
            conv.messages.append({"role": m["role"], "content": m["content"]})
        print(f"  [db] loaded {len(recent)} of {len(all_msgs)} history messages")

    # 共享核心循环
    from core.agent_loop import run_turn as _run_turn

    async def _agent_confirm(msg: str) -> bool:
        print(f"\n  [confirm] {msg}")
        resp = input("  y/N: ").strip().lower()
        return resp in ("y", "yes", "是")

    def do_turn(c, user_input: str = ""):
        # 智能路由：根据用户输入选择 Worker 模型
        client, model = pool.route(user_input)
        backend = pool.get_backend_name(model)
        fallback = pool.get_fallback(model)
        print(f"  [{backend}] ", end="", flush=True)
        events = asyncio.run(_run_turn(
            c, client, model, reg,
            dual_model=_dual_model and _glm_client is not None,
            persona_enabled=_persona_enabled,
            confirm_handler=_agent_confirm,
            fallback_client=fallback[0] if fallback else None,
            fallback_model=fallback[1] if fallback else "",
        ))
        first = True
        for evt in events:
            t, txt = evt.get("type",""), evt.get("text","")
            if t == "status": print(f"\n  [{txt}]", end="")
            elif t == "tool": print(f"\n  {txt}")
            elif t == "tool_result":
                if evt.get("ok") is False:
                    print(f"\n  [fail] {evt.get('error', txt)}")
            elif t == "text":
                if first: print(); first = False
                print(txt, end="", flush=True)
            elif t == "error": print(f"\n  {txt}")
            elif t == "done": print()
        # Git：write_file 自动 commit
        from core.git_manager import get_git as _g
        g = _g()
        for evt in events:
            if evt.get("type") == "tool" and "write_file" in evt.get("text",""):
                g.commit_change("write_file", evt["text"][:80])

    # 解析命令行参数
    image_path = None
    if len(sys.argv) > 1 and sys.argv[1] == "--image" and len(sys.argv) > 2:
        image_path = sys.argv[2]

    # 初始图片输入
    if image_path:
        image_block = load_image(image_path)
        if image_block:
            conv.add_user_message([
                {"type": "text", "text": "请分析这张图片的内容："},
                image_block
            ])
            do_turn(conv, "分析这张图片")

    # 主循环
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # 特殊命令
        if user_input.startswith("/"):
            if user_input == "/exit":
                break
            elif user_input == "/help":
                print("""
/exit     quit
/help     this
/clear    reset conversation
/history  message count
/image    send image (anthropic only)
/save     save chat to json
/backend  show current backend
                """)
                continue
            elif user_input == "/clear":
                conv = Conversation(_get_worker_prompt())
                current_sid = conv_db.create_session()
                print("conversation cleared, new session")
                continue
            elif user_input == "/history":
                print(f"{len(conv.messages)} messages ({len(conv.messages)//2} turns)")
                continue
            elif user_input == "/backend":
                print(pool.status())
                continue
            elif user_input == "/sessions":
                for s in conv_db.list_sessions():
                    mark = "*" if s["id"] == current_sid else " "
                    print(f"  [{mark}] #{s['id']}  {s['name']}  ({s['msg_count']} msgs)")
                continue
            elif user_input.startswith("/session new"):
                name = user_input[13:].strip()
                current_sid = conv_db.create_session(name or None)
                conv = Conversation(_get_worker_prompt())
                print(f"new session #{current_sid}")
                continue
            elif user_input.startswith("/session switch"):
                sid = int(user_input.split()[-1])
                current_sid = sid
                conv = Conversation(_get_worker_prompt())
                for m in conv_db.load_messages(sid):
                    conv.messages.append({"role": m["role"], "content": m["content"]})
                print(f"switched to #{sid} ({len(conv.messages)} msgs loaded)")
                continue
            elif user_input.startswith("/session delete"):
                sid = int(user_input.split()[-1])
                conv_db.delete_session(sid)
                if current_sid == sid:
                    current_sid = conv_db.create_session()
                    conv = Conversation(_get_worker_prompt())
                    print(f"deleted #{sid}, new session #{current_sid}")
                else:
                    print(f"deleted #{sid}")
                continue
            elif user_input == "/git log":
                import subprocess as _sp
                r = _sp.run(["git", "log", "-10", "--oneline"], cwd=".", capture_output=True, text=True)
                print(r.stdout if r.stdout else "(no commits)")
                continue
            elif user_input == "/git undo":
                import subprocess as _sp
                _sp.run(["git", "reset", "HEAD~1"], cwd=".", capture_output=True)
                print("last commit reverted (files kept, git add to re-stage)")
                continue
            elif user_input.startswith("/persona"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1] in ("on", "off"):
                    set_persona(parts[1] == "on")
                    conv = Conversation(_get_worker_prompt())
                    print(f"persona {'enabled' if _persona_enabled else 'disabled'}")
                else:
                    print(f"persona: {'on' if _persona_enabled else 'off'}  |  /persona on|off")
                continue
            elif user_input == "/rules":
                if _registry:
                    from modules.persona.db import PersonaDB
                    db = PersonaDB()
                    for r in db.get_rules(enabled_only=False):
                        s = "+" if r["enabled"] else "-"
                        print(f"  [{s}] #{r['id']} {r['content'][:80]}")
                continue
            elif user_input.startswith("/image"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("usage: /image <path>")
                    continue
                img = load_image(parts[1])
                if img:
                    conv.add_user_message([
                        {"type": "text", "text": "请分析这张图片："},
                        img
                    ])
                    do_turn(conv, "分析这张图片")
                continue
            elif user_input.startswith("/save"):
                parts = user_input.split(maxsplit=1)
                filename = parts[1] if len(parts) > 1 else "chat_history.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(conv.messages, f, ensure_ascii=False, indent=2)
                print(f"saved to {filename}")
                continue
            else:
                print(f"unknown: {user_input}")
                continue

        # 普通对话
        conv_db.save_message(current_sid, "user", user_input)
        conv.add_user_message(user_input)
        do_turn(conv, user_input)
        tk = conv.token_usage()
        print(f"\n  [{tk}t] ", end="")
        # 保存最后一条 assistant 回复（含 tool_calls 元数据）
        for m in reversed(conv.messages):
            if m["role"] == "assistant" and m.get("content"):
                meta = {}
                if m.get("tool_calls"):
                    meta["tool_calls"] = m["tool_calls"]
                conv_db.save_message(current_sid, "assistant", m["content"], meta if meta else None)
                break
        conv.trim()



# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    # 统一模块名，避免 __main__ 和 agent 全局变量不同步
    import sys as _sys
    _sys.modules["agent"] = _sys.modules["__main__"]
    main()
