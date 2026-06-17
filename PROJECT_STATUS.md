# 项目状态总览 2026-06-16

## 一、项目结构

```
ai-agent-mvp/
├── agent.py              终端入口 — 命令行聊天，双模型 + 模块系统
├── server.py              Web 入口  — 手机浏览器连，共用 agent 后端
├── core/                  框架层
│   ├── module.py          BaseModule — 所有模块的基类（生命周期、钩子）
│   ├── registry.py        ModuleRegistry — 加载/卸载/查询/聚合模块
│   ├── logger.py          SessionLogger — JSONL 结构化日志
│   └── git_manager.py     GitManager — 会话分支 + 自动 commit
├── modules/
│   ├── executor/          执行器模块 — 5 个电脑操作工具
│   │   ├── module.py      ExecutorModule(Module)
│   │   └── handlers/      每个工具独立一个文件
│   │       ├── base.py        工具基类
│   │       ├── read_file.py   读文件
│   │       ├── write_file.py  写文件（需确认）
│   │       ├── list_dir.py    列目录
│   │       ├── run_shell.py   跑命令（危险命令需确认）
│   │       └── search.py      搜内容
│   └── persona/           人格模块 — AI 性格管理
│       ├── module.py      PersonaModule — 动态注入 system prompt
│       ├── db.py          SQLite — 4 张表（profile/rules/memories）
│       └── editor.py      CLI 编辑器 — 增删改查人格设定
├── memory/                存放 persona.db
├── logs/                  存放 JSONL 日志
├── COMMANDS.md            指令速查
└── PROJECT_STATUS.md      本文件
```

## 二、入口与运行

| 入口 | 命令 | 用途 |
|------|------|------|
| 终端 | `python agent.py` | PC 命令行聊天 |
| 手机 | `python server.py` | 手机浏览器连 `http://<LAN-IP>:8898` |
| 编辑器 | `python modules/persona/editor.py` | 管理人格设定 |

## 三、功能清单

### 3.1 已实现

| 功能 | 状态 | 说明 |
|------|------|------|
| 5 个电脑操作工具 | ✅ | read_file, write_file, list_directory, run_shell, search_content |
| 双模型架构 | ✅ | Worker (DeepSeek) 干活 + Persona (GLM) 润色人格 |
| 人格系统 | ✅ | Profile + Rules + Memories 三表，动态拼 system prompt |
| 人格编辑器 | ✅ | CLI 工具，命令行/交互模式 |
| 手机端 Web UI | ✅ | chat tab + shell tab，确认弹窗，取消按钮 |
| 手机端进度反馈 | ✅ | thinking/rephrasing/tool/tool_result 状态流 |
| JSONL 结构化日志 | ✅ | 每次工具调用自动记录 |
| Git 会话管理 | ✅ | 启动建分支，write_file/run_shell 自动 commit |
| `/git log` `/git undo` | ✅ | 查看提交记录，回退 |
| `/persona on/off` | ✅ | 运行时开关人格模块 |
| `/rules` | ✅ | 查看当前约束列表 |
| emoji 过滤 | ✅ | 代码层 + prompt 层 |
| 危险命令审批 | ✅ | 黑名单 + 手机端 y/n 确认 |
| 多后端支持 | ✅ | DeepSeek / GLM / Anthropic / OpenAI |

### 3.2 未实现

| 功能 | 状态 | 备注 |
|------|------|------|
| Examples 样本表 | ❌ | 人格第四张表，对话样本训练 Lain |
| web_fetch 联网搜索 | ❌ | 新工具 |
| 对话持久化 | ❌ | 关了重开接着聊 |
| WebSocket 替换 SSE | ❌ | 双向实时 |
| 会话管理 | ❌ | 多会话并存/切换 |
| 进程管理工具 | ❌ | 新工具 |
| 截图工具 | ❌ | 新工具 |
| TTS 语音 | ❌ | 远期 |

## 四、人格系统（三张表）

| 表 | 问题 | 例子 | 命令 |
|------|------|------|------|
| **Profile** | AI 是谁 | Lain，14岁，说话轻柔 | `set-profile "xxx"` |
| **Rules** | 怎么做 | 句尾用……呢吧，不用 emoji | `add-rule "xxx"` |
| **Memories** | 知道什么 | 用户用 Win11，项目在 D 盘 | `set-mem key val` |

Profile 拼成 `你是{profile}` 放 system prompt 最前面。Rules 和 Memories 拼成列表跟在后面。

## 五、终端聊天命令

| 命令 | 作用 |
|------|------|
| `/persona on/off` | 开关人格 |
| `/rules` | 查规则 |
| `/clear` | 清对话 |
| `/history` | 对话轮数 |
| `/backend` | 当前模型 |
| `/git log` | 查看提交 |
| `/git undo` | 回退提交 |
| `/exit` | 退出 |

## 六、已知问题

| 问题 | 状态 |
|------|------|
| DeepSeek 自报 Claude 身份 | 双模型缓解，GLM 润色后不出现 |
| 旧 server 进程残留 | 需手动 Ctrl+C，重启前关旧 |
| 导入快照 bug | server.py 改用 `import agent as _ag` 已修 |

## 七、API Key 配置

| 用途 | 环境变量 | 来源 |
|------|------|------|
| 干活模型 | DEEPSEEK_API_KEY | platform.deepseek.com |
| 人格模型 | GLM_API_KEY | open.bigmodel.cn |
| 备用 | ANTHROPIC_API_KEY | console.anthropic.com |
