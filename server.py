"""
agent server — 手机也能用的 AI 助手
PC 上跑这个，手机浏览器连 http://你的IP:8899
一个页面两个 tab：聊天 + PowerShell
"""

import os
import sys
import json
import re
import asyncio
import signal
import subprocess
from pathlib import Path
from datetime import datetime

# ---- 加载 agent 模块 ----
sys.path.insert(0, str(Path(__file__).parent))
import agent as _agent
_agent.SERVER_MODE = True   # 服务端模式：跳过 confirm_action 的 input() 阻塞
import agent as _ag
from agent import (
    detect_backend, get_client, Conversation,
    MODEL, _init_registry, _get_system_prompt,
    _persona_enabled, set_persona, init_dual_model, _rephrase_with_persona,
)

# ---- 初始化模块系统 ----
_registry = _init_registry()
_dual_available = init_dual_model()

try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:
    print("pip install fastapi uvicorn aiofiles  (需要这三个)")
    sys.exit(1)

# ---- 初始化 ----
backend, reason = detect_backend()
if backend == "none":
    print("no backend available. set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY")
    sys.exit(1)

backend_client = get_client(backend)
model_display = os.environ.get("AI_MODEL") or {
    "anthropic": MODEL, "deepseek": "deepseek-chat", "openai": "gpt-4o",
}.get(backend, "unknown")

app = FastAPI()

# 按会话 ID 存储对话实例
sessions: dict[str, Conversation] = {}


def get_or_create_conv(session_id: str) -> Conversation:
    if session_id not in sessions:
        sessions[session_id] = Conversation(_get_system_prompt())
    return sessions[session_id]


# ---- Shell 执行 ----
@app.post("/shell")
async def shell(request: Request):
    data = await request.json()
    command = data.get("cmd", "").strip()
    cwd = data.get("cwd", os.getcwd())

    if not command:
        return JSONResponse({"output": "(no command)", "cwd": cwd})

    print(f"[shell] {command}")  # 同步到服务端

    # 危险命令拦截
    dangerous = ["rm -rf", "del /f", "format", "shutdown", "restart", "reg delete"]
    for d in dangerous:
        if d in command.lower() and not data.get("confirm"):
            msg = f"DANGEROUS: {command}\nsend again with confirm:true to execute"
            print(f"  {msg.split(chr(10))[0]}")
            return JSONResponse({"output": msg, "cwd": cwd})

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit: {result.returncode}]"
        # 简短输出同步到终端
        preview = output[:200].replace('\n', ' ') + ("..." if len(output) > 200 else "")
        print(f"  -> {preview}")
        return JSONResponse({
            "output": output[:10000] or "(no output)",
            "cwd": cwd,
        })
    except subprocess.TimeoutExpired:
        print("  -> timed out (30s)")
        return JSONResponse({"output": "timed out (30s)", "cwd": cwd})
    except Exception as e:
        print(f"  -> error: {e}")
        return JSONResponse({"output": f"error: {e}", "cwd": cwd})


# ---- HTML 前端 ----
@app.get("/", response_class=HTMLResponse)
async def index():
    from fastapi.responses import Response
    return Response(
        content=HTML, media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                 "Pragma": "no-cache", "Expires": "0"}
    )


# ---- 页面 ----
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>agent v2.2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font:14px/1.5 Consolas,monospace;background:#0d0d0d;color:#c0c0c0;height:100dvh;display:flex;flex-direction:column}
header{display:flex;background:#1a1a1a;border-bottom:1px solid #333}
header button{flex:1;padding:10px;background:none;color:#888;border:none;font:inherit;cursor:pointer}
header button.on{color:#fff;border-bottom:2px solid #5af}
#chat,#shell{flex:1;overflow-y:auto;padding:10px;display:flex;flex-direction:column}
#shell{display:none}
#chatMsgs{flex:1;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
#shellOutput{flex:1;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.inputRow{display:flex;margin-top:8px;gap:6px}
.inputRow input{flex:1;padding:8px;background:#1a1a1a;color:#c0c0c0;border:1px solid #333;font:inherit;outline:none}
.inputRow input:focus{border-color:#5af}
.inputRow button{padding:8px 14px;background:#2a2a2a;color:#c0c0c0;border:1px solid #444;font:inherit;cursor:pointer}
.inputRow button:active{background:#444}
.role{color:#888}
.msg{color:#c0c0c0}
.tool{color:#aaa}
.cwd{color:#555;font-size:12px;padding:4px 0}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:#0d0d0d}
::-webkit-scrollbar-thumb{background:#333}
</style>
</head>
<body>
<header>
  <button id="tabChat" class="on" onclick="switchTab('chat')">chat</button>
  <button id="tabShell" onclick="switchTab('shell')">shell</button>
  <button onclick="killServer()" style="margin-left:auto;color:#f66">clear</button>
</header>

<div id="chat">
  <div id="chatMsgs"></div>
  <div class="inputRow">
    <input id="chatInput" placeholder="say something..." autofocus onkeydown="if(event.key==='Enter')sendChat()">
    <button id="sendBtn" onclick="sendChat()">send</button>
    <button id="cancelBtn" onclick="doCancel()" style="display:none;color:#f66">cancel</button>
  </div>
</div>

<div id="shell">
  <div id="shellOutput"></div>
  <div class="cwd" id="shellCwd">loading...</div>
  <div class="inputRow">
    <input id="shellInput" placeholder="powershell command..." onkeydown="if(event.key==='Enter')sendShell()">
    <button onclick="sendShell()">run</button>
  </div>
</div>

<script>
const SESSION = Date.now().toString(36);
let currentBlock = null;
let shellCwd = '.';

// ---- WebSocket ----
const ws = new WebSocket(`ws://${location.host}/ws/${SESSION}`);
let wsReady = false;

ws.onopen = () => { wsReady = true; appendMsg('tool', 'connected'); };
ws.onclose = () => { wsReady = false; appendMsg('tool', 'disconnected, refresh page'); };

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  const t = msg.type;
  if(t === 'echo') { currentBlock = null; appendMsg('role', '> ' + msg.text); }
  else if(t === 'text') { if(!currentBlock){currentBlock=document.createElement('div');currentBlock.className='msg';document.getElementById('chatMsgs').appendChild(currentBlock);} currentBlock.textContent+=msg.text; }
  else if(t === 'tool'||t === 'tool_result'||t === 'status') { currentBlock=null; appendMsg('tool', (t==='status'?'... ':'') + msg.text); }
  else if(t === 'confirm_needed') { currentBlock=null; appendMsg('tool','[confirm] '+msg.text); appendMsg('tool','reply y/n:'); const ci=document.getElementById('chatInput'); ci.disabled=false; ci.placeholder='y/n'; ci.value=''; ci.focus(); ci.dataset.confirm=msg.text; document.getElementById('sendBtn').style.display=''; document.getElementById('cancelBtn').style.display='none'; }
  else if(t === 'error') { currentBlock=null; appendMsg('tool','error: '+msg.text); }
  else if(t === 'done') { currentBlock=null; document.getElementById('sendBtn').style.display=''; document.getElementById('cancelBtn').style.display='none'; document.getElementById('chatInput').disabled=false; document.getElementById('chatInput').focus(); }
  else if(t === 'connected') { /* ignore */ }
  document.getElementById('chatMsgs').scrollTop = document.getElementById('chatMsgs').scrollHeight;
};

async function doCancel() {
  ws.send(JSON.stringify({type:'cancel'}));
  document.getElementById('chatMsgs').textContent = '';
  document.getElementById('sendBtn').style.display = '';
  document.getElementById('cancelBtn').style.display = 'none';
  document.getElementById('chatInput').disabled = false;
}

function switchTab(t) {
  document.getElementById('chat').style.display = t==='chat' ? 'flex' : 'none';
  document.getElementById('shell').style.display = t==='shell' ? 'flex' : 'none';
  document.getElementById('tabChat').classList.toggle('on', t==='chat');
  document.getElementById('tabShell').classList.toggle('on', t==='shell');
  if(t==='chat') document.getElementById('chatInput').focus();
  if(t==='shell') document.getElementById('shellInput').focus();
}

function appendMsg(type, text) {
  const el = document.createElement('div');
  el.className = type;
  el.textContent = text;
  document.getElementById('chatMsgs').appendChild(el);
  document.getElementById('chatMsgs').scrollTop = document.getElementById('chatMsgs').scrollHeight;
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if(!text) return;

  // 确认模式
  if(input.dataset.confirm) {
    const approved = /^(y|yes|是)$/i.test(text);
    input.dataset.confirm = '';
    input.placeholder = 'say something...';
    input.value = '';
    input.disabled = false;
    ws.send(JSON.stringify({type:'confirm', approved}));
    return;
  }

  input.value = '';
  input.disabled = true;
  document.getElementById('sendBtn').style.display = 'none';
  document.getElementById('cancelBtn').style.display = '';
  currentBlock = null;

  ws.send(JSON.stringify({type:'chat', text}));
}

async function sendShell() {
  const input = document.getElementById('shellInput');
  const cmd = input.value.trim();
  if(!cmd) return;
  input.value = '';
  const out = document.getElementById('shellOutput');
  out.textContent += shellCwd + '> ' + cmd + '\n';

  const resp = await fetch('/shell', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cmd, cwd: shellCwd})
  });
  const data = await resp.json();
  out.textContent += data.output + '\n';
  out.scrollTop = out.scrollHeight;
  if(data.cwd) {
    shellCwd = data.cwd;
    document.getElementById('shellCwd').textContent = 'cwd: ' + shellCwd;
  }
}

// kill server
async function killServer() {
  if(!confirm('clear all sessions?')) return;
  ws.send(JSON.stringify({type:'cancel'}));
  await fetch('/kill', {method:'POST'});
  alert('done');
  location.reload();
  let tries = 0;
  const check = setInterval(async () => {
    try {
      const r = await fetch('/ping');
      if(r.ok) location.reload();
    } catch(e) {}
    tries++;
    if(tries > 60) { clearInterval(check); document.getElementById('retry').textContent = 'giving up. restart manually.'; }
  }, 3000);
}

// init shell cwd
fetch('/shell', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({cmd:'pwd',cwd:'.'})})
  .then(r=>r.json()).then(d=>{
    if(d.cwd) { shellCwd = d.cwd; document.getElementById('shellCwd').textContent = 'cwd: ' + shellCwd; }
  });
</script>
</body>
</html>
"""


# ---- 自清理：杀掉老端口上的残留进程 ----
def _free_port(port: int):
    """杀掉占用指定端口的进程"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr "LISTENING.*:{port}"',
            shell=True, capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 5 and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid != os.getpid():
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
    except Exception:
        pass


# ---- kill 端点：手机也能关服务 ----
@app.post("/kill")
async def kill_server():
    """重置服务：清空所有会话，等同于重启。"""
    sessions.clear()
    return {"status": "reset, all sessions cleared"}




@app.post("/persona/toggle")
async def persona_toggle(request: Request):
    data = await request.json()
    state = data.get("enabled", not _persona_enabled)
    set_persona(bool(state))
    return {"persona_enabled": _persona_enabled}


@app.get("/persona")
async def persona_status():
    return {"persona_enabled": _persona_enabled}


@app.post("/cancel")
async def cancel_session(request: Request):
    """取消当前会话的进行中请求"""
    data = await request.json()
    sid = data.get("session", "default")
    if sid in sessions:
        del sessions[sid]
    return {"status": "cancelled"}


@app.get("/ping")
async def ping():
    return {"status": "alive"}


# ---- WebSocket 双向通信 ----
_ws_db_sessions: dict[str, int] = {}  # WebSocket session → DB session 映射

@app.websocket("/ws/{session_id}")
async def ws_chat(ws: WebSocket, session_id: str):
    print(f"[ws] connected: {session_id}")
    await ws.accept()

    # 加载或创建 DB 会话
    db_sid = None
    cdb = None
    try:
        from core.conversation_db import get_conv_db
        cdb = get_conv_db()
        all_sessions = cdb.list_sessions()
        main = [s for s in all_sessions if s["name"] == "phone-main"]
        if main:
            db_sid = main[0]["id"]
        else:
            db_sid = cdb.create_session("phone-main")
        _ws_db_sessions[session_id] = db_sid
        # 装历史消息
        all_msgs = cdb.load_messages(db_sid)
        recent = all_msgs[-8:]
        if recent:
            conv = get_or_create_conv(session_id)
            conv.messages.clear()
            conv.messages.append({"role": "user", "content": "(以下是之前的对话记录，新对话即将开始)"})
            conv.messages.append({"role": "assistant", "content": "嗯……刚才我们聊到哪了？"})
            for m in recent:
                conv.messages.append({"role": m["role"], "content": m["content"]})
            print(f"[ws] loaded {len(recent)} msgs, conv has {len(conv.messages)}")
            await ws.send_json({"type": "tool", "text": "--- history ---"})
            for m in recent:
                await ws.send_json({"type": "echo", "text": m["content"] if m["role"] == "user" else ""})
                if m["role"] == "assistant":
                    await ws.send_json({"type": "text", "text": m["content"]})
    except Exception as e:
        print(f"[ws] DB error: {e}")
        db_sid = None

    # 发送身份确认
    await ws.send_json({"type": "connected", "session": session_id})

    while True:
        try:
            data = await ws.receive_json()
        except WebSocketDisconnect:
            break
        except Exception:
            continue

        msg_type = data.get("type", "")

        # ---- 确认回复（ws_confirm 已直接处理，这里忽略残留） ----
        if msg_type == "confirm":
            continue

        # ---- 取消 ----
        if msg_type == "cancel":
            if session_id in sessions:
                del sessions[session_id]
            conv = get_or_create_conv(session_id)
            await ws.send_json({"type": "done"})
            continue

        # ---- 聊天 ----
        text = data.get("text", "").strip()
        if not text:
            continue

        conv = get_or_create_conv(session_id)
        conv.add_user_message(text)
        print(f"> {text}")
        await ws.send_json({"type": "echo", "text": text})

        # 同步到会话数据库
        if db_sid and cdb:
            try:
                cdb.save_message(db_sid, "user", text)
            except Exception:
                pass

        # 共享核心循环
        from core.agent_loop import run_turn as _run_turn

        async def ws_confirm(msg: str) -> bool:
            await ws.send_json({"type": "confirm_needed", "text": msg})
            # 直接读 WebSocket，不依赖外层循环（外层循环被 run_turn 阻塞了）
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=120)
                if data.get("type") == "confirm":
                    return data.get("approved", False)
            except (asyncio.TimeoutError, WebSocketDisconnect, Exception):
                pass
            return False

        try:
            events = await _run_turn(
                conv, backend_client, model_display, _registry,
                dual_model=_dual_available and _ag._glm_client is not None,
                persona_enabled=_persona_enabled,
                confirm_handler=ws_confirm,
            )

            reply_text = ""
            first_text = True
            for evt in events:
                t, txt = evt.get("type", ""), evt.get("text", "")
                if t == "status":
                    print(f"\n  [{txt}]", end="")
                elif t == "tool":
                    print(f"\n  {txt}")
                elif t == "tool_result":
                    if evt.get("ok") is False:
                        print(f"  -> [fail] {evt.get('error', txt)}")
                    else:
                        print(f"  -> {txt}")
                elif t == "confirm_needed":
                    print(f"\n  [confirm] {txt}")
                elif t == "text":
                    if first_text:
                        print()
                        first_text = False
                    reply_text += txt
                    print(txt, end="", flush=True)
                elif t == "done":
                    print()
                elif t == "error":
                    print(f"\n  error: {txt}")
                if t in ("text", "tool", "tool_result", "status", "error", "confirm_needed", "done"):
                    try:
                        await ws.send_json(evt)
                    except Exception:
                        return
        except WebSocketDisconnect:
            return
        except Exception as e:
            print(f"  [ws] error: {e}")
            return

        # 助手回复入库
        if reply_text and db_sid and cdb:
            try:
                cdb.save_message(db_sid, "assistant", reply_text)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    import socket
    import signal as _signal

    # 杀旧进程（PID 文件）
    pid_file = Path(__file__).parent / "memory" / "server.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.kill(old_pid, _signal.SIGTERM)
        except Exception:
            pass
    pid_file.write_text(str(os.getpid()))

    # 自动找空闲端口
    def find_free_port(start=8898):
        for port in range(start, start + 10):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                sock.close()
                return port
            except OSError:
                sock.close()
        return start

    PORT = find_free_port()

    # 退出时清 PID
    import atexit
    atexit.register(lambda: pid_file.unlink(missing_ok=True))

    # 获取本机 LAN IP
    def get_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "???"

    lan_ip = get_lan_ip()

    print(f"agent  {backend} / {model_display}")
    if _dual_available:
        print(f"  dual  Worker: deepseek  |  Persona: glm-4-flash")
    print(f"modules {_registry.list()}")
    print(f"persona {'on' if _persona_enabled else 'off'}")
    print(f"  http://127.0.0.1:{PORT}")
    print(f"  http://{lan_ip}:{PORT}")
    print(f"  Ctrl+C to stop")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
