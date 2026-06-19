# AI Agent MVP — 项目状态移交报告

> 写给新窗口的自己。读完这份报告，你应该完全了解项目当前情况、待解问题和下一步方向。

## 项目概况

- 5 天开发，484 行 agent.py + 385 行 server.py + 核心模块（2026-06-19 优化后）
- 18 个工具 + RECOVERY 错误恢复 + 记忆层已启用 + 37 个测试
- GitHub: Bluesoul050207/CapoOne (main 分支)
- **上次优化**: Phase 1-7 完成，详见下文"优化记录"

## 入口

```
python agent.py       终端聊天
python server.py      Web 服务 (手机 :8898)
python modules/persona/editor.py  人格编辑器
```

## 当前使用模型

- Worker: Qwen-Max (阿里 DashScope) — 听话但推理链短
- Persona: GLM-4-Flash (智谱) — 润色 Lain 语气
- DeepSeek 还在，但 Qwen 对工具调用更积极
- 切回 DS: 改 agent.py 里 detect_backend() 优先级 或 设 AI_BACKEND=deepseek

## 已实现功能

### 18 个工具
- 文件: read_file write_file list_directory run_shell search_content
- 进程: process_list process_kill process_start
- 剪贴板: clipboard_read clipboard_write
- 搜索: web_search(Tavily) web_fetch
- 截屏: screenshot
- CLI 注册表: cmd_help cmd_run (cli_registry.json 驱动)
- 网易云: ncm_play (搜歌→网易云API→cmd start→Chrome跳桌面播放)
- 记忆: save_rule save_memory

### 架构
- 模块框架: BaseModule + ModuleRegistry (core/)
- 反思循环: agent_loop.py 中 run_turn() — 工具失败自动追问，成功追问
- 长期记忆: PersonaModule → persona.db → system prompt 注入
- 双模型: Worker(干活) + Persona(润色语气)
- 结构化值: ToolResult(ok/text/error)
- 手机端: WebSocket + chat/shell 双 tab
- 持久化: SQLite 对话历史 + 多会话
- 人格: Profile/Rules/Memories 三表 + 编辑器
- Git: 自动分支 + 工具 commit

### 网易云搜播流程
  用户说歌名
  → AI 调 ncm_play("歌名")
  → 搜网易云公开 API → 不匹配 → error="low_match"
  → 反思循环 → AI web_search 查原名
  → 再 ncm_play 原名 → 匹配
  → cmd /c start "https://music.163.com/song?id=xxx"
  → Chrome 打开 → 弹"打开客户端" → 桌面端播放
  前提: Chrome 弹窗勾选过"记住我的选择"

## 当前遇到的问题

1. **模型链式推理上限** — Qwen 走 1-2 步就停，DS 能走 3-4 步但偶尔偷懒
2. ~~**找到不动手**~~ — ✅ RECOVERY 字典已实现，错误标签路由自动注入下一步指令
3. **没眼** — 没有多模态模型同时看图+调工具+便宜
4. **模型中转缓** — 有 write_file 不调 press_keys（非 Agent 问题，是操作系统限制）
5. ~~**记忆打架**~~ — ✅ save_memory 已有冲突检测（追加而非覆盖），ncm_play 记忆查询已启用
6. **网易云限制** — ncm-cli 播放仅 Mac，Win 只能网页桥接
7. **并发安全** — WebSocket 确认期间用户的并发消息可能被误消费

## 优化记录 (2026-06-19)

### 已完成 ✅
| Phase | 内容 | 效果 |
|-------|------|------|
| 1 | 删除死代码 (~230行) | agent.py 1026→484 行 |
| 2 | RECOVERY 字典 + 错误标签路由 | 7 个错误标签 → 针对性恢复指令 |
| 3 | 18 个 handler 统一返回 ToolResult | 错误标签不再丢失 |
| 4 | HTML 模板外提 | server.py 570→385 行，前端可独立编辑 |
| 5 | agent.py 拆分为 core/ | format_convert / conversation / backend 三模块 |
| 6 | 记忆层重新启用 | lookup_memory() + 冲突检测 |
| 7 | 基础测试 37 个 | ToolResult/格式转换/RECOVERY/handler 全覆盖 |

### 新增文件结构
```
core/
├── format_convert.py   ← Anthropic↔OpenAI 格式转换
├── conversation.py     ← Conversation 类 + token 计数
├── backend.py          ← LLM 后端检测 + 客户端创建
├── agent_loop.py       ← RECOVERY 字典 + 错误标签路由
templates/
├── index.html          ← 手机端 Web UI
tests/
├── test_tool_result.py
├── test_format_convert.py
├── test_recovery.py
├── test_handlers.py
```

## 待实现

- ~~任务队列 (最高优)~~ → ✅ 已实现为 RECOVERY 字典
- 工具执行验证器 (ok=true 但结果不对→自动标失败)
- 记忆冲突合并策略 (目前追加，未来可做语义去重)
- ncm-cli 原生播放 (需要 Mac 或找 Win 替代方案)
- WebSocket 并发安全修复
- 多模态视觉模型接入

## 关键文件

- agent.py: 入口 + Conversation + 格式转换 + 双模型
- server.py: FastAPI + WebSocket + HTML 前端
- core/agent_loop.py: run_turn() 反思循环
- core/registry.py: ModuleRegistry
- modules/executor/handlers/: 18 个工具
- modules/persona/: 人格系统 (db.py + module.py + editor.py)
- cli_registry.json: CLI 命令模板
- COMMANDS.md: 指令速查

## API Key 配置 (环境变量)

- DASHSCOPE_API_KEY: Qwen
- GLM_API_KEY: GLM
- DEEPSEEK_API_KEY: DeepSeek (备)
- TAVILY_API_KEY: 网页搜索

## 用户偏好

- 人格: 岩仓铃音 (Lain)，14岁。10条规则。
- 设备: 机械革命笔记本 Win11
- 项目路径: C:\Users\15175\ai-agent-mvp
- 网易云路径: D:\MusicCloudYI\CloudMusic\cloudmusic.exe
- 微信路径: D:\Chatsoftware\Weixin\Weixin.exe
