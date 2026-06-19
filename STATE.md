# AI Agent MVP — 项目状态移交报告

> v0.7.0 — 2026-06-19。写给新窗口的自己。

## 项目概况

- 24 个工具，三模型智能路由，工程化安全网，Web 管理面板
- ~4200 行 Python + 37 个测试
- GitHub: Bluesoul050207/CapoOne (main 分支)

## 入口

```
python agent.py             终端聊天
python server.py            Web 服务 (手机 :8898)
python admin_server.py      管理面板 (端口 :8900)
python memory/editors/edit_persona.py  人格编辑器
python memory/editors/edit_songs.py    歌名编辑器
```

## 当前使用模型

- Worker 简单任务: Qwen-Plus (阿里 DashScope)
- Worker 复杂任务: DeepSeek-Chat
- Persona: GLM-4-Flash (智谱)
- 自动路由：AI_BACKEND=auto（默认），=deepseek 强制 DS，=qwen 强制 Qwen

## 项目结构

```
agent.py             终端入口 — CLI 命令、模型初始化、主循环
server.py            Web 入口 — FastAPI + WebSocket + 手机 HTML
admin_server.py      管理面板 — 独立 Web，端口 8900
config.py            集中配置 — 模型名、路由规则、RECOVERY、价格

core/                框架层（不依赖任何 handler）
├── agent_loop.py    核心循环 — API调用→工具执行→反思注入→润色
├── backend.py       模型池 — 多后端自动发现 + 智能路由 + 故障转移
├── format_convert.py 格式桥 — Anthropic↔OpenAI 消息/工具互转
├── conversation.py  对话管理 — 消息历史 + 滑动窗口
├── registry.py      模块注册 — 加载/工具聚合/验证分发
├── module.py        模块基类 — BaseModule 生命周期
├── conversation_db.py 对话持久化 — SQLite + metadata
├── git_manager.py   Git 管理 — 自动分支 + commit
├── logger.py        日志 — JSONL 结构化记录
└── token_tracker.py Token 追踪 — 成本估算空壳

modules/
├── executor/        工具执行层
│   ├── module.py    ExecutorModule — 工具注册/执行/验证
│   ├── tool_result.py ToolResult(ok, text, error) 值对象
│   └── handlers/    24 个工具，每个独立文件
└── persona/         人格系统
    ├── module.py    PersonaModule — Worker/Persona 双 prompt 构建
    ├── db.py        PersonaDB — Profile/Rules/Memories CRUD
    └── song_map.py  SongMapDB — 歌名映射独立存储

memory/              数据存储
├── persona.db        人格数据库
├── song_map.db       歌名映射库 (不进入 system prompt)
├── conversation.db   对话历史库
├── editors/
│   ├── edit_persona.py
│   └── edit_songs.py
└── notes.md / screenshots/

tests/               37 个测试
templates/
└── index.html        手机端聊天 UI
```

## 24 个工具

| # | 工具 | 功能 |
|------|------|------|
| 1 | read_file | 读文件带行号 |
| 2 | write_file | 写文件(需确认) |
| 3 | list_directory | 列目录 |
| 4 | run_shell | 执行命令(危险需确认) |
| 5 | search_content | 正则搜索 |
| 6 | move_file | 移动/重命名 |
| 7 | web_search | Tavily 搜索 |
| 8 | web_fetch | 抓取网页 |
| 9 | process_list | 进程列表 |
| 10 | process_kill | 杀进程(需确认) |
| 11 | process_start | 启动程序 |
| 12 | clipboard_read | 读剪贴板 |
| 13 | clipboard_write | 写剪贴板 |
| 14 | screenshot | 截屏 |
| 15 | cmd_help | CLI 命令帮助 |
| 16 | cmd_run | 执行 CLI 注册表命令 |
| 17 | ncm_play | 网易云搜播(多试+映射+URL直通) |
| 18 | save_memory | 保存记忆(需说"记住"才真写) |
| 19 | temp_rule | 临时规则(会话级，不写DB) |
| 20 | window_list | 列出窗口 |
| 21 | window_minimize | 最小化窗口 |
| 22 | window_restore | 恢复聚焦窗口 |
| 23 | quick_note | 快捷备忘到 notes.md |
| 24 | system_status | CPU/内存/磁盘/电池 |

## 数据流

```
用户输入 → ModelPool.route() 智能分流
  ├── 简单(Qwen) / 复杂(DS)
  └── Worker 调工具 → 筛选层砍客服腔 → GLM 加 Lain 语气 → 输出
```

## 工程化安全网

| 层 | 机制 |
|------|------|
| 代码强制执行 | song_map 替换 query / URL 直通 |
| 代码强制恢复 | RECOVERY 字典 — 失败自动注入恢复指令 |
| 代码强制推进 | POST_TOOL_HINTS — 搜完必须读 / cmd_help 后拦 cmd_run |
| 代码强制检查 | 任务完成检查 — 要放歌没调 ncm_play → 推回去 |
| 代码强制清理 | _filter_worker_output — 自动砍客服腔 |
| 代码兜底 | ncm 多试查询 + 查询净化 |
| 人工兜底 | Admin 面板 — 手动增删改查 |

## System Prompt 分离

- Worker Prompt (DS/Qwen): SYSTEM_PROMPT + constraint 规则 + memories(target=both/worker)
- Persona Prompt (GLM): Profile + behavior 规则 + memories(target=both/persona)
- Memory target 三种: both(都看), worker(只Worker), persona(只Persona)

## API Key 配置

- DEEPSEEK_API_KEY: DeepSeek
- DASHSCOPE_API_KEY: Qwen
- GLM_API_KEY: GLM (人格 + 备用 Worker)
- TAVILY_API_KEY: 网页搜索
- GEMINI_API_KEY: Gemini (预留，config.py 已配端点)

## 用户偏好

- 人格: 岩仓铃音 (Lain)，14岁
- 设备: 机械革命笔记本 Win11
- 项目路径: C:\Users\15175\ai-agent-mvp

## 当前问题

1. 无多模态视觉 — 需要 Gemini Key 或 Anthropic Key
2. Worker 偶发幻觉 — 干了活也调不相关的工具
3. save_memory 被卸 — 工作规则只能 Admin 面板手动写
4. 仅支持 Windows
