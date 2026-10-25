"""草稿渲染与合并。

私有草稿 = paper 目录下 meta.json（结构化字段）+ draft.md（可读版）。
draft.md 分两个区域：
  machine 区（同步自动更新）与 human 区（人工笔记，同步永不覆盖）。
合并策略：列表字段并集；标量字段仅在为空时填充，冲突记录到 changes-*.md，不直接覆盖。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

MACHINE_BEGIN = "<!-- machine:begin 同步区域（自动更新） -->"
MACHINE_END = "<!-- machine:end -->"
HUMAN_BEGIN = "<!-- human:begin 人工笔记区（同步永不覆盖） -->"
HUMAN_END = "<!-- human:end -->"

LIST_FIELDS = ("authors", "contributions", "limitations", "my_notes", "missing")
SCALAR_FIELDS = ("title", "venue", "doi", "arxiv", "paper_url", "github_url", "summary", "background", "problem", "method")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_dir_name(paper_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", paper_id)


def load_meta(paper_dir: Path) -> dict | None:
    p = paper_dir / "meta.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_meta(paper_dir: Path, meta: dict) -> None:
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def merge_meta(existing: dict, incoming: dict) -> tuple[dict, list[str]]:
    """合并新旧 meta：列表并集、标量补空、冲突记录（不覆盖）。返回 (meta, 冲突描述)。"""
    conflicts: list[str] = []
    meta = dict(existing)
    for f in LIST_FIELDS:
        old = list(meta.get(f) or [])
        new = [x for x in (incoming.get(f) or []) if x and x not in old]
        if new:
            meta[f] = old + new
    for f in SCALAR_FIELDS:
        old, new = (meta.get(f) or ""), (incoming.get(f) or "")
        if new and not old:
            meta[f] = new
        elif new and old and str(new) != str(old):
            conflicts.append(f"{f}: 保留「{str(old)[:60]}」，未采用「{str(new)[:60]}」")
    if incoming.get("year") and not meta.get("year"):
        meta["year"] = incoming["year"]
    # 公式：按 latex 去重合并
    old_f = meta.get("formulas") or []
    seen = {f.get("latex", "") for f in old_f}
    for f in incoming.get("formulas") or []:
        if f.get("latex") and f["latex"] not in seen:
            f.setdefault("verified", False)
            old_f.append(f)
            seen.add(f["latex"])
    meta["formulas"] = old_f
    # 实验结果：按 dataset 去重合并
    exp = meta.get("experiments") or {"setup": "", "results": []}
    old_r = exp.get("results") or []
    seen_ds = {(r.get("dataset", ""), json.dumps(r.get("metrics", {}), sort_keys=True)) for r in old_r}
    for r in incoming.get("experiments", {}).get("results") or []:
        key = (r.get("dataset", ""), json.dumps(r.get("metrics", {}), sort_keys=True))
        if key not in seen_ds:
            r.setdefault("verified", False)
            old_r.append(r)
            seen_ds.add(key)
    if incoming.get("experiments", {}).get("setup") and not exp.get("setup"):
        exp["setup"] = incoming["experiments"]["setup"]
    meta["experiments"] = exp
    meta["updated"] = now_iso()
    return meta, conflicts


def _meta_table(meta: dict) -> str:
    rows = []
    if meta.get("authors"):
        rows.append(("作者", "、".join(meta["authors"]) + "（来源：对话/笔记，未核实）"))
    if meta.get("year"):
        rows.append(("年份", meta["year"]))
    if meta.get("venue"):
        rows.append(("发表场所", meta["venue"]))
    if meta.get("doi"):
        rows.append(("DOI", meta["doi"]))
    if meta.get("arxiv"):
        rows.append(("arXiv", meta["arxiv"]))
    if meta.get("paper_url"):
        rows.append(("论文地址", meta["paper_url"]))
    if meta.get("github_url"):
        rows.append(("代码仓库", meta["github_url"]))
    return "\n".join(f"| {k} | {v} |" for k, v in rows)


def render_machine_block(meta: dict, discussions: list[dict]) -> str:
    parts = [MACHINE_BEGIN, f"# {meta.get('title') or '(未命名论文)'}", ""]
    if meta.get("ai_extracted"):
        parts.append("> ⚠️ 本条目由 AI 从对话中提取，所有公式与实验数字均未核实，引用前请对照原文。\n")
    tbl = _meta_table(meta)
    if tbl:
        parts += ["| 字段 | 值 |", "| --- | --- |", tbl, ""]
    if meta.get("summary"):
        parts += ["## 核心摘要", meta["summary"], ""]
    for key, label in (("background", "研究背景"), ("problem", "主要问题"), ("method", "核心方法")):
        if meta.get(key):
            parts += [f"## {label}", meta[key], ""]
    if meta.get("formulas"):
        parts.append("## 关键公式")
        for f in meta["formulas"]:
            state = "已核实" if f.get("verified") else "**未核实**"
            parts += [f"$\n{f.get('latex', '')}\n$", f"- {f.get('explanation', '')}（核验状态：{state}）", ""]
    if meta.get("contributions"):
        parts.append("## 创新贡献")
        parts += [f"- {c}" for c in meta["contributions"]] + [""]
    exp = meta.get("experiments") or {}
    if exp.get("setup") or exp.get("results"):
        parts.append("## 实验")
        if exp.get("setup"):
            parts += [f"设置：{exp['setup']}", ""]
        for r in exp.get("results") or []:
            state = "已核实" if r.get("verified") else "**未核实**"
            parts.append(f"- {r.get('dataset', '?')}：{json.dumps(r.get('metrics', {}), ensure_ascii=False)}（核验状态：{state}）")
        parts.append("")
    if meta.get("limitations"):
        parts.append("## 论文局限")
        parts += [f"- {c}" for c in meta["limitations"]] + [""]
    if meta.get("my_notes"):
        parts.append("## 我的研究启发（来自对话）")
        parts += [f"- {c}" for c in meta["my_notes"]] + [""]
    if discussions:
        parts.append("## 讨论记录")
        for d in discussions:
            parts += [f"### {d.get('date', '')} · {d.get('conversation_key', '')}", d.get("summary", ""), ""]
    if meta.get("missing_resources"):
        parts.append("## 缺失资源")
        parts += [f"- {m}" for m in meta["missing_resources"]] + [""]
    parts.append(MACHINE_END)
    return "\n".join(parts)


def render_draft_md(meta: dict, discussions: list[dict], human_block: str) -> str:
    machine = render_machine_block(meta, discussions)
    human = human_block.strip() or "（待写：人工笔记写在 human 区内，同步不会覆盖。）"
    return (
        f"---\ntitle: {meta.get('title') or '(未命名论文)'}\n"
        f"paper_id: {meta.get('paper_id', '')}\n---\n\n"
        + machine
        + "\n\n"
        + HUMAN_BEGIN
        + "\n"
        + human
        + "\n"
        + HUMAN_END
        + "\n"
    )


def split_draft_md(text: str) -> tuple[str, str]:
    """从既有 draft.md 拆出 human 区内容（保护人工编辑）。"""
    m = re.search(re.escape(HUMAN_BEGIN) + r"\n(.*?)" + re.escape(HUMAN_END), text, re.DOTALL)
    return (m.group(1).strip() if m else ""), bool(m)


def write_changes_report(paper_dir: Path, source_key: str, conflicts: list[str]) -> None:
    if not conflicts:
        return
    report = paper_dir / f"changes-{datetime.now():%Y%m%d-%H%M%S}.md"
    report.write_text(
        f"# 同步冲突报告（{source_key}）\n\n以下字段存在差异，已保留现有值，未覆盖：\n\n"
        + "\n".join(f"- {c}" for c in conflicts)
        + "\n",
        encoding="utf-8",
    )


# ---- 公开版渲染 ----
def slugify(paper_id: str, title: str) -> str:
    t = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    words = re.findall(r"[a-z0-9]+", t.lower())[:6]
    base = "-".join(words) if words else ""
    h = re.sub(r"[^A-Za-z0-9]", "", paper_id)[:12]
    slug = (base + "-" if base else "") + h
    return slug[:64].strip("-") or "paper"


def render_public_md(meta: dict, discussions: list[dict], human_block: str, updated: str) -> str:
    fm = {
        "title": meta.get("title") or "(未命名论文)",
        "description": (meta.get("summary") or "")[:150],
        "paperId": meta.get("paper_id", ""),
        "topics": ["论文精读"],
        "tags": (["论文", meta.get("venue", "")] if meta.get("venue") else ["论文"]),
        "draft": False,
        "updated": updated,
    }
    if meta.get("year"):
        fm["year"] = meta["year"]
    if meta.get("doi"):
        fm["doi"] = meta["doi"]
    if meta.get("arxiv"):
        fm["arxiv"] = meta["arxiv"]
    if meta.get("paper_url"):
        fm["paperUrl"] = meta["paper_url"]
    if meta.get("github_url"):
        fm["githubUrl"] = meta["github_url"]
    fm_lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, bool):
            fm_lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, int):
            fm_lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            fm_lines.append(f"{k}: {json.dumps([str(x) for x in v], ensure_ascii=False)}")
        else:
            if v == "":
                continue
            # YAML 值统一 JSON 转义，避免标题/摘要中的冒号破坏 frontmatter
            fm_lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    fm_lines.append("---")
    machine = render_machine_block(meta, discussions)
    # 公开版不需要 machine 标记
    machine = machine.replace(MACHINE_BEGIN + "\n", "").replace("\n" + MACHINE_END, "")
    human = human_block.strip()
    human_md = ("\n\n## 我的研究笔记\n\n" + human) if human else ""
    return "\n".join(fm_lines) + "\n\n" + machine + human_md + "\n"
