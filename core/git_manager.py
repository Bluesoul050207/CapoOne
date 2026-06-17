"""
GitManager — 会话级自动版本控制
- 启动时建分支
- write_file 后自动 commit
- /git log 查看记录
- /git undo 回退
"""

import subprocess
import os
from datetime import datetime
from pathlib import Path


class GitManager:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.session_branch = None
        self._ensure_repo()

    def _run(self, *args) -> tuple[int, str, str]:
        """跑 git 命令，返回 (returncode, stdout, stderr)"""
        try:
            r = subprocess.run(
                ["git"] + list(args),
                cwd=str(self.repo_path),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    def _ensure_repo(self):
        """确保目录是 git 仓库，不是就 init"""
        rc, _, _ = self._run("rev-parse", "--git-dir")
        if rc != 0:
            self._run("init")
            self._run("add", ".")
            self._run("commit", "-m", "init: agent project")
            # 设置 git 用户（首次需要）
            self._run("config", "user.name", "Lain Agent")
            self._run("config", "user.email", "lain@agent.local")

    # ---- 会话 ----

    def start_session(self):
        """开始新会话，建分支"""
        ts = datetime.now().strftime("%Y%m%d-%H%M")
        branch = f"session-{ts}"
        rc, _, err = self._run("checkout", "-b", branch)
        if rc == 0:
            self.session_branch = branch
            return branch
        # 分支已存在，切过去
        self._run("checkout", branch)
        self.session_branch = branch
        return branch

    def end_session(self):
        """结束会话，切回主分支"""
        if self.session_branch:
            self._run("checkout", "master")
            self.session_branch = None

    # ---- 自动 commit ----

    def commit_change(self, tool_name: str, details: str = ""):
        """工具执行后自动 commit"""
        msg = f"Lain: {tool_name}"
        if details:
            msg += f" — {details[:80]}"
        self._run("add", ".")
        self._run("commit", "-m", msg, "--allow-empty")

    # ---- 查询 ----

    def log(self, n: int = 10) -> str:
        """最近 n 条 commit"""
        rc, out, _ = self._run("log", f"-{n}", "--oneline", "--decorate")
        return out if out else "(no commits)"

    def current_branch(self) -> str:
        rc, out, _ = self._run("branch", "--show-current")
        return out if out else "?"

    # ---- 回退 ----

    def undo(self, n: int = 1):
        """回退最近 n 个 commit（保留文件改动）"""
        self._run("reset", f"HEAD~{n}")
        return self.log(5)

    def undo_hard(self, n: int = 1):
        """回退最近 n 个 commit（丢弃文件改动）"""
        self._run("reset", "--hard", f"HEAD~{n}")
        return self.log(5)


# 全局单例
_git: GitManager | None = None


def get_git(repo_path: str = ".") -> GitManager | None:
    global _git
    if _git is None:
        try:
            _git = GitManager(repo_path)
            _git.start_session()
        except Exception:
            return None
    return _git
