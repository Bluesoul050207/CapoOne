# AI Agent MVP — 个人 AI 电脑助手

24 个工具 · 三模型智能路由 · 工程化安全网 · Web 管理面板

## 入口

```powershell
python agent.py              # 终端聊天
python server.py             # 手机 Web (端口 8898)
python admin_server.py       # 管理面板 (端口 8900)
```

## 架构

```
用户输入 → ModelPool 路由 → Worker (DS/Qwen) 调工具 → 筛选层 → GLM 润色 → 输出

Worker 只管干活 ──→ 输出原始事实
  筛选层砍客服腔 ──→ 干净文本
  GLM 加 Lain 语气 ──→ 最终输出
```

## 模型分工

| 模型 | 角色 | System Prompt |
|------|------|------|
| DeepSeek-Chat | Worker — 复杂任务 | 执行纪律 + 工具规则 + 工作约束 |
| Qwen-Plus | Worker — 简单任务 | 同上（共享 Worker Prompt） |
| GLM-4-Flash | Persona — 润色 | Lain 人设 + 行为风格 + 用户记忆 |

## 24 个工具

| # | 工具 | 功能 |
|------|------|------|
| 1 | `read_file` | 读文件带行号 |
| 2 | `write_file` | 写文件(需确认) |
| 3 | `list_directory` | 列目录 |
| 4 | `run_shell` | 执行命令(危险需确认) |
| 5 | `search_content` | 正则搜索 |
| 6 | `move_file` | 移动/重命名 |
| 7 | `web_search` | Tavily 搜索 |
| 8 | `web_fetch` | 抓取网页 |
| 9 | `process_list` | 进程列表 |
| 10 | `process_kill` | 杀进程(需确认) |
| 11 | `process_start` | 启动程序 |
| 12 | `clipboard_read` | 读剪贴板 |
| 13 | `clipboard_write` | 写剪贴板 |
| 14 | `screenshot` | 截屏 |
| 15 | `cmd_help` | CLI 命令帮助 |
| 16 | `cmd_run` | 执行 CLI 注册表命令 |
| 17 | `ncm_play` | 网易云搜播(多试+映射+URL直通) |
| 18 | `save_memory` | 保存记忆(关键词触发) |
| 19 | `temp_rule` | 临时规则(会话级) |
| 20 | `window_list` | 列出窗口 |
| 21 | `window_minimize` | 最小化窗口 |
| 22 | `window_restore` | 恢复聚焦窗口 |
| 23 | `quick_note` | 快捷备忘 |
| 24 | `system_status` | CPU/内存/磁盘/电池 |

## 工程化安全网

| 层 | 机制 |
|------|------|
| 路由 | 智能分流 — 简单活 Qwen / 复杂活 DS / 故障自动转移 |
| 恢复 | RECOVERY 字典 — 工具失败自动注入针对性恢复指令 |
| 推进 | POST_TOOL_HINTS — web_search 后强制 web_fetch |
| 检查 | 任务完成检查 — 用户要放歌但没调 ncm_play → 强制推回 |
| 过滤 | 筛选层 — 砍客服腔/emoji/自我介绍 |
| 兜底 | ncm 多试查询 + 查询净化 + song_map URL 直通 |
| 验证 | 工具验证器 — ok=true 但结果不对自动标失败 |
| 确认 | 写文件/杀进程/危险命令需用户 y/n |

## 项目结构

```
agent.py             终端入口
server.py            Web 服务 + 手机端 HTML
admin_server.py      管理面板 (独立 8900)
config.py            集中配置 (模型/路由/RECOVERY/价格)
core/                框架层 (agent_loop, backend, format_convert, conversation, registry)
modules/executor/    工具执行层 (24 handlers + ToolResult)
modules/persona/     人格系统 (PersonaDB, SongMapDB)
memory/              数据库 + 编辑器
templates/           前端 HTML
tests/               37 个测试
```

## 管理面板

`python admin_server.py` → http://127.0.0.1:8900

五个 tab：Worker Rules / Persona Rules / Profile / Memories / Song Maps。全 CRUD 可视化。

## 技术栈

Python 3.12 · FastAPI · WebSocket · SQLite · DeepSeek · Qwen · GLM · Tavily · psutil

## 快速开始

```powershell
# 设 API Key
$env:DEEPSEEK_API_KEY="sk-..."
$env:DASHSCOPE_API_KEY="sk-..."
$env:GLM_API_KEY="..."
$env:TAVILY_API_KEY="..."

# 启动
python agent.py
```
