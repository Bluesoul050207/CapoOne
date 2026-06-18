"""
ncm_helper — 网易云搜索+播放一步完成
Agent 调这个，不用自己解析 JSON
"""

import subprocess, json, sys


def search_and_play(query: str) -> str:
    r = subprocess.run(
        f'ncm-cli search song --keyword "{query}" --output json',
        shell=True, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return f"search failed: {r.stderr[:200] if r.stderr else 'no output'}"

    try:
        d = json.loads(r.stdout)
        records = d.get("data", {}).get("records", [])
        if not records:
            return f"no results for: {query}"
        song = records[0]
        name = song.get("name", "?")
        artist = song.get("artists", [{}])[0].get("name", "?")
        oid = song.get("originalId", "")

        subprocess.run(
            f'cmd /c start "" "https://music.163.com/song?id={oid}"',
            shell=True, timeout=10,
        )
        return f"opened: {name} - {artist} (id={oid})"
    except Exception as e:
        return f"parse error: {e}"


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "瘦子"
    print(search_and_play(query))
