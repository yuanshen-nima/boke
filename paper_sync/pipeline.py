"""同步管线：inbox 扫描 → 论文识别 → 归纳 → 私有草稿 → 人工审核 → 安全发布。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config, identity, normalize, render, security
from .lock import SyncLock
from .state import StateDB, now


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=config.REPO_ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _push_with_fallback(log) -> bool:
    candidates = [None, "http://127.0.0.1:7897", "http://127.0.0.1:7890"]
    for attempt in (1, 2):
        for proxy in candidates:
            args = ["push"]
            label = "直连"
            if proxy:
                args = ["-c", f"http.proxy={proxy}", "push"]
                label = f"代理 {proxy}"
            r = _git(*args)
            if r.returncode == 0:
                log(f"git push 成功（{label}）")
                return True
        if attempt == 1:
            log("push 失败，30 秒后重试一轮")
            import time

            time.sleep(30)
    log(f"push 最终失败：{r.stderr.strip()[:200]}")
    return False


class PaperSync:
    def __init__(self, offline: bool = False, log=None):
        self.cfg = config.load_private_config()
        self.offline = offline or not self.cfg.get("ai", {}).get("enabled", True)
        self.log = log or config.get_logger()
        self.state: StateDB | None = None
        self.allowlist = config.load_conversation_allowlist()
        self.project_ids = [str(x) for x in self.cfg.get("project_ids", [])]
        self.manual_map = config.load_manual_map()

    # ---------------- helpers ----------------
    def _state(self) -> StateDB:
        if self.state is None:
            self.state = StateDB(config.STATE_DB)
        return self.state

    def close(self) -> None:
        if self.state:
            self.state.close()
            self.state = None

    def _paper_dir(self, paper_id: str) -> Path:
        return config.PAPERS_DIR / render.safe_dir_name(paper_id)

    def _attribution(self, conv) -> str:
        """返回 'include' | 'needs_review'。仅对 ChatGPT 导出有意义。"""
        if conv.project_id and self.project_ids and conv.project_id in self.project_ids:
            return "include"
        if conv.conversation_key in self.allowlist:
            return "include"
        if not self.project_ids and not self.allowlist:
            # 未做任何归属配置：宁可人工确认，不凭标题猜测
            return "needs_review"
        return "needs_review"

    def _identify(self, conv, source_type: str) -> tuple[str, bool]:
        """返回 (paper_id, confident)。禁止仅凭对话标题/文件名断言同一性。"""
        key = conv.conversation_key
        if key in self.manual_map:
            return self.manual_map[key], True
        text = conv.full_text()
        doi, arxiv = identity.find_identifiers(text)
        title = ""
        m = __import__("re").search(r"论文标题[:：]\s*(.+)", text)
        if m:
            title = m.group(1).strip()
        if not (doi or arxiv) and source_type == "note_json":
            # 笔记 JSON 的标题是结构化字段，可用于标题匹配
            title = title or conv.title
        if not (doi or arxiv) and source_type == "note_md":
            title = title or conv.title
        paper_id, confident = identity.make_paper_id(doi=doi, arxiv=arxiv, title=title)
        return paper_id, confident

    # ---------------- sync ----------------
    def sync(self, dry_run: bool = False) -> int:
        config.ensure_dirs()
        files = sorted(
            [p for p in config.INBOX_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
        )
        if not files:
            self.log.info("inbox 为空，无待处理文件")
            return 0
        self.log.info(f"发现 {len(files)} 个待处理文件")
        if dry_run:
            for f in files:
                self.log.info(f"[dry-run] 将处理 {f.name}（sha256 {sha256_file(f)[:12]}…）")
            return 0
        exit_code = 0
        try:
            with SyncLock(config.LOCK_FILE):
                for f in files:
                    try:
                        if not self._process_file(f):
                            exit_code = 1
                    except Exception as err:  # 单文件失败不影响其余
                        self.log.error(f"处理 {f.name} 失败：{err}")
                        self._state().log_event("error", f"{f.name}: {err}")
                        exit_code = 1
        except RuntimeError as err:
            self.log.error(str(err))
            self.close()
            return 1
        self.close()
        return exit_code

    def _process_file(self, f: Path) -> bool:
        from . import sources

        file_hash = sha256_file(f)
        fallback_type = {
            ".zip": "chatgpt_export",
            ".json": "note_json",
            ".md": "note_md",
            ".markdown": "note_md",
        }.get(f.suffix.lower())
        if not fallback_type:
            self.log.warning(f"跳过不支持的类型 {f.name}")
            return True

        # 解析（source_type 以解析器判定为准：conversations.json 属于导出而非笔记）
        try:
            conversations, source_type = sources.parse_source(f)
        except sources.SourceError as err:
            sid = f"{file_hash[:16]}:{fallback_type}:parse"
            self._state().upsert_source(
                sid, source_type=fallback_type, paper_id="", source_path=str(f),
                source_hash=file_hash, status="error", error_message=str(err),
            )
            self._state().log_event("error", f"{f.name}: {err}")
            self.log.error(f"{f.name} 解析失败：{err}")
            return False

        self.log.info(f"{f.name}: 解析出 {len(conversations)} 个会话（{source_type}）")
        state = self._state()
        ok = True
        for conv in conversations:
            source_id = f"{file_hash[:16]}:{source_type}:{conv.conversation_key}"
            # 幂等：同一文件同一会话且已成功处理 → 跳过
            row = state.get_source(source_id)
            if row and row["status"] == "imported" and row["source_hash"] == file_hash:
                self.log.info(f"  跳过已处理会话 {conv.conversation_key[:40]}")
                continue
            try:
                self._process_conversation(conv, source_id, source_type, f, file_hash)
            except normalize.SensitiveMaterialError as err:
                state.upsert_source(
                    source_id, source_type=source_type, paper_id="", source_path=str(f),
                    source_hash=file_hash, conversation_key=conv.conversation_key,
                    status="error", error_message=f"敏感素材拦截：{err}",
                )
                state.log_event("security", f"{f.name}: 敏感素材未发送给模型：{err}")
                self.log.error(f"  会话 {conv.conversation_key[:40]} 含敏感信息，已拦截：{err}")
            except Exception as err:
                ok = False
                state.upsert_source(
                    source_id, source_type=source_type, paper_id="", source_path=str(f),
                    source_hash=file_hash, conversation_key=conv.conversation_key,
                    status="error", error_message=str(err)[:500],
                )
                state.log_event("error", f"{f.name}: {err}")
                self.log.error(f"  会话 {conv.conversation_key[:40]} 处理失败：{err}")
        return ok

    def _process_conversation(self, conv, source_id: str, source_type: str, f: Path, file_hash: str) -> None:
        state = self._state()
        state.upsert_source(
            source_id, source_type=source_type, paper_id="", source_path=str(f),
            source_hash=file_hash, conversation_key=conv.conversation_key,
            status="pending",
        )

        # 归属检查（仅 ChatGPT 导出需要）
        if source_type == "chatgpt_export" and self._attribution(conv) != "include":
            state.upsert_source(
                source_id, source_type=source_type, paper_id="", source_path=str(f),
                source_hash=file_hash, conversation_key=conv.conversation_key,
                status="needs_review",
                error_message="无法确认属于「论文阅读」项目：请将对话 ID 加入 conversation_ids.txt，"
                "或在 config.json 配置 project_ids 后重跑",
            )
            self.log.warning(f"  会话 {conv.conversation_key[:40]} 待人工确认归属")
            return

        text = conv.full_text()
        paper_id, confident = self._identify(conv, source_type)
        if not paper_id:
            state.upsert_source(
                source_id, source_type=source_type, paper_id="", source_path=str(f),
                source_hash=file_hash, conversation_key=conv.conversation_key,
                status="needs_review", error_message="无法识别论文（无 DOI/arXiv/标题）",
            )
            self.log.warning(f"  会话 {conv.conversation_key[:40]} 无法识别论文")
            return

        # 归纳（脱敏后发送；离线模式确定性提取）
        meta_new, _ = normalize.extract(text, ai_enabled=not self.offline)
        meta_new["paper_id"] = paper_id
        if not meta_new.get("title"):
            meta_new["title"] = conv.title if source_type != "chatgpt_export" else ""
        if not confident:
            # 仅标题匹配：paper 保留 needs_review 直到人工 approve
            pass

        paper_dir = self._paper_dir(paper_id)
        existing = render.load_meta(paper_dir)
        discussions = []
        if existing is None:
            meta = dict(meta_new)
            meta["paper_id"] = paper_id
            meta["created"] = now()
            human_block = ""
            paper_status = "draft" if confident else "needs_review"
            self.log.info(f"  新论文 {paper_id}（{meta.get('title', '')[:40]}）")
        else:
            meta, conflicts = render.merge_meta(existing, meta_new)
            meta["paper_id"] = paper_id
            if conflicts:
                render.write_changes_report(paper_dir, conv.conversation_key, conflicts)
                self.log.warning(f"  论文 {paper_id} 有 {len(conflicts)} 处字段冲突，已生成差异报告")
            human_block, _ = render.split_draft_md(
                (paper_dir / "draft.md").read_text(encoding="utf-8")
            )
            paper_status = state.get_paper(paper_id)["status"]
            self.log.info(f"  合并到已有论文 {paper_id}")

        # 讨论记录（追加式）；离线模式下摘录用素材开头，避免占位文案刷屏
        summary = meta_new.get("summary") or ""
        if not meta_new.get("ai_extracted"):
            summary = text[:300]
        discussions = meta.get("discussions") or []
        discussions.append(
            {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "conversation_key": conv.conversation_key,
                "summary": summary.strip()[:500],
            }
        )
        meta["discussions"] = discussions
        if conv.missing_resources:
            meta["missing_resources"] = sorted(
                set((meta.get("missing_resources") or []) + conv.missing_resources)
            )

        render.save_meta(paper_dir, meta)
        (paper_dir / "draft.md").write_text(
            render.render_draft_md(meta, discussions, human_block), encoding="utf-8"
        )
        normalized_hash = sha256_text(json.dumps(meta, ensure_ascii=False, sort_keys=True))
        state.upsert_paper(
            paper_id,
            title=meta.get("title", ""),
            year=meta.get("year"),
            venue=meta.get("venue", ""),
            status=paper_status if existing is None else None,
        )
        state.upsert_source(
            source_id, source_type=source_type, paper_id=paper_id, source_path=str(f),
            source_hash=file_hash, conversation_key=conv.conversation_key,
            normalized_hash=normalized_hash, status="imported",
        )
        state.log_event("info", f"{f.name} -> {paper_id}")

    # ---------------- 审核 / 发布 ----------------
    def approve(self, paper_id: str) -> int:
        paper = self._state().get_paper(paper_id)
        if not paper:
            self.log.error(f"论文不存在：{paper_id}")
            return 1
        self._state().upsert_paper(paper_id, status="approved")
        self.log.info(f"已批准 {paper_id}，可执行 publish")
        return 0

    def publish(self, paper_id: str, force: bool = False, no_push: bool = False) -> int:
        state = self._state()
        paper = state.get_paper(paper_id)
        if not paper:
            self.log.error(f"论文不存在：{paper_id}")
            return 1
        if paper["status"] not in ("approved", "published"):
            self.log.error(f"论文状态为 {paper['status']}，需先 approve（发布需要明确的人工审核标记）")
            return 1
        paper_dir = self._paper_dir(paper_id)
        meta = render.load_meta(paper_dir)
        if not meta:
            self.log.error(f"缺少草稿数据：{paper_dir}")
            return 1
        draft_md = (paper_dir / "draft.md").read_text(encoding="utf-8")
        human_block, _ = render.split_draft_md(draft_md)
        md = render.render_public_md(
            meta, meta.get("discussions") or [], human_block, updated=datetime.now().strftime("%Y-%m-%d")
        )
        # 发布前安全扫描（公开仓库不能包含敏感内容）
        findings = security.scan(md)
        if findings and not force:
            for f in findings:
                self.log.error(f"安全扫描[{f['kind']}] {f['name']}：{f['sample']}")
            self.log.error("发布被拦截。清理内容后重试，或确认无风险用 --force")
            return 1
        slug = render.slugify(paper_id, meta.get("title", ""))
        dest = config.PUBLIC_PAPERS_DIR / f"{slug}.md"
        content_hash = sha256_text(md)
        if paper["status"] == "published" and paper["published_hash"] == content_hash and dest.exists():
            self.log.info("内容无变化，跳过重复发布")
            return 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        state.upsert_paper(
            paper_id, status="published", published_hash=content_hash, published_slug=slug
        )
        state.log_event("info", f"published {paper_id} -> {slug}")
        import os

        if no_push or os.environ.get("PAPER_SYNC_NO_GIT"):
            self.log.info(f"已写入 {dest}（跳过 git 提交）")
            return 0
        _git("add", str(dest.relative_to(config.REPO_ROOT)))
        commit = _git("commit", "-m", f"papers: publish {slug}")
        if commit.returncode != 0:
            self.log.warning(f"git commit：{commit.stderr.strip()[:200]}")
        pull = _git("pull", "--rebase", "--autostash")
        if pull.returncode != 0:
            self.log.warning(f"git pull：{pull.stderr.strip()[:200]}")
        if _push_with_fallback(self.log):
            self.log.info(f"已发布并推送：/papers/{slug}/")
            return 0
        return 1
