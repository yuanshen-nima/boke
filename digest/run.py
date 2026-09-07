"""每日对话归纳编排：提取 -> 归纳 -> 写文章 -> git 发布。

用法（在 digest/ 目录下）：
  python run.py                     # 处理今天，调用 LLM，发布
  python run.py --date 2026-09-05   # 补某一天
  python run.py --no-llm            # 不调 API，生成话题清单版（用于测试）
  python run.py --no-push          # 只生成文章，不执行 git 发布
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent
ROOT = DIGEST_DIR.parent
POSTS_DIR = ROOT / "src" / "content" / "posts"
WORK_DIR = DIGEST_DIR / "work"

sys.path.insert(0, str(DIGEST_DIR))
import extract  # noqa: E402
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


def build_markdown(date_str: str, body: str, n_sessions: int) -> str:
    frontmatter = (
        "---\n"
        f"title: AI 对话日报 · {date_str}\n"
        f"published: {date_str}\n"
        f"description: {date_str} 与 AI 结对的一天，{n_sessions} 个会话的话题归纳。\n"
        "tags: [每日摘要, AI 对话]\n"
        "category: 对话摘要\n"
        "draft: false\n"
        "---\n\n"
    )
    return frontmatter + body.strip() + "\n"


def git_run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


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
    push = git_run("push")
    if push.returncode != 0:
        log(f"git push 失败：{push.stderr.strip()[:300]}")
        log("文章已在本地提交，网络恢复后可手动 git push")
        return False
    log("git push 完成，Cloudflare 将自动构建发布")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="每日对话归纳")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--no-llm", action="store_true", help="不调 API，生成话题清单版")
    ap.add_argument("--no-push", action="store_true", help="只生成文章，不 git 发布")
    args = ap.parse_args()

    date_str = args.date
    WORK_DIR.mkdir(exist_ok=True)
    log(f"===== 每日对话归纳 {date_str} =====")

    material = extract.build_material(date_str)
    n_sessions = len(material["sessions"])
    if n_sessions == 0:
        log("当天没有对话记录，跳过生成与发布")
        return 0
    material_path = WORK_DIR / f"material-{date_str}.json"
    material_path.write_text(
        json.dumps(material, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    log(f"素材提取完成：{n_sessions} 个会话 -> {material_path.name}")

    if args.no_llm:
        body = fallback_body(material)
        log("使用 --no-llm 话题清单模式")
    else:
        try:
            cfg = summarize.load_config()
            body = summarize.summarize(material, cfg)
            log(f"LLM 归纳完成（{cfg['model']}，正文 {len(body)} 字符）")
        except Exception as err:
            log(f"归纳失败：{err}")
            log("素材已保留，可修复配置后重跑；当天未发布")
            return 1

    post_path = POSTS_DIR / f"daily-{date_str}.md"
    post_path.write_text(
        build_markdown(date_str, body, n_sessions), encoding="utf-8"
    )
    log(f"文章已写入 {post_path}")

    if args.no_push:
        log("--no-push：跳过 git 发布")
        return 0
    ok = publish(f"src/content/posts/{post_path.name}", date_str)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
