"""
backend — LLM 后端检测与客户端创建
支持 Anthropic / DeepSeek / Qwen / GLM / OpenAI
"""

import os
import sys


# ---- 配置常量 ----

MODEL = "claude-sonnet-4-6"          # 模型，可换成 claude-opus-4-8 等
MAX_HISTORY = 32                      # 最多保留多少轮对话（省 token）
DANGEROUS_COMMANDS = [
    "rm -rf", "del /f", "format",
    "shutdown", "restart", "reg delete",
    ":(){ :|:& };:",                   # fork bomb
]

# ---- 后端可用性检测 ----

try:
    from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

if not HAS_ANTHROPIC and not HAS_OPENAI:
    print("请至少安装一个后端: pip install anthropic 或 pip install openai")
    sys.exit(1)


# ---- 后端检测与客户端创建 ----

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
