"""
Admin Panel — 独立管理面板 (端口 8900)
和 agent/server 完全分离，只管 persona.db + song_map.db 的增删改查

用法: python admin_server.py
打开: http://127.0.0.1:8900
"""

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:
    print("pip install fastapi uvicorn")
    sys.exit(1)

from modules.persona.db import PersonaDB
from modules.persona.song_map import SongMapDB

app = FastAPI()


# ============================================================
# API: Profile
# ============================================================
@app.get("/api/profile")
def get_profile():
    return {"content": PersonaDB().get_profile()}

@app.post("/api/profile")
async def set_profile(request: Request):
    data = await request.json()
    PersonaDB().set_profile(data.get("content", ""))
    return {"ok": True}


# ============================================================
# API: Rules
# ============================================================
@app.get("/api/rules")
def get_rules():
    return PersonaDB().get_rules(enabled_only=False)

@app.post("/api/rules")
async def add_rule(request: Request):
    data = await request.json()
    rid = PersonaDB().add_rule(data.get("content",""), data.get("rule_type","behavior"), data.get("priority",5))
    return {"ok": True, "id": rid}

@app.delete("/api/rules/{rule_id}")
def del_rule(rule_id: int):
    PersonaDB().delete_rule(rule_id)
    return {"ok": True}

@app.put("/api/rules/{rule_id}")
async def update_rule(rule_id: int, request: Request):
    data = await request.json()
    kwargs = {}
    if "content" in data: kwargs["content"] = data["content"]
    if "rule_type" in data: kwargs["rule_type"] = data["rule_type"]
    if kwargs:
        PersonaDB().update_rule(rule_id, **kwargs)
    return {"ok": True}


# ============================================================
# API: Memories
# ============================================================
@app.get("/api/memories")
def get_memories():
    return [m for m in PersonaDB().get_all_memories() if m.get("category","general") != "song"]

@app.post("/api/memories")
async def add_memory(request: Request):
    data = await request.json()
    PersonaDB().set_memory(data.get("key",""), data.get("value",""), target=data.get("target","both"))
    return {"ok": True}

@app.put("/api/memories")
async def update_memory(request: Request):
    data = await request.json()
    PersonaDB().set_memory(data.get("key",""), data.get("value",""), target=data.get("target","both"))
    return {"ok": True}

@app.delete("/api/memories/{key:path}")
def del_memory(key: str):
    PersonaDB().delete_memory(key)
    return {"ok": True}


# ============================================================
# API: Song Maps
# ============================================================
@app.get("/api/songs")
def get_songs():
    return SongMapDB().list_all()

@app.post("/api/songs")
async def add_song(request: Request):
    data = await request.json()
    SongMapDB().set(data.get("key",""), data.get("value",""))
    return {"ok": True}

@app.put("/api/songs")
async def update_song(request: Request):
    data = await request.json()
    SongMapDB().set(data.get("key",""), data.get("value",""))
    return {"ok": True}

@app.delete("/api/songs/{key:path}")
def del_song(key: str):
    SongMapDB().delete(key)
    return {"ok": True}


# ============================================================
# HTML
# ============================================================
@app.get("/", response_class=HTMLResponse)
def index():
    return HTML

HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Admin</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font:14px/1.5 -apple-system,Segoe UI,sans-serif;background:#f0f4f8;color:#333;display:flex;height:100vh}
nav{width:180px;background:#1e3a5f;padding:16px 0;color:#fff;flex-shrink:0}
nav h3{padding:8px 20px 20px;font-size:15px;color:#8ab4f8;letter-spacing:1px}
nav a{display:block;padding:10px 20px;color:#a8c8e8;text-decoration:none;cursor:pointer;font-size:13px;border-left:3px solid transparent}
nav a:hover{background:#2a5080;color:#fff}
nav a.on{background:#2a5080;color:#fff;border-left-color:#5af}
main{flex:1;overflow-y:auto;padding:28px 32px}
h2{font-size:18px;color:#1e3a5f;margin-bottom:18px;font-weight:600}
.panel{display:none}
.panel.on{display:block}
.card{background:#fff;border-radius:6px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:16px}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #e8ecf0;font-size:13px}
th{color:#5a7a9a;font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
td{color:#444}
tr:hover{background:#f7fafd}
input,textarea,select{background:#fff;color:#333;border:1px solid #ccd6e0;border-radius:4px;padding:8px 10px;font:inherit;outline:none;width:100%}
input:focus,textarea:focus,select:focus{border-color:#5af;box-shadow:0 0 0 2px rgba(85,170,255,.15)}
button{background:#2d7dd2;color:#fff;border:none;border-radius:4px;padding:8px 18px;cursor:pointer;font:inherit;font-weight:500}
button:hover{background:#1e5faa}
button.danger{background:#fff;color:#d33;border:1px solid #e8ccd0}
button.danger:hover{background:#fef0f0;color:#b22}
button.sm{font-size:12px;padding:4px 10px}
.row{display:flex;gap:10px;margin-bottom:12px;align-items:flex-end}
.row>*{flex:1}
.row button{flex-shrink:0;margin-bottom:0}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;}
.badge.worker{background:#e3f2e8;color:#1e6e3e}
.badge.persona{background:#e8eaf6;color:#3d5afe}
.badge.general{background:#f0f0f0;color:#666}
.msg{color:#4a9;margin-left:10px;font-size:13px}
small{color:#8899aa;font-size:12px}
.muted{color:#99aabb}
</style>
</head>
<body>
<nav>
  <h3>Agent Admin</h3>
  <a class="on" onclick="show('worker')">Worker Rules</a>
  <a onclick="show('persona')">Persona Rules</a>
  <a onclick="show('profile')">Profile</a>
  <a onclick="show('memories')">Memories</a>
  <a onclick="show('songs')">Song Maps</a>
</nav>
<main>

<!-- Worker Rules (constraint) -->
<div id="worker" class="panel on">
  <h2>Worker Rules — DS / Qwen 怎么看</h2>
  <p class="muted">constraint 规则：管工具使用、执行纪律、工作习惯。这些规则注入 Worker 的 system prompt。</p>
  <div class="card">
    <div class="row">
      <input id="wrText" placeholder="新规则内容...">
      <button onclick="addRule('constraint')">Add</button>
    </div>
    <table id="wrTable"><tr><th>#</th><th>Content</th><th></th></tr></table>
  </div>
</div>

<!-- Persona Rules (behavior) -->
<div id="persona" class="panel">
  <h2>Persona Rules — GLM 怎么看</h2>
  <p class="muted">behavior 规则：管语气、风格、人设扮演。这些规则注入 GLM 的 system prompt。</p>
  <div class="card">
    <div class="row">
      <input id="prText" placeholder="新规则内容...">
      <button onclick="addRule('behavior')">Add</button>
    </div>
    <table id="prTable"><tr><th>#</th><th>Content</th><th></th></tr></table>
  </div>
</div>

<!-- Profile -->
<div id="profile" class="panel">
  <h2>Profile — Lain 人设</h2>
  <p class="muted">GLM 看到的身份描述。越详细越像。</p>
  <div class="card">
    <textarea id="profText" rows="6"></textarea>
    <div style="margin-top:10px"><button onclick="saveProfile()">Save</button> <span id="profMsg" class="msg"></span></div>
  </div>
</div>

<!-- Memories -->
<div id="memories" class="panel">
  <h2>Memories — 用户事实</h2>
  <p class="muted">你的名字、设备、偏好。GLM 会记住。</p>
  <div class="card">
    <div class="row">
      <input id="memKey" placeholder="Key（如 user_name）">
      <input id="memVal" placeholder="Value（如 CapoOne）">
      <select id="memTarget"><option value="both">Both</option><option value="worker">Worker</option><option value="persona">Persona</option></select>
      <button onclick="addMemory()">Add</button>
    </div>
    <table id="memTable"><tr><th>Key</th><th>Value</th><th>Target</th><th></th></tr></table>
  </div>
</div>

<!-- Song Maps -->
<div id="songs" class="panel">
  <h2>Song Maps — 歌名映射</h2>
  <p class="muted">你怎么叫 → 网易云上的准确名字或 URL。ncm_play 自动查。</p>
  <div class="card">
    <div class="row">
      <input id="songKey" placeholder="你怎么叫它">
      <input id="songVal" placeholder="网易云正确歌名或 URL">
      <button onclick="addSong()">Add</button>
    </div>
    <table id="songTable"><tr><th>Key</th><th>Value</th><th></th></tr></table>
  </div>
</div>

</main>

<script>
function show(id){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  document.querySelectorAll('nav a').forEach(a=>a.classList.remove('on'));
  event.target.classList.add('on');
}

// === Profile ===
async function loadProfile(){
  const r=await fetch('/api/profile');const d=await r.json();
  document.getElementById('profText').value=d.content||'';
}
async function saveProfile(){
  await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:document.getElementById('profText').value})});
  document.getElementById('profMsg').textContent='Saved';setTimeout(()=>document.getElementById('profMsg').textContent='',1500);
}
loadProfile();

// === Rules ===
function ruleRow(r){
  return `<tr id="rule-${r.id}"><td>#${r.id}</td><td id="rule-cell-${r.id}">${esc(r.content)}</td><td><button class="sm" onclick="editRule(${r.id},'${escAttr(r.content)}','${r.rule_type}')">Edit</button> <button class="danger sm" onclick="delRule(${r.id})">Del</button></td></tr>`;
}
function editRule(id,content,type){
  document.getElementById('rule-cell-'+id).innerHTML=`<input id="rule-edit-${id}" value="${escAttr(content)}" style="width:100%"><div style="margin-top:4px"><button class="sm" onclick="saveRule(${id},'${type}')">Save</button> <button class="sm" onclick="loadRules()">Cancel</button></div>`;
}
async function saveRule(id,type){
  const c=document.getElementById('rule-edit-'+id).value;
  await fetch('/api/rules/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:c})});
  loadRules();
}
async function loadRules(){
  const r=await fetch('/api/rules');const rules=await r.json();
  let wh='<tr><th>#</th><th>Content</th><th></th></tr>',ph=wh;
  rules.forEach(r=>{
    if(r.rule_type==='constraint') wh+=ruleRow(r); else ph+=ruleRow(r);
  });
  document.getElementById('wrTable').innerHTML=wh;
  document.getElementById('prTable').innerHTML=ph;
}
async function addRule(type){
  const el=type==='constraint'?'wrText':'prText';
  const c=document.getElementById(el).value;if(!c)return;
  await fetch('/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rule_type:type,content:c})});
  document.getElementById(el).value='';loadRules();
}
async function delRule(id){await fetch('/api/rules/'+id,{method:'DELETE'});loadRules();}
loadRules();

// === Memories ===
function memRow(m){
  const t=m.target||'both';
  return `<tr id="mem-${escAttr(m.key)}"><td>${esc(m.key)}</td><td id="mem-cell-${escAttr(m.key)}">${esc(m.value)}</td><td id="mem-target-${escAttr(m.key)}"><span class="badge ${t}">${t}</span></td><td><button class="sm" onclick="editMem('${escAttr(m.key)}','${escAttr(m.value)}','${t}')">Edit</button> <button class="danger sm" onclick="delMem('${escAttr(m.key)}')">Del</button></td></tr>`;
}
function editMem(key,value,target){
  document.getElementById('mem-cell-'+escAttr(key)).innerHTML=`<input id="mem-edit-val-${escAttr(key)}" value="${escAttr(value)}" style="width:100%">`;
  document.getElementById('mem-target-'+escAttr(key)).innerHTML=`<select id="mem-edit-target-${escAttr(key)}"><option value="both" ${target=='both'?'selected':''}>Both</option><option value="worker" ${target=='worker'?'selected':''}>Worker</option><option value="persona" ${target=='persona'?'selected':''}>Persona</option></select>`;
  document.getElementById('mem-'+escAttr(key)).querySelector('td:last-child').innerHTML=`<button class="sm" onclick="saveMem('${escAttr(key)}')">Save</button> <button class="sm" onclick="loadMems()">Cancel</button>`;
}
async function saveMem(key){
  const v=document.getElementById('mem-edit-val-'+escAttr(key)).value;
  const t=document.getElementById('mem-edit-target-'+escAttr(key)).value;
  await fetch('/api/memories',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key,value:v,target:t})});
  loadMems();
}
async function loadMems(){
  const r=await fetch('/api/memories');const d=await r.json();
  document.getElementById('memTable').innerHTML='<tr><th>Key</th><th>Value</th><th>Target</th><th></th></tr>'+d.map(m=>memRow(m)).join('');
}
async function addMemory(){
  const k=document.getElementById('memKey').value,v=document.getElementById('memVal').value,t=document.getElementById('memTarget').value;
  if(!k||!v)return;
  await fetch('/api/memories',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,value:v,target:t})});
  document.getElementById('memKey').value='';document.getElementById('memVal').value='';loadMems();
}
async function delMem(k){await fetch('/api/memories/'+encodeURIComponent(k),{method:'DELETE'});loadMems();}
loadMems();

// === Song Maps ===
function songRow(s){
  return `<tr id="song-${escAttr(s.key)}"><td>${esc(s.key)}</td><td id="song-cell-${escAttr(s.key)}">${esc(s.value)}</td><td><button class="sm" onclick="editSong('${escAttr(s.key)}','${escAttr(s.value)}')">Edit</button> <button class="danger sm" onclick="delSong('${escAttr(s.key)}')">Del</button></td></tr>`;
}
function editSong(key,value){
  document.getElementById('song-cell-'+escAttr(key)).innerHTML=`<input id="song-edit-${escAttr(key)}" value="${escAttr(value)}" style="width:100%"><div style="margin-top:4px"><button class="sm" onclick="saveSong('${escAttr(key)}')">Save</button> <button class="sm" onclick="loadSongs()">Cancel</button></div>`;
}
async function saveSong(key){
  const v=document.getElementById('song-edit-'+escAttr(key)).value;
  await fetch('/api/songs',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key,value:v})});
  loadSongs();
}
async function loadSongs(){
  const r=await fetch('/api/songs');const d=await r.json();
  document.getElementById('songTable').innerHTML='<tr><th>Key</th><th>Value</th><th></th></tr>'+d.map(s=>songRow(s)).join('');
}
async function addSong(){
  const k=document.getElementById('songKey').value,v=document.getElementById('songVal').value;
  if(!k||!v)return;
  await fetch('/api/songs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,value:v})});
  document.getElementById('songKey').value='';document.getElementById('songVal').value='';loadSongs();
}
async function delSong(k){await fetch('/api/songs/'+encodeURIComponent(k),{method:'DELETE'});loadSongs();}
loadSongs();

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function escAttr(s){return String(s).replace(/'/g,"\\'").replace(/"/g,'&quot;')}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("Admin Panel → http://127.0.0.1:8900")
    uvicorn.run(app, host="127.0.0.1", port=8900, log_level="warning")
