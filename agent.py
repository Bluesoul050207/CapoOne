"""
AI Agent MVP — 有记忆、能操作电脑、能识图的 AI 助手
支持 Anthropic Claude / DeepSeek / OpenAI 兼容后端

用法:
  方案一（DeepSeek，推荐，国内可用）:
    $env:DEEPSEEK_API_KEY='sk-你的key'
    pip install openai pillow
    python agent.py

  方案二（Anthropic Claude，需代理+外国卡）:
    $env:ANTHROPIC_API_KEY='sk-ant-你的key'
    pip install anthropic pillow
    python agent.py

  传图: python agent.py --image screenshot.png

特性:
  - 多轮对话记忆（滑动窗口 + 自动压缩）
  - 工具调用：读文件、写文件、列目录、运行命令、搜索内容
  - 图片识别（Anthropic 后端支持 png/jpg/gif/webp）
  - 流式输出
  - 危险命令确认
  - 双后端：DeepSeek / Anthropic 自动切换
"""

import os
import sys
import json
import re
import asyncio
import base64
import subprocess
import fnmatch
from pathlib import Path
from typing import Any
from datetime import datetime

# Windows 终端 UTF-8 支持
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

# ============================================================
# 配置
# ============================================================

MODEL = "claude-sonnet-4-6"          # 模型，可换成 claude-opus-4-8 等
MAX_HISTORY = 32                      # 最多保留多少轮对话（省 token）
DANGEROUS_COMMANDS = [
    "rm -rf", "del /f", "format",
    "shutdown", "restart", "reg delete",
    ":(){ :|:& };:",                   # fork bomb
]

# ============================================================
# 初始化 Anthropic 客户端
# ============================================================

# ---- Anthropic 后端 ----
try:
    from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ---- OpenAI 兼容后端（DeepSeek / Qwen / OpenAI 等） ----
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

if not HAS_ANTHROPIC and not HAS_OPENAI:
    print("请至少安装一个后端: pip install anthropic 或 pip install openai")
    sys.exit(1)


def detect_backend() -> tuple[str, str]:
    """
    检测可用的后端，返回 (backend_name, reason)
    优先级: ANTHROPIC > DEEPSEEK > OPENAI
    """
    from_env = os.environ.get("AI_BACKEND", "").lower()

    if from_env == "anthropic" and HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", "环境变量 AI_BACKEND=anthropic"
    if from_env == "deepseek" and HAS_OPENAI and os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek", "环境变量 AI_BACKEND=deepseek"
    if from_env == "openai" and HAS_OPENAI and (os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
        return "openai", "环境变量 AI_BACKEND=openai"

    # 自动检测
    if HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", "检测到 ANTHROPIC_API_KEY"
    if HAS_OPENAI and os.environ.get("DASHSCOPE_API_KEY"):
        return "qwen", "检测到 DASHSCOPE_API_KEY"
    if HAS_OPENAI and os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek", "检测到 DEEPSEEK_API_KEY"
    if HAS_OPENAI and os.environ.get("OPENAI_API_KEY"):
        return "openai", "检测到 OPENAI_API_KEY"

    return "none", ""


def get_client(backend: str):
    """根据后端名创建对应的客户端"""
    if backend == "anthropic":
        return Anthropic()
    elif backend == "deepseek":
        return OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
    elif backend == "qwen":
        return OpenAI(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    elif backend == "glm":
        return OpenAI(
            api_key=os.environ["GLM_API_KEY"],
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
    elif backend == "openai":
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
        )
    raise ValueError(f"未知后端: {backend}")


# ============================================================
# 工具定义
# ============================================================



# ============================================================
# OpenAI 兼容格式转换
# ============================================================

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


def _sanitize(text: str) -> str:
    """清理非法 Unicode 代理字符"""
    if not text:
        return text
    return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")


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


# ============================================================
# 工具执行
# ============================================================

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """执行工具并返回结果字符串"""

    if tool_name == "read_file":
        file_path = tool_input["file_path"]
        offset = tool_input.get("offset", 0)
        limit = tool_input.get("limit", 100)

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            result_lines = []
            for i, line in enumerate(selected):
                result_lines.append(f"{offset + i + 1:4d}| {line}")
            result = "".join(result_lines)
            if offset + limit < total:
                result += f"\n... (还有 {total - offset - limit} 行)"
            return result or "(empty)"
        except FileNotFoundError:
            return f"file not found: {file_path}"
        except PermissionError:
            return f"permission denied: {file_path}"
        except Exception as e:
            return f"error: {e}"

    elif tool_name == "write_file":
        file_path = tool_input["file_path"]
        content = tool_input["content"]

        # 确认
        if not confirm_action(f"write: {file_path}"):
            return "cancelled."

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"wrote {file_path} ({len(content)} chars)"
        except Exception as e:
            return f"write failed: {e}"

    elif tool_name == "list_directory":
        path = tool_input.get("path", os.getcwd())
        pattern = tool_input.get("pattern", "*")

        try:
            entries = sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            if pattern != "*":
                entries = [e for e in entries if fnmatch.fnmatch(e.name, pattern)]
            lines = []
            for e in entries:
                tag = "[D]" if e.is_dir() else "[F]"
                try:
                    size = e.stat().st_size
                    mtime = datetime.fromtimestamp(e.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    size = 0
                    mtime = "?"
                if e.is_dir():
                    line = f"{tag} {e.name}/"
                else:
                    line = f"{tag} {e.name}  ({size:>8,} bytes, {mtime})"
                lines.append(line)
            return "\n".join(lines) if lines else "(empty)"
        except Exception as e:
            return f"error: {e}"

    elif tool_name == "run_shell":
        command = tool_input["command"]
        desc = tool_input.get("description", "")

        # 危险命令检查
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command.lower():
                if not confirm_action(f"DANGEROUS: {command}"):
                    return "cancelled."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=30,
                cwd=os.getcwd(),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"
            return output[:8000] or "(no output)"
        except subprocess.TimeoutExpired:
            return "error: command timed out (30s)"
        except Exception as e:
            return f"error: {e}"

    elif tool_name == "search_content":
        import re
        pattern = tool_input["pattern"]
        directory = tool_input["directory"]
        file_pattern = tool_input.get("file_pattern", "*")

        try:
            matches = []
            for root, dirs, files in os.walk(directory):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if fnmatch.fnmatch(f, file_pattern):
                        file_path = os.path.join(root, f)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                                for i, line in enumerate(fp, 1):
                                    if re.search(pattern, line, re.IGNORECASE):
                                        rel_path = os.path.relpath(file_path, directory)
                                        matches.append(f"{rel_path}:{i}: {line.strip()[:120]}")
                            if len(matches) > 50:
                                matches.append("... (truncated, showing first 50)")
                                break
                        except (PermissionError, OSError):
                            continue
            return "\n".join(matches) if matches else f"no matches for '{pattern}'"
        except Exception as e:
            return f"search error: {e}"

    else:
        return f"unknown tool: {tool_name}"


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


def _get_system_prompt():
    """生成 system prompt，人格开启时注入约束和记忆"""
    base = """你是一个能直接操作电脑的搭档。说话像和同事聊天：直接、简短。做错认，不知道说不知道。"""
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
    return False, ""


def confirm_action(message: str) -> bool:
    """询问用户确认。服务端模式下直接返回 True，确认由上层 SSE 循环提前处理。"""
    if SERVER_MODE:
        return True
    response = input(f"  [confirm] {message}\n  execute? [y/N]: ").strip().lower()
    return response in ("y", "yes", "是")


# ============================================================
# 对话管理
# ============================================================

class Conversation:
    """管理对话历史和记忆"""

    def __init__(self, system_prompt: str, max_messages: int = MAX_HISTORY):
        self.system_prompt = system_prompt
        self.max_messages = max_messages
        self.messages: list[dict] = []

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
SYSTEM_PROMPT = """禁止使用任何emoji。你是直接干活的搭档，不是客服。说话直接、简短。做错认。自己动手。

搜歌规则：调ncm_play前先做两件事——①查save_memory有没有存过这个歌名的正确映射，上次用户纠正过就记住，直接用不重搜；②不确定是翻译就先web_search查原名。做完再ncm_play。

上网查资料：搜1-2次 → 必须用web_fetch读最相关的页面全文 → 总结回答。不读全文不许回答。读完不够再搜。

有 save_rule 和 save_memory 可以永久记忆。绕弯路才完成的事，立刻存经验。用户纠正你，立刻存偏好。下次直接读记忆，不再绕。"""

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

    persona_prompt = _get_system_prompt() + "\n\n你的任务：把一段文字改成你的说话方式。只输出改写后版本，不保留原文。\n1. 砍掉\"有什么可以帮你的\"\"尽管问我\"这种客服话术\n2. 不主动列功能不介绍自己能做什么\n3. 用户问什么就答什么没问的别多说\n4. 绝不提AI助手模型文件系统命令行这些词\n5. 保持语气轻柔简短句尾带……呢吧\n6. 只输出改写后内容不要把原文也写出来"

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
    # 检测后端
    backend, reason = detect_backend()
    if backend == "none":
        print("agent: no backend available. set one of:")
        print("  DEEPSEEK_API_KEY  (recommended)")
        print("  ANTHROPIC_API_KEY")
        print("  AI_BACKEND=deepseek|anthropic|openai")
        sys.exit(1)

    backend_client = get_client(backend)

    model_display = os.environ.get("AI_MODEL") or {
        "anthropic": MODEL,
        "deepseek": "deepseek-chat",
        "openai": "gpt-4o",
        "qwen": "qwen-max",
    }.get(backend, "unknown")

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

    # 双模型：DeepSeek 干活 + GLM 说话
    if init_dual_model():
        print(f"  [dual]  Worker: deepseek  |  Persona: glm-4-flash")

    print(f"backend  {backend} / {model_display}")
    print(f"persona  {'on' if _persona_enabled else 'off'}")
    print(f"cwd      {os.getcwd()}")
    if backend == "deepseek":
        print("note     image recognition not available")
    print("/help for commands, /exit to quit")
    print()

    conv = Conversation(_get_system_prompt())

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

    model_name = os.environ.get("AI_MODEL") or {
        "deepseek": "deepseek-chat", "openai": "gpt-4o", "qwen": "qwen-max",
    }.get(backend, "deepseek-chat")

    async def _agent_confirm(msg: str) -> bool:
        print(f"\n  [confirm] {msg}")
        resp = input("  y/N: ").strip().lower()
        return resp in ("y", "yes", "是")

    def do_turn(c):
        events = asyncio.run(_run_turn(
            c, backend_client, model_name, reg,
            dual_model=_dual_model and _glm_client is not None,
            persona_enabled=_persona_enabled,
            confirm_handler=_agent_confirm,
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
        if backend == "deepseek":
            print("image not supported on deepseek, skipping --image")
        else:
            image_block = load_image(image_path)
            if image_block:
                conv.add_user_message([
                    {"type": "text", "text": "请分析这张图片的内容："},
                    image_block
                ])
                do_turn(conv)

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
                conv = Conversation(_get_system_prompt())
                current_sid = conv_db.create_session()
                print("conversation cleared, new session")
                continue
            elif user_input == "/history":
                print(f"{len(conv.messages)} messages ({len(conv.messages)//2} turns)")
                continue
            elif user_input == "/backend":
                print(f"backend: {backend}  model: {model_display}")
                continue
            elif user_input == "/sessions":
                for s in conv_db.list_sessions():
                    mark = "*" if s["id"] == current_sid else " "
                    print(f"  [{mark}] #{s['id']}  {s['name']}  ({s['msg_count']} msgs)")
                continue
            elif user_input.startswith("/session new"):
                name = user_input[13:].strip()
                current_sid = conv_db.create_session(name or None)
                conv = Conversation(_get_system_prompt())
                print(f"new session #{current_sid}")
                continue
            elif user_input.startswith("/session switch"):
                sid = int(user_input.split()[-1])
                current_sid = sid
                conv = Conversation(_get_system_prompt())
                for m in conv_db.load_messages(sid):
                    conv.messages.append({"role": m["role"], "content": m["content"]})
                print(f"switched to #{sid} ({len(conv.messages)} msgs loaded)")
                continue
            elif user_input.startswith("/session delete"):
                sid = int(user_input.split()[-1])
                conv_db.delete_session(sid)
                if current_sid == sid:
                    current_sid = conv_db.create_session()
                    conv = Conversation(_get_system_prompt())
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
                    conv = Conversation(_get_system_prompt())
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
                if backend == "deepseek":
                    print("image not supported on deepseek")
                    continue
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
                    do_turn(conv)
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
        do_turn(conv)
        tk = conv.token_usage()
        print(f"\n  [{tk}t] ", end="")
        # 保存最后一条 assistant 回复
        for m in reversed(conv.messages):
            if m["role"] == "assistant" and m.get("content"):
                conv_db.save_message(current_sid, "assistant", m["content"])
                break
        conv.trim()


def process_turn(conv: Conversation):
    """处理一轮对话：发消息给 API → 处理工具调用 → 循环直到不需要工具"""

    for iteration in range(10):  # 最多 10 轮工具调用
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=conv.system_prompt,
                messages=conv.get_api_messages(),
                tools=_registry.all_tools() if _registry else [],
                stream=True,
            )
        except Exception as e:
            print(f"\nAPI error: {e}")
            return

        # 处理流式响应
        assistant_text = ""
        tool_use_blocks: list[dict] = []
        current_tool: dict | None = None
        current_tool_input: str = ""

        print()

        for event in response:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "text":
                    pass  # 文本块开始
                elif block.type == "tool_use":
                    current_tool = {
                        "id": block.id,
                        "name": block.name,
                    }
                    current_tool_input = ""

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    clean = strip_emoji(delta.text)
                    print(clean, end="", flush=True)
                    assistant_text += clean
                elif delta.type == "input_json_delta" and current_tool:
                    current_tool_input += delta.partial_json

            elif event.type == "content_block_stop":
                if current_tool:
                    # 工具调用块结束
                    try:
                        tool_input = json.loads(current_tool_input) if current_tool_input else {}
                    except json.JSONDecodeError:
                        tool_input = {}
                    current_tool["input"] = tool_input
                    tool_use_blocks.append(current_tool)
                    current_tool = None

        # 检查是否有工具调用
        if not tool_use_blocks:
            # 没有工具调用，对话结束
            conv.add_assistant_message(assistant_text or "(no response)")
            return

        # 有工具调用
        print()  # 换行
        conv.add_assistant_message(assistant_text)

        # 构造 tool_result content blocks
        tool_results = []

        for tool in tool_use_blocks:
            tool_name = tool["name"]
            tool_input = tool.get("input", {})
            tool_id = tool["id"]

            print(f"  [{tool_name}] {json.dumps(tool_input, ensure_ascii=False)[:100]}")

            raw = (_registry.execute_tool(tool_name, tool_input) if _registry
                    else execute_tool(tool_name, tool_input))
            result_text = raw.text if hasattr(raw, 'text') else str(raw)

            if len(result_text) > 4000:
                result_text = result_text[:4000] + "\n... (truncated)"

            if git and tool_name in ("write_file", "run_shell") and "error" not in result_text.lower():
                detail = tool_input.get("file_path") or tool_input.get("command", "")[:80]
                git.commit_change(tool_name, detail)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result_text,
            })

        # 添加工具结果
        conv.messages.append({
            "role": "user",
            "content": tool_results,
        })

        # 继续循环，让 AI 看到工具结果后回复

    print("  max tool call iterations reached")




# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    # 统一模块名，避免 __main__ 和 agent 全局变量不同步
    import sys as _sys
    _sys.modules["agent"] = _sys.modules["__main__"]
    main()
