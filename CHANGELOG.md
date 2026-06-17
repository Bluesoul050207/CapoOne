# 更新日志

## v0.3.0 — 2026-06-17（CLI 注册表 + 网易云接入）

### 新增
- **CLI 注册表**：`cli_registry.json` + `cmd_help`/`cmd_run` 通用命令执行器
- **网易云音乐**：搜歌 → 网页跳桌面端 → 自动播放（含 VIP 歌曲）
- ncm-cli 集成、mpv 安装、Node.js 环境配置
- `start` 协议唤起桌面端

### 修改
- 清理 GUI 自动化死代码（ReAct、pywinauto、mouse_keyboard）
- `run_shell` UTF-8 编码修复
- `process_start` 路径检查 + PATH 回退

---

## v0.2.2 — 2026-06-17（对话持久化 + 会话管理）

### 新增
- SQLite 对话持久化：关掉重开接着聊
- 多会话管理：`/sessions`、`/session switch/delete/new`
- `/git log`、`/git undo` 命令
- 手机端会话自动恢复

### 修改
- 历史消息加载限制 16 条 + 分隔线
- 死代码清理：SSE `/chat`、`process_turn_openai` 移除
- server.py 减 130 行、agent.py 减 126 行

---

## v0.2.1 — 2026-06-16（结构化返回值 + 手部工具）

### 新增
- **ToolResult** 结构化返回值（ok/text/error）
- **进程管理**：process_list / process_kill / process_start
- **剪贴板**：clipboard_read / clipboard_write
- **截屏**：screenshot
- **Git 管理**：git_manager，会话自动分支 + 自动 commit

### 修改
- 9 个现有 handler 兼容 ToolResult
- emit() 支持 kwargs
- JSONL 日志记录 tool_call

---

## v0.2.0 — 2026-06-15（双模型 + 人格系统 + WebSocket）

### 新增
- **双模型架构**：DeepSeek Worker + GLM Persona（Lain 润色）
- **人格系统**：Profile / Rules / Memories 三表 + 编辑器 CLI
- **WebSocket**：替换 SSE，手机端双向实时
- 确认流程手机端 y/n 异步处理
- `/persona on|off`、`/rules` 命令
- 会话持久化 SQLite

### 修改
- agent.py 和 server.py 统一用 `core/agent_loop.py`
- 手机缓存禁用（HTTP 头 + meta 标签）
- emoji 过滤完善的 prompt 规则

---

## v0.1.0 — 2026-06-14（项目初始化）

### 新增
- 终端 + 手机 Web 双入口
- 5 个基础工具：read_file / write_file / list_directory / run_shell / search_content
- DeepSeek + Anthropic 双后端
- 模块化框架：BaseModule + ModuleRegistry
- JSONL 结构化日志
- 手机端 chat + shell 双 tab
- 流式输出 + 危险命令确认
