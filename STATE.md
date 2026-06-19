# AI Agent MVP — 项目状态移交报告

> v0.7.1 — 2026-06-19 深夜。Agent 工具本体开发暂缓，下一阶段转向人格扮演。

## 一、项目概况

- **24 个工具**，三模型智能路由，工程化安全网，Web 管理面板
- ~4200 行 Python，37 个测试，~70 个 git commits
- GitHub: `Bluesoul050207/CapoOne` (main 分支)
- 开发周期：2026-06-14 至 2026-06-19（6天）

## 二、入口

```powershell
python agent.py              # 终端聊天（主要使用）
python server.py             # Web 服务 + 手机端 (端口 8898)
python admin_server.py       # 管理面板 (端口 8900)
python -m pytest tests/ -v   # 跑测试
```

## 三、三模型架构

| 模型 | 角色 | System Prompt | API Key 环境变量 |
|------|------|------|------|
| DeepSeek-Chat | Worker — 复杂任务 + 默认 | 执行纪律 + 工具规则 + constraint 规则 + 记忆 | `DEEPSEEK_API_KEY` |
| Qwen3-Max | Worker — 简单任务 | 同上（共享 Worker Prompt） | `DASHSCOPE_API_KEY` |
| GLM-4-Flash | Persona — 润色 | Lain 人设 + behavior 规则 + 记忆 | `GLM_API_KEY` |

**路由逻辑**：`AI_BACKEND=auto`（默认）自动按意图分流。=deepseek/qwen 强制指定。简单意图（放/打开/读/截图）→ Qwen，复杂意图（搜索/分析/写代码）→ DS。音乐意图优先（"搜索+播放"=简单）。

**故障转移**：主模型 API 失败自动切备用。

## 四、项目结构

```
ai-agent-mvp/
│
├── agent.py              [532行] 终端入口 — CLI命令/模型初始化/主循环/筛选层
├── server.py             [387行] Web入口 — FastAPI+WebSocket+Token认证
├── admin_server.py       [360行] 管理面板 — 独立8900端口/蓝白UI/CRUD
├── config.py             [135行] 集中配置 — 模型名/路由规则/RECOVERY/价格
│
├── core/                 框架层
│   ├── agent_loop.py     [350行] 核心循环 — 智能路由→执行→验证→反思→润色
│   ├── backend.py        [214行] 模型池 — 多后端发现/路由/故障转移
│   ├── format_convert.py [111行] Anthropic↔OpenAI格式互转
│   ├── conversation.py   [ 99行] 对话管理 — 历史/滑动窗口/token估算
│   ├── registry.py       [110行] 模块注册 — 加载/聚合工具/验证分发
│   ├── module.py         [ 57行] BaseModule生命周期
│   ├── conversation_db.py[119行] 对话持久化 — SQLite+metadata列
│   ├── git_manager.py    [111行] Git自动分支+commit
│   ├── logger.py         [ 98行] JSONL结构化日志
│   └── token_tracker.py  [ 63行] Token成本估算空壳
│
├── modules/
│   ├── executor/
│   │   ├── module.py         执行器模块
│   │   ├── tool_result.py    ToolResult(ok,text,error)
│   │   └── handlers/         24个工具(每个独立文件)
│   └── persona/
│       ├── module.py         PersonaModule — Worker/Persona双prompt
│       ├── db.py             PersonaDB — Profile/Rules/Memories
│       └── song_map.py       SongMapDB — 歌名映射三级匹配
│
├── memory/
│   ├── persona.db            人格数据库
│   ├── song_map.db           歌名映射 (不进入system prompt)
│   ├── conversation.db       对话历史
│   ├── app_map.json          应用别名 (PCL2→完整路径)
│   ├── editors/              CLI编辑器
│   └── notes.md / screenshots/
│
├── templates/
│   └── index.html           手机端聊天UI
│
└── tests/                    37个测试
```

## 五、24 个工具

| # | 工具 | 功能 | 确认 |
|------|------|------|------|
| 1 | `read_file` | 读文件带行号 | - |
| 2 | `write_file` | 写文件 | 🔒 |
| 3 | `list_directory` | 列目录 | - |
| 4 | `run_shell` | 执行命令 | 🔒危险 |
| 5 | `search_content` | 正则搜索 | - |
| 6 | `move_file` | 移动/重命名 | - |
| 7 | `web_search` | Tavily搜索 | - |
| 8 | `web_fetch` | 抓取网页 | - |
| 9 | `process_list` | 进程列表 | - |
| 10 | `process_kill` | 杀进程 | 🔒 |
| 11 | `process_start` | 启动程序(app_map+常见路径) | - |
| 12 | `clipboard_read` | 读剪贴板 | - |
| 13 | `clipboard_write` | 写剪贴板 | - |
| 14 | `screenshot` | 截屏存PNG | - |
| 15 | `cmd_help` | CLI命令帮助 | - |
| 16 | `cmd_run` | 执行CLI注册表命令 | - |
| 17 | `ncm_play` | 网易云搜播(多试+映射+杀进程重开+URL直通) | - |
| 18 | `save_memory` | 保存记忆(需说"记住"才写) | - |
| 19 | `temp_rule` | 临时规则(会话级,不写DB) | - |
| 20 | `window_list` | 列出窗口 | - |
| 21 | `window_minimize` | 最小化窗口 | - |
| 22 | `window_restore` | 恢复聚焦窗口(ctypes原生API) | - |
| 23 | `quick_note` | 快捷备忘到notes.md | - |
| 24 | `system_status` | CPU/内存/磁盘/电池 | - |

## 六、工程化安全网

| 层 | 机制 | 位置 |
|------|------|------|
| **song_map** | lookup查映射→URL直通/歌名替换→100%生效 | ncm_play handler |
| **RECOVERY** | 7个错误标签→自动注入恢复指令 | agent_loop.py |
| **POST_TOOL_HINTS** | web_search后强制web_fetch / cmd_help后拦cmd_run / ncm_play后问用户 | agent_loop.py |
| **任务检查** | 要放歌没调ncm_play→强制推回 / 搜了没读→强制推回 | agent_loop.py |
| **筛选层** | Worker输出→砍客服腔/emoji/自我介绍→GLM收到干净文本 | agent.py _filter_worker_output |
| **多试+净化** | ncm_play搜不到→去括号/去符号/拆词→最多3次 | ncm_play handler |
| **崩溃保护** | 全函数try/catch / _restart_netease杀进程重开 | ncm_play handler |
| **验证器** | ncm_play/web_search/read_file/write_file结果验证(URL跳过) | 各handler validate |
| **确认门禁** | write_file/process_kill/危险命令需y/n / 空格大小写绕过加固 | agent.py |
| **防污染** | 用户确认后自动截断对话历史到4条 / "是的=嗯嗯" | agent_loop.py |
| **服务器认证** | AUTH_TOKEN环境变量保护WebSocket | server.py |
| **应用别名** | app_map.json + Admin面板 → process_start自动查 | process.py |

## 七、数据流

```
用户输入 → ModelPool.route() 智能分流
  ├── 音乐意图/简单操作 → Qwen3-Max
  ├── 搜索/分析/默认 → DeepSeek-Chat
  └── 主模型挂了 → 自动切fallback

Worker调工具 → 工具内部handler处理
  ├── ncm_play: song_map→API多试→RECOVERY→POST_TOOL_HINT
  ├── process_start: app_map→常见路径→PATH
  └── 其他: 直接执行

Worker输出原始文本 → _filter_worker_output() 砍客服腔
  → GLM(_rephrase_with_persona) 加Lain语气 → 最终输出

任务完成/用户确认 → 对话历史自动截断到4条 → 防污染
```

## 八、System Prompt 分离

- **Worker Prompt** (DS/Qwen): SYSTEM_PROMPT + constraint规则 + memories(target=both/worker)
- **Persona Prompt** (GLM): Profile + behavior规则 + memories(target=both/persona)
- **memory target**: `both`(都看) / `worker`(仅Worker) / `persona`(仅GLM)
- **筛选层**: Worker输出→_filter_worker_output砍客服腔→GLM只加语气

## 九、管理面板

`python admin_server.py` → http://127.0.0.1:8900

六个 tab：Worker Rules / Persona Rules / Profile / Memories / Song Maps / App Maps
全部支持增删改查（Edit按钮→行内编辑→Save）

## 十、三个手动维护的数据文件

| 文件 | 用途 | 编辑方式 |
|------|------|------|
| `memory/persona.db` | Profile + Rules + Memories | Admin面板 或 `memory/editors/edit_persona.py` |
| `memory/song_map.db` | 歌名映射 | Admin面板 或 `memory/editors/edit_songs.py` |
| `memory/app_map.json` | 应用别名 | Admin面板 或直接编辑JSON |

## 十一、当前已知问题

1. **无多模态视觉** — 需要 Gemini Key 或 Anthropic Key。Gemini 端点已在 config.py 预配
2. **上下文污染** — LLM固有问题。已有自动截断+确认检测缓解，无法根治
3. **Worker 偶发幻觉** — 调不相关工具。无法在代码层彻底解决
4. **仅支持 Windows** — 大量 Win32 API
5. **网易云网页桥接不可靠** — `_restart_netease` 缓解但非100%
6. **Qwen3-Max 免费额度有限** — 用完需换模型或付费。模型名在 config.py 一行切换

## 十二、未来方向（按优先级）

| 优先级 | 方向 | 说明 |
|------|------|------|
| **现在** | **人格扮演深化** | 开发重点转向 Persona 层。当前架构已为此做好准备：GLM 有独立 prompt、behavior 规则系统、Profile 编辑器。只需要丰富内容 |
| 高 | 接入 Gemini 视觉 | 已有 Key 就能开。config.py 已配好端点 |
| 中 | TTS 语音输出 | Lain 能"说"出来 |
| 中 | 定时任务/提醒 | "30分钟后提醒我" |
| 低 | 跨平台 | 非 Windows 支持 |
| 低 | 插件系统 | 当前规模不需要 |

## 十三、注意事项

- **不要改 `config.py` 里的模型名格式**：换模型只改 `MODEL_NAMES` 中的值
- **Agent 本体不要大改**：核心循环、工具系统、路由逻辑已经稳定
- **Admin 面板不依赖 Agent**：可以单独跑，只管 DB
- **save_memory 需要用户说"记住"才真写**：关键词检测在 handler 里
- **/clear 是上下文污染的最后手段**：确认后自动截断一般够用
- **app_map.json 是 JSON 格式**：key 全小写，value 写完整路径
- **song_map.db 的值**：URL 直接播放，歌名替换 query 搜索
- **ncm_play 崩溃不会挂掉 agent**：全函数 try/catch
- **git push 可能因为网络失败**：commit 在本地不会丢

## 十四、日常维护

```powershell
# 换模型
notepad config.py  # 改 MODEL_NAMES 对应行

# 加应用别名
python admin_server.py  # → App Maps tab 可视化操作

# 加歌名映射
python admin_server.py  # → Song Maps tab

# 管理人格
python admin_server.py  # → Worker Rules / Persona Rules / Profile / Memories

# 清理对话历史
/clear  # 在 agent 对话中

# 跑测试
python -m pytest tests/ -v

# 更新到 GitHub
git add -A && git commit -m "..." && git push origin main
```
