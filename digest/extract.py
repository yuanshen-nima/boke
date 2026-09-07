"""提取指定日期的 ZCode 与 Codex 对话素材，供 summarize.py 归纳。

数据源：
- ZCode:  ~/.zcode/cli/db/db.sqlite （SQLite，只读方式打开）
- Codex:  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl

输出素材结构（build_material 返回值）：
{
  "date": "YYYY-MM-DD",
  "sessions": [
    {"source": "zcode|codex", "title": str, "project": str, "time": "HH:MM",
     "turns": [{"q": 用户提问, "a": [助手回复, ...]}]}
  ]
}
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

HOME = Path.home()
ZCODE_DB = HOME / ".zcode" / "cli" / "db" / "db.sqlite"
CODEX_SESSIONS = HOME / ".codex" / "sessions"

# 素材体积控制
MAX_MSG_CHARS = 800  # 单条消息截断
MAX_MSGS_PER_SESSION = 40  # 每会话最多保留的消息条数
MAX_SESSION_CHARS = 16000  # 单会话素材字符上限

# 密钥样式字符串，发送给大模型前先脱敏
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(
        r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*[\"']?[A-Za-z0-9._/-]{12,}"
    ),
]

# Codex 会把系统上下文以 user 消息注入，以下特征用于排除
CODEX_INJECTED_PREFIXES = ("<", "The following is", "NOTE:", "You are ", "You're ")


def scrub(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub("[已脱敏]", text)
    return text


def truncate(text: str, limit: int = MAX_MSG_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit] + "…(截断)"
    return text


def _cap_turns(turns: list) -> list:
    """限制会话素材的条数与总长度。"""
    total = 0
    capped = []
    for turn in turns:
        if len(capped) >= MAX_MSGS_PER_SESSION:
            break
        size = len(turn["q"]) + sum(len(a) for a in turn["a"])
        if total + size > MAX_SESSION_CHARS and capped:
            break
        capped.append(turn)
        total += size
    return capped


def _dedupe(texts: list) -> list:
    out = []
    for t in texts:
        if not out or out[-1] != t:
            out.append(t)
    return out


def local_day_bounds_ms(date_str: str) -> tuple[int, int]:
    day_start = datetime.strptime(date_str, "%Y-%m-%d").astimezone()
    start_ms = int(day_start.timestamp() * 1000)
    return start_ms, start_ms + 86_400_000


def extract_zcode(date_str: str) -> list:
    """ZCode 会话存在本地 SQLite 中，消息全文在 part 表的 text 部件里。"""
    if not ZCODE_DB.exists():
        return []
    start_ms, end_ms = local_day_bounds_ms(date_str)
    con = sqlite3.connect(f"file:{ZCODE_DB.as_posix()}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT id, title, directory, time_created FROM session
               WHERE task_type='interactive' AND parent_id IS NULL
                 AND time_created < ? AND time_updated >= ?
               ORDER BY time_created""",
            (end_ms, start_ms),
        )
        rows = cur.fetchall()
        sessions = []
        for sid, title, directory, t_created in rows:
            cur.execute(
                """SELECT m.data, p.data FROM message m
                   JOIN part p ON p.message_id = m.id
                   WHERE m.session_id = ?
                     AND m.time_created >= ? AND m.time_created < ?
                   ORDER BY m.time_created, p.sequence""",
                (sid, start_ms, end_ms),
            )
            turns, cur_turn = [], None
            for mdata, pdata in cur.fetchall():
                part = json.loads(pdata)
                if part.get("type") != "text":
                    continue
                text = (part.get("text") or "").strip()
                if not text:
                    continue
                m = json.loads(mdata)
                role = m.get("role")
                if role == "user":
                    # 只取真实用户输入，排除自动注入的提醒/系统消息
                    if (m.get("semantics") or {}).get("origin") != "real_user":
                        continue
                    cur_turn = {"q": truncate(scrub(text)), "a": []}
                    turns.append(cur_turn)
                elif role == "assistant" and cur_turn is not None:
                    cur_turn["a"].append(truncate(scrub(text)))
            turns = [
                {"q": t["q"], "a": _dedupe(t["a"])}
                for t in _cap_turns(turns)
                if t["q"]
            ]
            if turns:
                project = Path(directory).name if directory else ""
                time_hm = datetime.fromtimestamp(t_created / 1000).strftime("%H:%M")
                sessions.append(
                    {
                        "source": "zcode",
                        "title": (title or "(未命名会话)").strip(),
                        "project": project,
                        "time": time_hm,
                        "turns": turns,
                    }
                )
        return sessions
    finally:
        con.close()


def extract_codex(date_str: str) -> list:
    """Codex 会话按 日期目录/rollout-*.jsonl 存放，逐行解析取对话全文。"""
    day = datetime.strptime(date_str, "%Y-%m-%d")
    day_dir = CODEX_SESSIONS / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    if not day_dir.exists():
        return []
    sessions = []
    for f in sorted(day_dir.glob("rollout-*.jsonl")):
        cwd = ""
        turns, cur_turn = [], None
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "session_meta":
                    cwd = (obj.get("payload") or {}).get("cwd", "") or cwd
                    continue
                if obj.get("type") != "response_item":
                    continue
                p = obj.get("payload") or {}
                if p.get("type") != "message":
                    continue
                role = p.get("role")
                texts = [
                    c.get("text", "")
                    for c in p.get("content", [])
                    if c.get("type") in ("input_text", "output_text")
                ]
                text = " ".join(t for t in texts if t).strip()
                if not text:
                    continue
                if role == "user":
                    # 排除系统注入的上下文块
                    if any(text.startswith(pre) for pre in CODEX_INJECTED_PREFIXES):
                        continue
                    cur_turn = {"q": truncate(scrub(text)), "a": []}
                    turns.append(cur_turn)
                elif role == "assistant" and cur_turn is not None:
                    cur_turn["a"].append(truncate(scrub(text)))
        turns = [
            {"q": t["q"], "a": _dedupe(t["a"])} for t in _cap_turns(turns) if t["q"]
        ]
        if turns:
            t = datetime.strptime(f.stem[8:23], "%Y-%m-%dT%H-%M-%S")
            sessions.append(
                {
                    "source": "codex",
                    "title": turns[0]["q"][:40],
                    "project": Path(cwd).name if cwd else "",
                    "time": t.strftime("%H:%M"),
                    "turns": turns,
                }
            )
    return sessions


def build_material(date_str: str) -> dict:
    sessions = extract_zcode(date_str) + extract_codex(date_str)
    sessions.sort(key=lambda s: s["time"])
    return {"date": date_str, "sessions": sessions}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="提取指定日期的对话素材")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    material = build_material(args.date)
    WORK = Path(__file__).resolve().parent / "work"
    WORK.mkdir(exist_ok=True)
    out = WORK / f"material-{args.date}.json"
    out.write_text(json.dumps(material, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in material["sessions"]:
        print(f"[{s['source']:5}] {s['time']} {s['project']:20} {s['title'][:36]} ({len(s['turns'])} 问)")
    print(f"共 {len(material['sessions'])} 个会话，已写入 {out}")
