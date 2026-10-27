"""每日自动提交与推送脚本：检查仓库变更 -> 安全扫描 -> git commit -> git push。

用于 Windows 任务计划程序（每日 21:00）或手动调用。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 仓库根目录与日志目录
REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_FILE = LOG_DIR / "auto_git_sync.log"

# 敏感信息扫描正则（防止误提交密钥）
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}", re.IGNORECASE),
    re.compile(r"github_pat_[a-zA-Z0-9_]{30,}", re.IGNORECASE),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}", re.IGNORECASE),
    re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]+@[^/\s]+/\S+", re.IGNORECASE),
]


def log(msg: str) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now_str}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"写入日志失败: {e}", file=sys.stderr)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def scan_for_secrets() -> list[str]:
    """检查即将暂存的文件中是否含有敏感词。"""
    st = git("status", "--porcelain")
    findings = []
    for line in st.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path_str = line[3:].strip().strip('"')
        if "D" in status:
            continue
        p = REPO_ROOT / path_str
        # 排除单元测试文件（测试用例中包含 mock 敏感词）
        if "test" in path_str.lower() and (path_str.startswith("paper_sync/tests") or path_str.startswith("tests")):
            continue
        if not p.is_file() or p.stat().st_size > 1024 * 1024:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for pat in SECRET_PATTERNS:
                m = pat.search(content)
                if m:
                    findings.append(f"文件 {path_str} 疑似包含敏感信息（{m.group(0)[:8]}***）")
        except Exception:
            pass
    return findings


def sync_and_push() -> int:
    log("=== 开始执行每日自动提交与推送 ===")
    
    # 1. 检查工作区状态
    st = git("status", "--porcelain")
    uncommitted = bool(st.stdout.strip())
    
    # 2. 检查是否有未推送的本地提交
    ahead = git("rev-list", "@{u}..HEAD")
    unpushed = bool(ahead.stdout.strip()) if ahead.returncode == 0 else False

    if not uncommitted and not unpushed:
        log("工作区无任何未提交更改，且无未推送提交，无需操作。")
        log("=== 结束 ===")
        return 0

    # 3. 安全扫描
    if uncommitted:
        findings = scan_for_secrets()
        if findings:
            for f in findings:
                log(f"[安全拦截] {f}")
            log("为保护账号安全，自动提交已终止！请人工检查并移除敏感信息。")
            return 1

    # 4. 远端变动拉取（rebase）
    log("正在从远端拉取最新变动...")
    pull = git("pull", "--rebase", "--autostash")
    if pull.returncode != 0:
        log(f"git pull 提示/告警: {pull.stderr.strip()[:300]}")

    # 5. 暂存并提交
    if uncommitted:
        log("发现未提交更改，正在暂存...")
        git("add", "-A")
        now_desc = datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_msg = f"chore(auto): 自动同步与知识库更新 ({now_desc})"
        commit = git("commit", "-m", commit_msg)
        if commit.returncode != 0:
            log(f"git commit 失败: {commit.stderr.strip()}")
            return 1
        log(f"git commit 成功: {commit_msg}")

    # 6. 推送到远端（带重试机制）
    log("正在推送到 GitHub (origin main)...")
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        push = git("push", "origin", "main")
        if push.returncode == 0:
            log(f"git push 成功！（第 {attempt} 次尝试）")
            log("=== 全部同步完成 ===")
            return 0
        err = push.stderr.strip()
        log(f"git push 失败（第 {attempt}/{max_retries} 次）：{err[:200]}")
        if attempt < max_retries:
            delay = attempt * 10
            log(f"等待 {delay} 秒后重试...")
            time.sleep(delay)

    log("git push 最终失败，请检查网络连接或 GitHub 访问状态。")
    return 1


if __name__ == "__main__":
    code = sync_and_push()
    sys.exit(code)
