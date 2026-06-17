# Agent 项目指令速查

> 最后更新: 2026-06-15  
> 项目路径: `C:\Users\15175\ai-agent-mvp`

---

## agent.py — 终端聊天

```powershell
python agent.py
```

| 指令 | 作用 |
|------|------|
| `/persona on` | 开启人格模块 |
| `/persona off` | 关闭人格模块 |
| `/persona` | 查看人格状态 |
| `/rules` | 查看当前所有约束 |
| `/clear` | 清除对话记忆 |
| `/history` | 查看对话轮数 |
| `/backend` | 查看后端和模型 |
| `/sessions` | 查看所有会话 |
| `/session new <名>` | 新建会话 |
| `/session switch <id>` | 切换会话 |
| `/git log` | 查看 Git 提交记录 |
| `/git undo` | 回退最近一次提交 |
| `/image <路径>` | 发送图片（需 Anthropic） |
| `/save <文件名>` | 保存对话为 JSON |
| `/exit` | 退出 |

**示例：**
```
> /persona off         关闭人格
> /rules               看约束
> /clear               重开对话
> /exit                退出
```

---

## server.py — 手机 Web 服务

```powershell
python server.py
```

手机浏览器打开提示的 LAN 地址（如 `http://10.30.57.119:8898`）。

| 操作 | 怎么用 |
|------|------|
| chat tab | 打字聊天，AI 自动调工具 |
| shell tab | 直接跑 PowerShell 命令 |
| send 按钮 | 发送消息 |
| cancel 按钮 | 取消当前请求 |
| clear 按钮 | 清空所有会话 |
| 确认弹窗 | 工具需批准时输入 `y` 确认 |

---

## modules/persona/editor.py — 人格编辑器

### 命令行模式

```powershell
python modules/persona/editor.py <子命令>
```

| 子命令 | 作用 |
|------|------|
| `show` | 看全部规则 + 记忆 + prompt 预览 |
| `rules` | 列出所有规则 |
| `add "内容"` | 加一条约束规则 |
| `add-behavior "内容"` | 加一条行为风格 |
| `edit 3 "新内容"` | 编辑第 3 条规则 |
| `toggle 3` | 开关第 3 条规则 |
| `delete 3` | 删除第 3 条规则 |
| `mem` | 列出所有记忆 |
| `set <key> <value>` | 设一条长期记忆 |
| `del <key>` | 删除一条记忆 |
| `preview` | 预览拼好的 system prompt |

**示例：**
```powershell
python modules/persona/editor.py add-rule "回复中禁止用英文缩写"
python modules/persona/editor.py set-mem "user_os" "Windows 11"
python modules/persona/editor.py toggle 3
python modules/persona/editor.py show
```

### 交互模式

不跟子命令，直接回车进入交互模式：

```powershell
python modules/persona/editor.py
```

会出现 `persona>` 提示符，连续敲命令，不用每次打全路径：

```
persona> show
persona> add-rule 每条回复不超过50字
persona> toggle 5
persona> exit
```

适合反复调试人格设定时用。

---

## 项目结构速览

```
ai-agent-mvp/
├── agent.py                终端入口
├── server.py               Web 服务入口
├── core/                   框架（Module、Registry、Logger）
├── modules/
│   ├── executor/           执行器模块（5 个工具 handler）
│   └── persona/            人格模块（DB + 编辑器）
├── logs/                   JSONL 日志
├── memory/                 persona.db
└── requirements.txt
```
