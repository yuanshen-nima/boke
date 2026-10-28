"""每日对话归纳编排：提取 -> 归纳 -> 写文章 -> git 发布。

用法（在 digest/ 目录下）：
  python run.py                     # 处理今天，调用 LLM，发布
  python run.py --date 2026-09-05   # 补某一天
  python run.py --no-llm            # 不调 API，生成话题清单版（用于测试）
  python run.py --no-push          # 只生成文章，不执行 git 发布
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent
ROOT = DIGEST_DIR.parent
POSTS_DIR = ROOT / "src" / "content" / "posts"
WORK_DIR = DIGEST_DIR / "work"

sys.path.insert(0, str(DIGEST_DIR))
import extract  # noqa: E402
import security  # noqa: E402
import summarize  # noqa: E402


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def fallback_body(material: dict) -> str:
    """无 LLM 时的降级版本：话题清单。"""
    lines = [
        f"今天我和 AI 助手一共进行了 **{len(material['sessions'])} 个会话**。",
        "以下是按会话整理的话题清单（这是未接入摘要模型时的简版日报）：",
        "",
    ]
    for s in material["sessions"]:
        lines.append(f"## {s['title']}")
        lines.append(f"（{s['time']} · {s['source']} · 项目 {s['project']}）")
        lines.append("")
        for t in s["turns"][:8]:
            lines.append(f"- 讨论：{t['q']}")
        lines.append("")
    return "\n".join(lines)


def build_markdown(date_str: str, body: str, n_sessions: int, draft: bool = False) -> str:
    # 摘要行优先取"今日重点"第一条加粗结论，取不到再用默认句式
    m = re.search(r"^\s*[-*]\s*\*\*(.+?)\*\*", body, re.MULTILINE)
    if m:
        desc = re.sub(r"[。！？.]+$", "", m.group(1))[:80]
    else:
        desc = f"{date_str} 与 AI 结对的一天，{n_sessions} 个会话的话题归纳。"
    frontmatter = (
        "---\n"
        f"title: AI 对话日报 · {date_str}\n"
        f"published: {date_str}\n"
        f"description: {desc}\n"
        "tags: [每日摘要, AI 对话]\n"
        "category: 对话摘要\n"
        f"draft: {'true' if draft else 'false'}\n"
        "---\n\n"
    )
    return frontmatter + body.strip() + "\n"


def git_run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


# push 时依次尝试：直连 + 常见本地代理端口（Clash/V2Ray 等）
PUSH_PROXY_CANDIDATES = [
    None,
    "http://127.0.0.1:7897",
    "http://127.0.0.1:7890",
    "http://127.0.0.1:10809",
    "socks5h://127.0.0.1:7897",
]


def push_with_fallback() -> bool:
    last_err = ""
    for attempt in (1, 2):
        for proxy in PUSH_PROXY_CANDIDATES:
            args = ["push"]
            label = "直连"
            if proxy:
                args = ["-c", f"http.proxy={proxy}", "push"]
                label = f"代理 {proxy}"
            push = git_run(*args)
            if push.returncode == 0:
                log(f"git push 成功（{label}），Cloudflare 将自动构建发布")
                return True
            last_err = push.stderr.strip()[:200]
        if attempt == 1:
            log(f"git push 全部失败（{last_err}），30 秒后重试一轮")
            time.sleep(30)
    log(f"git push 最终失败：{last_err}")
    log("文章已在本地提交；之后任何一次成功运行都会自动补推")
    return False


def publish(post_rel: str, date_str: str) -> bool:
    r = git_run("status", "--porcelain", post_rel)
    if not r.stdout.strip():
        log("文章内容与已发布版本一致，无需提交")
        return True
    pull = git_run("pull", "--rebase", "--autostash")
    if pull.returncode != 0:
        log(f"git pull 失败（继续本地提交）：{pull.stderr.strip()[:200]}")
    git_run("add", post_rel)
    commit = git_run("commit", "-m", f"daily digest {date_str}")
    if commit.returncode != 0:
        log(f"git commit 失败：{commit.stderr.strip()[:200]}")
        return False
    return push_with_fallback()


def main() -> int:
    ap = argparse.ArgumentParser(description="每日对话归纳")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--no-llm", action="store_true", help="不调 API，生成话题清单版")
    ap.add_argument("--no-push", action="store_true", help="只生成文章，不 git 发布")
    ap.add_argument("--force", action="store_true", help="跳过安全拦截，强制发布（人工确认后使用）")
    args = ap.parse_args()

    date_str = args.date
    WORK_DIR.mkdir(exist_ok=True)
    log(f"===== 每日对话归纳 {date_str} =====")

    # 补推：之前某天 push 失败遗留的本地提交，借这次联网机会先推出去
    ahead = git_run("rev-list", "@{u}..HEAD")
    if ahead.returncode == 0 and ahead.stdout.strip():
        n = len(ahead.stdout.splitlines())
        log(f"检测到 {n} 个未推送的本地提交，先尝试补推")
        push_with_fallback()

    material_path = WORK_DIR / f"material-{date_str}.json"
    material = extract.build_material(date_str)
    # 源记录可能已被 Codex/ZCode 清理：留存的素材快照若更全，则优先用快照
    saved = None
    if material_path.exists():
        try:
            saved = json.loads(material_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            saved = None
    fresh_n = len(material["sessions"])
    saved_n = len(saved.get("sessions", [])) if isinstance(saved, dict) else 0
    if saved_n > fresh_n:
        log(f"源记录仅提取到 {fresh_n} 个会话，改用更全的留存快照（{saved_n} 个）")
        material = saved
        n_sessions = saved_n
    else:
        n_sessions = fresh_n
        material_path.write_text(
            json.dumps(material, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    # 项目黑名单过滤（config.json security.blocked_projects）：整个项目的会话不进入素材
    sec_cfg = security.load_security_config()
    material["sessions"], dropped = security.filter_sessions(material["sessions"], sec_cfg)
    n_sessions = len(material["sessions"])
    for d in dropped:
        log(f"安全过滤：已跳过 {d}")
    if n_sessions == 0:
        log("当天没有对话记录，跳过生成与发布")
        return 0
    log(f"素材就绪：{n_sessions} 个会话 -> {material_path.name}")

    if args.no_llm:
        body = fallback_body(material)
        log("使用 --no-llm 话题清单模式")
        draft = True  # 清单模式含原始提问，默认只存草稿
    else:
        try:
            cfg = summarize.load_config()
            body = summarize.summarize(material, cfg)
            log(f"LLM 归纳完成（{cfg['model']}，正文 {len(body)} 字符）")
            draft = False
        except Exception as err:
            log(f"归纳失败：{err}")
            log("素材已保留，可修复配置后重跑；当天未发布")
            return 1

    # ===== 安全关卡 1：确定性扫描（密钥/路径/内网信息），LLM 提示词不能替代 =====
    findings = security.scan(body, extra_keywords=sec_cfg.get("sensitive_keywords", []))
    if findings and not args.force:
        for f in findings:
            log(f"安全拦截[{f['kind']}] {f['name']}：{f['sample']}")
        draft = True
        log("命中敏感内容，本文按草稿保存，不发布。人工确认安全后："
            "改 frontmatter draft 或用 --force 重新生成")

    # ===== 安全关卡 2：LLM 复审（私有研究内容等语义级风险） =====
    if not draft and not args.no_llm:
        try:
            review = summarize.safety_review(body, cfg)
            if not review["safe"] and not args.force:
                for r in review["reasons"]:
                    log(f"复审拦截：{r}")
                draft = True
                log("安全复审未通过，本文按草稿保存，不发布")
            else:
                log("安全复审通过")
        except Exception as err:
            log(f"安全复审异常：{err}，按不安全处理")
            draft = True

    post_path = POSTS_DIR / f"daily-{date_str}.md"
    post_path.write_text(
        build_markdown(date_str, body, n_sessions, draft=draft), encoding="utf-8"
    )
    log(f"文章已写入 {post_path}" + ("（草稿，未发布）" if draft else ""))

    if draft and not args.no_push:
        log("草稿模式：跳过 git 发布，仅本地保存")
        return 0
    if args.no_push:
        log("--no-push：跳过 git 发布")
        return 0
    ok = publish(f"src/content/posts/{post_path.name}", date_str)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
