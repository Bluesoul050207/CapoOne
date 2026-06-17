# AI Agent MVP

个人 AI Agent 助手，能操作电脑、控制软件、管理文件。17 个工具 + 双模型人格 + 手机远程 + CLI 注册表。

## 入口

```powershell
python agent.py          # 终端聊天
python server.py         # 手机 Web（同端口 :8898）
python modules/persona/editor.py   # 人格编辑器
```

## 核心能力

- **17 个工具**：文件读写、进程管理、剪贴板、网页搜索、CLI 命令注册表
- **双模型**：DeepSeek 干活 + GLM 演 Lain 人格
- **手机端**：WebSocket 实时双向，chat + shell 双 tab
- **对话持久化**：SQLite 存储，关掉重开接着聊
- **Git 管理**：会话自动分支 + 工具操作自动 commit
- **CLI 注册表**：cmd_help/cmd_run 通用命令执行器，网易云搜歌播放已接入

## 技术栈

Python 3.12 · FastAPI + WebSocket · SQLite · DeepSeek API · GLM API · Tavily Search · pywinauto · pyautogui

## 项目结构

```
ai-agent-mvp/
├── agent.py                    终端入口
├── server.py                   Web 服务 + 手机前端
├── core/                       框架层（模块管理、日志、Agent循环、会话DB、Git）
├── modules/
│   ├── executor/handlers/      17 个工具处理器
│   └── persona/                人格系统（Profile/Rules/Memories + 编辑器）
├── cli_registry.json           CLI 命令注册表
├── memory/                     SQLite 数据库
├── logs/                       JSONL 操作日志
└── requirements.txt
```
