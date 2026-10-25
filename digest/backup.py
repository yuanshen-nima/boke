"""每日备份：把 Waline 评论数据（Neon PostgreSQL）导出到本地 JSON。

- 数据源连接串在 config.json 的 waline_db 字段（该文件已 gitignore，密钥不进仓库）
- 输出 digest/work/backup/waline-YYYY-MM-DD.json
- 自动保留最近 KEEP 份，超出的删除
- 由 run_daily.bat 每日调用，与日报生成解耦（无对话也照常备份）
"""

import json
import re
from datetime import datetime
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent
BACKUP_DIR = DIGEST_DIR / "work" / "backup"
KEEP = 30
TABLES = ["wl_comment", "wl_users", "wl_counter"]


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_db_url() -> str:
    cfg_path = DIGEST_DIR / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    dsn = cfg.get("waline_db") or ""
    if not dsn:
        raise RuntimeError("config.json 缺少 waline_db（Neon 连接串）")
    return dsn


def dump(dsn: str) -> Path:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(dsn, sslmode="require")
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            data = {}
            for table in TABLES:
                cur.execute(f"SELECT * FROM {table}")
                data[table] = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return data


def prune() -> None:
    files = sorted(BACKUP_DIR.glob("waline-*.json"))
    for old in files[:-KEEP]:
        old.unlink()
        log(f"清理过期备份 {old.name}")


def main() -> int:
    date = datetime.now().strftime("%Y-%m-%d")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = dump(load_db_url())
    except Exception as err:
        log(f"备份失败：{err}")
        return 1
    out = BACKUP_DIR / f"waline-{date}.json"
    out.write_text(
        json.dumps({"date": date, "tables": data}, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8",
    )
    log(f"备份完成：{out.name}（评论 {len(data.get('wl_comment', []))} 条）")
    prune()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
