"""SQLite 同步状态库。所有表操作幂等，失败记录允许重试。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
  paper_id TEXT PRIMARY KEY,          -- doi:... | arxiv:... | title:<hash>
  title TEXT DEFAULT '',
  year INTEGER,
  venue TEXT DEFAULT '',
  status TEXT DEFAULT 'draft',        -- needs_review | draft | approved | published
  created_at TEXT,
  updated_at TEXT,
  published_hash TEXT DEFAULT '',
  published_slug TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,         -- 文件 sha256（+ 会话 key）
  source_type TEXT,                   -- chatgpt_export | note_json | note_md
  paper_id TEXT DEFAULT '',
  source_path TEXT,
  source_hash TEXT,
  conversation_key TEXT DEFAULT '',
  imported_at TEXT,
  last_processed_at TEXT,
  normalized_hash TEXT DEFAULT '',
  status TEXT DEFAULT 'pending',      -- pending | imported | needs_review | error
  error_message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, level TEXT, message TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateDB:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(db_path))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    def log_event(self, level: str, message: str) -> None:
        self.con.execute(
            "INSERT INTO events (ts, level, message) VALUES (?, ?, ?)", (now(), level, message)
        )
        self.con.commit()

    # ---- sources ----
    def get_source(self, source_id: str) -> sqlite3.Row | None:
        row = self.con.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        return row

    def upsert_source(
        self,
        source_id: str,
        *,
        source_type: str,
        paper_id: str,
        source_path: str,
        source_hash: str,
        conversation_key: str = "",
        normalized_hash: str = "",
        status: str,
        error_message: str = "",
    ) -> None:
        self.con.execute(
            """INSERT INTO sources (source_id, source_type, paper_id, source_path, source_hash,
                 conversation_key, imported_at, last_processed_at, normalized_hash, status, error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_id) DO UPDATE SET
                 paper_id=excluded.paper_id, source_path=excluded.source_path,
                 source_hash=excluded.source_hash, last_processed_at=excluded.last_processed_at,
                 normalized_hash=excluded.normalized_hash, status=excluded.status,
                 error_message=excluded.error_message""",
            (
                source_id, source_type, paper_id, source_path, source_hash, conversation_key,
                now(), now(), normalized_hash, status, error_message,
            ),
        )
        self.con.commit()

    def list_sources_by_paper(self, paper_id: str) -> list[sqlite3.Row]:
        return self.con.execute(
            "SELECT * FROM sources WHERE paper_id=? ORDER BY imported_at", (paper_id,)
        ).fetchall()

    # ---- papers ----
    def get_paper(self, paper_id: str) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM papers WHERE paper_id=?", (paper_id,)).fetchone()

    def upsert_paper(
        self,
        paper_id: str,
        *,
        title: str = "",
        year: int | None = None,
        venue: str = "",
        status: str | None = None,
        published_hash: str | None = None,
        published_slug: str | None = None,
    ) -> None:
        cur = self.get_paper(paper_id)
        if cur is None:
            self.con.execute(
                """INSERT INTO papers (paper_id, title, year, venue, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (paper_id, title, year, venue, status or "draft", now(), now()),
            )
        else:
            self.con.execute(
                """UPDATE papers SET
                     title=CASE WHEN ?<>'' THEN ? ELSE title END,
                     year=COALESCE(?, year),
                     venue=CASE WHEN ?<>'' THEN ? ELSE venue END,
                     status=COALESCE(?, status),
                     published_hash=COALESCE(?, published_hash),
                     published_slug=COALESCE(?, published_slug),
                     updated_at=?
                   WHERE paper_id=?""",
                (
                    title, title, year, venue, venue, status, published_hash, published_slug,
                    now(), paper_id,
                ),
            )
        self.con.commit()

    def list_papers(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return self.con.execute(
                "SELECT * FROM papers WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        return self.con.execute("SELECT * FROM papers ORDER BY updated_at DESC").fetchall()
