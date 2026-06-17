"""
Persona Editor — AI 人格设定编辑器

管理两类内容:
  1. Rules (约束):   行为规则，如 "禁止 emoji"、"回复简短"
  2. Memories (记忆): 长期信息，如 "用户用机械革命笔记本"、"项目在 D:\agent"

用法:
  python modules/persona/editor.py show
  python modules/persona/editor.py add-rule "xxx"
  python modules/persona/editor.py toggle 3
"""

import sys
import os

# 确保能找到项目根目录的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.persona.db import PersonaDB


def show_all(db: PersonaDB):
    rules = db.get_rules(enabled_only=False)
    memories = db.get_all_memories()

    print("\n=== Profile (角色设定) ===")
    p = db.get_profile()
    print(f"  {p}" if p else "  (none)")

    print("\n=== Rules (行为约束) ===")
    if not rules:
        print("  (none)")
    for r in rules:
        status = " ON" if r["enabled"] else "OFF"
        print(f"  [{r['id']}] {status}  {r['rule_type']:12s}  pri={r['priority']}")
        print(f"       {r['content']}")

    print("\n=== Memories (长期记忆) ===")
    if not memories:
        print("  (none)")
    for m in memories:
        print(f"  [{m['key']}] ({m['category']})")
        print(f"       {m['value']}")

    print(f"\n=== System Prompt Preview ===\n{db.build_prompt_suffix()}\n")


def interactive(db: PersonaDB):
    print("Persona Editor — 输入 help 查看命令")
    while True:
        try:
            cmd = input("\npersona> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue
        parts = cmd.split(maxsplit=2)

        if parts[0] == "help":
            print("""
  profile <内容>  设置角色设定（你是谁）
  profile         查看当前设定
  show            显示全部
  rules           列出规则
  add <内容>       添加约束规则
  add-behavior <内容>  添加行为规则
  edit <id> <内容>     编辑规则
  toggle <id>    开关规则
  delete <id>    删除规则
  mem            列出记忆
  set <key> <value>     设置记忆
  del <key>      删除记忆
  preview        预览 system prompt
  exit           退出
            """)
        elif parts[0] == "show":
            show_all(db)
        elif parts[0] == "profile" and len(parts) > 1:
            db.set_profile(parts[1])
            print(f"  profile set: {parts[1]}")
        elif parts[0] == "profile":
            p = db.get_profile()
            print(f"  profile: {p}" if p else "  (no profile set)")
        elif parts[0] == "rules":
            for r in db.get_rules(enabled_only=False):
                s = "+" if r["enabled"] else "-"
                print(f"  [{s}] {r['id']} ({r['rule_type']}) {r['content'][:80]}")
        elif parts[0] == "add" and len(parts) > 1:
            rid = db.add_rule(parts[1], "constraint", 5)
            print(f"  added rule #{rid}")
        elif parts[0] == "add-behavior" and len(parts) > 1:
            rid = db.add_rule(parts[1], "behavior", 3)
            print(f"  added rule #{rid}")
        elif parts[0] == "edit" and len(parts) > 2:
            db.update_rule(int(parts[1]), content=parts[2])
            print(f"  updated rule #{parts[1]}")
        elif parts[0] == "toggle" and len(parts) > 1:
            rules = db.get_rules(enabled_only=False)
            rid = int(parts[1])
            target = [r for r in rules if r["id"] == rid]
            if target:
                new_state = not target[0]["enabled"]
                db.update_rule(rid, enabled=1 if new_state else 0)
                print(f"  rule #{rid} {'enabled' if new_state else 'disabled'}")
        elif parts[0] == "delete" and len(parts) > 1:
            db.delete_rule(int(parts[1]))
            print(f"  deleted rule #{parts[1]}")
        elif parts[0] == "mem":
            for m in db.get_all_memories():
                print(f"  {m['key']} = {m['value']}")
        elif parts[0] == "set" and len(parts) > 2:
            db.set_memory(parts[1], parts[2])
            print(f"  set {parts[1]}")
        elif parts[0] == "del" and len(parts) > 1:
            db.delete_memory(parts[1])
            print(f"  deleted {parts[1]}")
        elif parts[0] == "preview":
            print(db.build_prompt_suffix())
        elif parts[0] == "exit":
            break
        else:
            print(f"  unknown: {cmd}")


if __name__ == "__main__":
    db = PersonaDB()

    if len(sys.argv) > 1:
        # 命令行模式
        cmd = sys.argv[1]
        if cmd == "show":
            show_all(db)
        elif cmd == "profile":
            p = db.get_profile()
            print(p if p else "(no profile set)")
        elif cmd == "set-profile" and len(sys.argv) > 2:
            db.set_profile(sys.argv[2])
            print(f"profile set: {sys.argv[2]}")
        elif cmd == "rules":
            for r in db.get_rules(enabled_only=False):
                s = "+" if r["enabled"] else "-"
                print(f"[{s}] {r['id']} ({r['rule_type']}) {r['content'][:80]}")
        elif cmd == "add-rule" and len(sys.argv) > 2:
            rid = db.add_rule(sys.argv[2], "constraint", 5)
            print(f"added rule #{rid}")
        elif cmd == "edit-rule" and len(sys.argv) > 3:
            db.update_rule(int(sys.argv[2]), content=sys.argv[3])
            print(f"updated rule #{sys.argv[2]}")
        elif cmd == "toggle" and len(sys.argv) > 2:
            rules = db.get_rules(enabled_only=False)
            target = [r for r in rules if r["id"] == int(sys.argv[2])]
            if target:
                new_state = not target[0]["enabled"]
                db.update_rule(int(sys.argv[2]), enabled=1 if new_state else 0)
        elif cmd == "delete-rule" and len(sys.argv) > 2:
            db.delete_rule(int(sys.argv[2]))
            print(f"deleted rule #{sys.argv[2]}")
        elif cmd == "mem":
            for m in db.get_all_memories():
                print(f"{m['key']} = {m['value']}")
        elif cmd == "set-mem" and len(sys.argv) > 3:
            db.set_memory(sys.argv[2], sys.argv[3])
            print(f"set {sys.argv[2]}")
        elif cmd == "del-mem" and len(sys.argv) > 2:
            db.delete_memory(sys.argv[2])
            print(f"deleted {sys.argv[2]}")
        elif cmd == "preview":
            print(db.build_prompt_suffix())
        else:
            print(f"unknown command: {cmd}")
            print("try: show rules mem preview add-rule set-mem")
    else:
        interactive(db)
