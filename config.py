"""
config.py — AI Agent MVP 集中配置
所有模型、端点、路由规则、默认值都在这里。
换模型只改这个文件，不动代码。
"""

import os

# ============================================================
# API 端点
# ============================================================

API_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4/",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
}

# ============================================================
# 模型名映射（backend → model name）
# 改模型只改这里，如 qwen-plus → qwen-max
# ============================================================

MODEL_NAMES = {
    "anthropic": "claude-sonnet-4-6",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "openai": "gpt-4o",
    "glm": "glm-4-flash",
    "gemini": "gemini-2.0-flash",
}

# 用户可通过环境变量 AI_MODEL 覆盖
MODEL_OVERRIDE = os.environ.get("AI_MODEL", "")

# ============================================================
# API Key 环境变量映射
# ============================================================

API_KEY_ENVS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "glm": "GLM_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# ============================================================
# 对话限制
# ============================================================

MAX_HISTORY = 32              # 最多保留消息数
MAX_TOOL_ITERATIONS = 6       # 每轮最多工具调用轮数
API_TIMEOUT = 60              # API 超时（秒）
TOOL_TIMEOUT = 30             # 工具执行超时（秒）

# ============================================================
# 危险命令黑名单
# ============================================================

DANGEROUS_COMMANDS = [
    "rm -rf", "del /f", "format",
    "shutdown", "restart", "reg delete",
    ":(){ :|:& };:",            # fork bomb
]

# ============================================================
# 模型路由规则
# ============================================================

COMPLEX_SIGNALS = [
    "搜索", "搜一下", "上网查", "查资料",
    "总结", "概括", "归纳",
    "分析", "解释", "为什么", "怎么", "是什么",
    "对比", "区别", "优缺点", "哪个好",
    "设计", "架构", "原理",
    "写", "改", "修改", "实现", "编", "生成",
    "代码", "函数", "脚本",
    "帮我", "帮忙",
    "review", "fix", "debug", "refactor", "优化",
]

SIMPLE_SIGNALS = [
    "播放", "放首歌", "来首", "放",
    "打开", "启动", "关闭",
    "截图", "截屏",
    "剪贴板", "粘贴", "复制",
    "进程", "kill",
    "读一下", "看一下", "读", "查看", "显示",
    "列目录", "ls", "dir", "pwd",
    "正在运行",
    "音量", "锁屏", "关机", "重启",
]

DEFAULT_WORKER = "deepseek"

# ============================================================
# Token 价格表 ($/1M tokens)
# ============================================================

PRICING = {
    "deepseek-chat":      {"input": 0.27, "output": 1.10},
    "deepseek-reasoner":  {"input": 0.55, "output": 2.19},
    "qwen-plus":          {"input": 0.10, "output": 0.30},
    "qwen-max":           {"input": 0.40, "output": 1.20},
    "glm-4-flash":        {"input": 0.00, "output": 0.00},
    "gemini-2.0-flash":   {"input": 0.00, "output": 0.00},
    "gpt-4o":             {"input": 2.50, "output": 10.00},
    "claude-sonnet-4-6":  {"input": 3.00, "output": 15.00},
}

# ============================================================
# RECOVERY 字典（工具失败时自动注入的恢复指令）
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
    "access_denied": "权限不够。换个路径或方式再试。",
    "unknown_tool": "这个工具不存在。用 cmd_help 看可用工具列表。",
    "timeout": "命令超时了。简化操作或拆成小步骤再试。",
    "not_found": "没找到目标。检查参数是否正确，或换个搜索方式。",
}

FALLBACK_RECOVERY = "上一步失败了。用其他方法再试一次，换工具、换参数、换顺序都行。"
