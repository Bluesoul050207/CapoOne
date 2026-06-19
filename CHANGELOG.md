# 更新日志

## v0.7.0 — 2026-06-19（架构重构 + 工程化 + 管理面板）

### 架构重构
- agent.py: 1026→532 行，死代码清零，拆分为 core/ (format_convert, conversation, backend)
- server.py: 570→387 行，HTML 外提至 templates/
- 新增 config.py 集中配置

### 三模型智能路由
- ModelPool 多后端池 + 智能路由（简单→Qwen, 复杂→DS, 润色→GLM）
- 故障转移：主模型挂了自动切备用
- 路由可见性 + 音乐意图优先

### System Prompt 分离
- Worker Prompt: 执行纪律 + 工具规则 + constraint 规则 + 记忆
- Persona Prompt: Lain 人设 + behavior 规则 + 记忆
- Memory target: both/worker/persona
- 筛选层 _filter_worker_output: 自动砍客服腔/emoji

### RECOVERY 工程化
- RECOVERY 字典：low_match/file_not_found/no_matches/timeout → 针对性恢复
- POST_TOOL_HINTS: web_search 后强制 web_fetch, cmd_help 后拦截 cmd_run
- 任务完成检查：用户要放歌但 ncm_play 没调 → 强制推回
- 工具验证器: ncm_play/web_search/read_file/write_file 结果验证

### 点歌全链路
- song_map.db 独立存储（三级匹配：精确→子串→CJK模糊）
- ncm_play: 查询净化 + 自动多试 + URL 直通 + 恢复链自动存映射
- URL 映射精确直达，不走 API 搜索

### 记忆 + 权限
- save_rule 卸掉写权限（Admin 面板手动写）
- save_memory 关键词触发（说"记住"才真写）
- temp_rule: 对话内临时规则，会话结束忘

### 新工具 (5个)
- `move_file`: 移动/重命名
- `window_list / window_minimize / window_restore`: 窗口管理
- `quick_note`: 快捷备忘
- `system_status`: CPU/内存/磁盘/电池

### Admin 面板
- admin_server.py: 独立 Web 管理 (端口 8900)
- 蓝白 UI: Profile / Worker Rules / Persona Rules / Memories / Song Maps
- 完整 CRUD + 增删改查可视化

### 对话持久化修复
- DB 加 metadata 列存 tool_calls
- 对话恢复不丢工具调用记录

### 测试
- 37 个测试: ToolResult / 格式转换 / RECOVERY / Handler

### 数据
- 新增 2664 行，删除 978 行
- 35 个文件变更
- 24 个工具，23 个工具 (save_rule 卸掉)

---

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
