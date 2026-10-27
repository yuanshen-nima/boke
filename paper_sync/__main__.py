"""paper_sync 命令行入口。

用法：
  python -m paper_sync import-export PATH   # 导入 ChatGPT 官方导出（zip / json / 分卷）
  python -m paper_sync import-note PATH     # 导入单篇结构化笔记（json / md，可传目录批量）
  python -m paper_sync sync --dry-run       # 只分析 inbox 不写入
  python -m paper_sync sync --offline       # 处理 inbox（禁用 AI，确定性提取）
  python -m paper_sync list --status draft  # 列出论文
  python -m paper_sync show PAPER_ID        # 查看论文状态
  python -m paper_sync approve PAPER_ID     # 人工审核通过（发布前置条件）
  python -m paper_sync publish PAPER_ID     # 安全扫描后导出到公开仓库并推送
  python -m paper_sync test                 # 运行离线测试套件
"""

import argparse
import sys
from pathlib import Path

from . import config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="paper_sync", description="论文知识库同步引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import-export", help="导入 ChatGPT 官方数据导出")
    p.add_argument("path")
    p.add_argument("--offline", action="store_true", help="禁用 AI，仅确定性提取")

    p = sub.add_parser("import-note", help="导入结构化笔记（文件或目录）")
    p.add_argument("path")
    p.add_argument("--offline", action="store_true")

    p = sub.add_parser("sync", help="处理 inbox 中所有待导入文件")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--offline", action="store_true")

    p = sub.add_parser("list", help="列出论文")
    p.add_argument("--status", choices=["needs_review", "draft", "approved", "published"])

    p = sub.add_parser("show", help="查看论文状态")
    p.add_argument("paper_id")

    p = sub.add_parser("approve", help="人工审核通过")
    p.add_argument("paper_id")

    p = sub.add_parser("publish", help="发布到公开仓库")
    p.add_argument("paper_id")
    p.add_argument("--force", action="store_true", help="安全扫描命中仍强制发布")
    p.add_argument("--no-push", action="store_true", help="只写入仓库不推送")

    p = sub.add_parser("serve", help="启动本地 HTTP 接收服务（供油猴脚本直接同步）")
    p.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765）")
    p.add_argument("--no-auto-sync", action="store_true", help="写入 inbox 后不自动触发同步")

    sub.add_parser("test", help="运行离线测试套件")

    args = ap.parse_args(argv)
    log = config.get_logger()

    if args.cmd == "test":
        import unittest

        from .tests.runner import run_tests

        return run_tests()

    if args.cmd == "list":
        from .state import StateDB

        db = StateDB(config.STATE_DB)
        rows = db.list_papers(args.status)
        if not rows:
            print("(无)")
        for r in rows:
            print(f"{r['paper_id']:44} [{r['status']:12}] {r['title'][:50]}")
        db.close()
        return 0

    if args.cmd == "show":
        from .state import StateDB

        db = StateDB(config.STATE_DB)
        paper = db.get_paper(args.paper_id)
        if not paper:
            print(f"论文不存在：{args.paper_id}")
            return 1
        print(dict(paper))
        for s in db.list_sources_by_paper(args.paper_id):
            print("  来源:", dict(s))
        db.close()
        return 0

    from .pipeline import PaperSync

    if args.cmd in ("import-export", "import-note"):
        src = Path(args.path)
        if not src.exists():
            log.error(f"路径不存在：{src}")
            return 1
        targets = [src] if src.is_file() else sorted(
            p for p in src.iterdir() if p.is_file() and not p.name.startswith(".")
        )
        config.ensure_dirs()
        exit_code = 0
        # 注意：不要在这里再套一层 SyncLock —— ps.sync() 内部已加锁，
        # 同进程重复加锁会自我阻塞并误报「另一个同步进程正在运行」。
        ps = PaperSync(offline=args.offline, log=log)
        try:
            for t in targets:
                dest = config.INBOX_DIR / t.name
                dest.write_bytes(t.read_bytes())
                log.info(f"已放入 inbox：{t.name}")
                exit_code = max(exit_code, ps.sync())
        finally:
            ps.close()
        return exit_code

    if args.cmd == "sync":
        ps = PaperSync(offline=args.offline, log=log)
        try:
            return ps.sync(dry_run=args.dry_run)
        finally:
            ps.close()

    if args.cmd == "approve":
        ps = PaperSync(log=log)
        try:
            return ps.approve(args.paper_id)
        finally:
            ps.close()

    if args.cmd == "publish":
        ps = PaperSync(log=log)
        try:
            return ps.publish(args.paper_id, force=args.force, no_push=args.no_push)
        finally:
            ps.close()

    if args.cmd == "serve":
        from .server import run_server

        run_server(host=args.host, port=args.port, auto_sync=not args.no_auto_sync)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
