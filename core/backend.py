"""
backend — LLM 后端检测、客户端创建、三模型智能路由
支持 Anthropic / DeepSeek / Qwen / GLM / OpenAI / Gemini
"""

import os
import sys

# 导入集中配置
from config import (
    MODEL_NAMES, API_KEY_ENVS, API_BASE_URLS,
    MAX_HISTORY, DANGEROUS_COMMANDS,
    COMPLEX_SIGNALS, SIMPLE_SIGNALS, DEFAULT_WORKER,
    MODEL_OVERRIDE,
)

# 向后兼容的别名
MODEL = MODEL_NAMES["anthropic"]
_MODEL_NAMES = MODEL_NAMES
MODEL_DISPLAY = MODEL_OVERRIDE

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


# ---- 后端检测与客户端创建（保留向后兼容） ----

def detect_backend() -> tuple[str, str]:
    """
    检测可用的后端，返回 (backend_name, reason)
    优先级: ANTHROPIC > DEEPSEEK > QWEN > OPENAI
    """
    from_env = os.environ.get("AI_BACKEND", "").lower()

    if from_env == "anthropic" and HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", "环境变量 AI_BACKEND=anthropic"
    if from_env == "deepseek" and HAS_OPENAI and os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek", "环境变量 AI_BACKEND=deepseek"
    if from_env == "openai" and HAS_OPENAI and (os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
        return "openai", "环境变量 AI_BACKEND=openai"
    if from_env == "qwen" and HAS_OPENAI and os.environ.get("DASHSCOPE_API_KEY"):
        return "qwen", "环境变量 AI_BACKEND=qwen"

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
    """根据后端名创建对应的客户端。API Key 和 Base URL 从 config.py 读取。"""
    key_env = API_KEY_ENVS.get(backend, "")
    api_key = os.environ.get(key_env, "")
    base_url = API_BASE_URLS.get(backend, "")

    if backend == "anthropic":
        return Anthropic()
    elif backend == "deepseek":
        return OpenAI(api_key=api_key, base_url=base_url)
    elif backend == "qwen":
        return OpenAI(api_key=api_key, base_url=base_url)
    elif backend == "glm":
        return OpenAI(api_key=api_key, base_url=base_url)
    elif backend == "gemini":
        return OpenAI(api_key=api_key, base_url=base_url)
    elif backend == "openai":
        return OpenAI(api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"))
    raise ValueError(f"未知后端: {backend}")


# ============================================================
# ModelPool — 多模型池 + 智能路由
# ============================================================

class ModelPool:
    """管理多个 LLM 后端，按任务复杂度自动路由。

    用法:
      pool = ModelPool()
      client, model_name = pool.route("播放 晴天")   # → Qwen
      client, model_name = pool.route("帮我分析代码")  # → DeepSeek
    """

    def __init__(self):
        self.clients: dict[str, object] = {}       # backend → client
        self.model_names: dict[str, str] = {}       # backend → model_name
        self.available: list[str] = []              # 可用的 backend 列表
        self._mode: str = "auto"                    # auto | deepseek | qwen | ...
        self._init_pool()

    def _init_pool(self):
        """初始化所有可用的模型客户端"""
        # 检查用户是否强制指定了某个后端
        from_env = os.environ.get("AI_BACKEND", "").lower()
        if from_env and from_env != "auto":
            self._mode = from_env
            # 只初始化用户指定的后端
            if from_env in ("deepseek", "qwen", "openai", "anthropic"):
                if self._has_key(from_env):
                    self.clients[from_env] = get_client(from_env)
                    self.model_names[from_env] = MODEL_DISPLAY or _MODEL_NAMES.get(from_env, from_env)
                    self.available.append(from_env)
            return

        # auto 模式：初始化所有可用的后端
        self._mode = "auto"
        for backend in ("deepseek", "qwen", "openai", "anthropic", "gemini"):
            if self._has_key(backend):
                try:
                    self.clients[backend] = get_client(backend)
                    self.model_names[backend] = MODEL_DISPLAY or _MODEL_NAMES.get(backend, backend)
                    self.available.append(backend)
                except Exception:
                    pass

        if not self.available:
            print("agent: no backend available. set one of:")
            print("  DEEPSEEK_API_KEY  (DeepSeek, 复杂任务)")
            print("  DASHSCOPE_API_KEY (Qwen, 简单任务)")
            print("  ANTHROPIC_API_KEY")
            sys.exit(1)

    @staticmethod
    def _has_key(backend: str) -> bool:
        """检查是否有对应后端的 API Key"""
        key_env = API_KEY_ENVS.get(backend, "")
        return os.environ.get(key_env, "") != ""

    def route(self, user_input: str) -> tuple[object, str]:
        """根据用户输入路由到最合适的模型。
        返回 (client, model_name)
        """
        # 用户强制模式 → 直接用
        if self._mode != "auto":
            backend = self._mode
            if backend in self.clients:
                return self.clients[backend], self.model_names[backend]
            # 降级到第一个可用的
            backend = self.available[0]
            return self.clients[backend], self.model_names[backend]

        # 智能路由
        text = user_input.lower()

        # 0. 简单意图优先：即使含"搜索"关键词，这些场景仍是简单活
        #    音乐:"搜索+播放" = ncm_play | 打开:"打开X搜索Y" = 打开网页
        simple_intent = ("播放" in text or "放首歌" in text or "来首" in text or
                         "点歌" in text or "放一下" in text or "听" in text or "歌" in text or
                         "打开" in text or "放" in text or "唱" in text)

        # 1. 先检查复杂信号 → DeepSeek（简单意图除外）
        if "deepseek" in self.clients and not simple_intent:
            for signal in COMPLEX_SIGNALS:
                if signal in text:
                    return self.clients["deepseek"], self.model_names["deepseek"]

        # 2. 简单信号 → Qwen（没命中复杂信号才算）
        if "qwen" in self.clients:
            for signal in SIMPLE_SIGNALS:
                if signal in text:
                    return self.clients["qwen"], self.model_names["qwen"]

        # 3. 默认 → DEFAULT_WORKER（DS），不可用时降级
        if DEFAULT_WORKER in self.clients:
            return self.clients[DEFAULT_WORKER], self.model_names[DEFAULT_WORKER]

        # 4. 最终降级
        backend = self.available[0]
        return self.clients[backend], self.model_names[backend]

    def get_backend_name(self, model_name: str) -> str:
        """根据 model_name 反查后端名（用于显示）"""
        for backend, name in self.model_names.items():
            if name == model_name:
                return backend
        return model_name

    def get_fallback(self, exclude_model: str) -> tuple[object, str] | None:
        """获取备用模型（当前模型挂了时用）。
        返回 (client, model_name) 或 None（没有备用）。
        """
        exclude_backend = self.get_backend_name(exclude_model)
        for backend in self.available:
            if backend != exclude_backend:
                return self.clients[backend], self.model_names[backend]
        return None

    def status(self) -> str:
        """返回当前池状态，用于启动时打印"""
        lines = []
        for backend in self.available:
            marker = "→" if (self._mode != "auto" and backend == self._mode) or \
                            (self._mode == "auto" and backend == DEFAULT_WORKER) else " "
            lines.append(f"  [{marker}] {backend}: {self.model_names[backend]}")
        mode_str = self._mode if self._mode != "auto" else f"auto (default: {DEFAULT_WORKER})"
        return f"routing: {mode_str}\n" + "\n".join(lines) if lines else "no backends"
