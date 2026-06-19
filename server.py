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
    Conversation, ModelPool,
    _init_registry, _get_worker_prompt,
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
pool = ModelPool()

app = FastAPI()

# 按会话 ID 存储对话实例
sessions: dict[str, Conversation] = {}


def get_or_create_conv(session_id: str) -> Conversation:
    if session_id not in sessions:
        sessions[session_id] = Conversation(_get_worker_prompt())
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
            encoding="utf-8", errors="replace", timeout=30, cwd=cwd,
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
    from fastapi.responses import FileResponse
    return FileResponse(
        "templates/index.html", media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                 "Pragma": "no-cache", "Expires": "0"}
    )


# ---- 自清理：杀掉老端口上的残留进程 ----
def _free_port(port: int):
    """杀掉占用指定端口的进程"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr "LISTENING.*:{port}"',
            shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5,
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
            sessions.pop(session_id, None)
            _ws_db_sessions.pop(session_id, None)
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
            # 智能路由：根据用户输入选择 Worker 模型
            client, model = pool.route(text)
            fallback = pool.get_fallback(model)
            events = await _run_turn(
                conv, client, model, _registry,
                dual_model=_dual_available and _ag._glm_client is not None,
                persona_enabled=_persona_enabled,
                confirm_handler=ws_confirm,
                fallback_client=fallback[0] if fallback else None,
                fallback_model=fallback[1] if fallback else "",
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

        # 助手回复入库（含 tool_calls 元数据）
        if reply_text and db_sid and cdb:
            try:
                meta = {}
                for m in reversed(conv.messages):
                    if m["role"] == "assistant" and m.get("tool_calls"):
                        meta["tool_calls"] = m["tool_calls"]
                        break
                cdb.save_message(db_sid, "assistant", reply_text, meta if meta else None)
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

    print(pool.status())
    if _dual_available:
        print(f"  dual  Persona: glm-4-flash")
    print(f"modules {_registry.list()}")
    print(f"persona {'on' if _persona_enabled else 'off'}")
    print(f"  http://127.0.0.1:{PORT}")
    print(f"  http://{lan_ip}:{PORT}")
    print(f"  Ctrl+C to stop")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
