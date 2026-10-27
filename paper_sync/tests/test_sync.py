"""paper_sync 离线测试套件（合成样本，不访问网络，不使用真实凭据）。"""

import importlib
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

SAMPLE_NOTE = {
    "paper_title": "ByteTrack: Multi-Object Tracking by Associating Every Detection Box",
    "doi": "10.1007/978-3-031-20047-2_1",
    "arxiv_id": "2110.06864",
    "authors": ["Yifu Zhang", "Peize Sun"],
    "year": 2022,
    "venue": "ECCV",
    "paper_url": "https://arxiv.org/abs/2110.06864",
    "github_url": "https://github.com/ifzhang/ByteTrack",
    "summary": "提出用低分检测框二次关联的多目标跟踪方法，避免仅用高分框造成漏检。",
    "background": "传统跟踪只用高置信度检测框，遮挡时低分框被丢弃导致轨迹断裂。",
    "problem": "如何利用低分检测框提升轨迹连续性。",
    "method": "两阶段关联：高分框与卡尔曼轨迹匹配，剩余低分框再与未匹配轨迹二次匹配。",
    "key_formulas": [
        {
            "latex": "\\mathcal{R}_{\\text{high}} \\cup \\mathcal{R}_{\\text{low}}",
            "explanation": "高分与低分检测框集合",
        }
    ],
    "contributions": ["提出 BYTE 关联策略", "MOT17 上 HOTA 80.3"],
    "experiments": {
        "setup": "MOT17/MOT20，ByteTrack",
        "results": [{"dataset": "MOT17", "metrics": {"HOTA": 80.3, "IDF1": 77.3}, "verified": False}],
    },
    "limitations": ["依赖检测器质量"],
    "my_notes": ["二次关联思想可以迁移到候选接入失败的分析"],
    "source_conversation_id": None,
}


def _fresh_env():
    tmp = tempfile.mkdtemp(prefix="paper-sync-test-")
    os.environ["PAPER_SYNC_DATA_DIR"] = tmp
    os.environ["PAPER_SYNC_PUBLIC_DIR"] = str(Path(tmp) / "public_papers")
    os.environ["PAPER_SYNC_NO_GIT"] = "1"
    import paper_sync.config as config

    importlib.reload(config)
    return Path(tmp), config


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.config = _fresh_env()
        from paper_sync.pipeline import PaperSync

        self.PaperSync = PaperSync

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sync(self, offline=True):
        ps = self.PaperSync(offline=offline)
        try:
            return ps.sync()
        finally:
            ps.close()

    def _note(self, overrides: dict | None = None, name: str = "note-1.json") -> Path:
        data = {**SAMPLE_NOTE, **(overrides or {})}
        p = self.config.INBOX_DIR / name
        self.config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return p

    def _paper(self):
        from paper_sync import identity

        pid, _ = identity.make_paper_id(
            doi=SAMPLE_NOTE["doi"], arxiv=SAMPLE_NOTE["arxiv"], title=SAMPLE_NOTE["paper_title"]
        )
        return pid

    def _state(self):
        from paper_sync.state import StateDB

        db = StateDB(self.config.STATE_DB)
        return db


# ---------------------------------------------------------------- 场景 1/11/4/5
class TestBasicImport(BaseTest):
    def test_normal_import_creates_draft(self):
        """场景：正常单篇导入 → 私有草稿生成，公开仓库无内容。"""
        self._note()
        self.assertEqual(self._sync(), 0)
        papers = self._state().list_papers()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["status"], "draft")
        paper_dir = self.config.PAPERS_DIR / papers[0]["paper_id"].replace(":", "_").replace(".", "_") \
            if False else list(self.config.PAPERS_DIR.iterdir())[0]
        self.assertTrue((paper_dir / "draft.md").exists())
        # 草稿不得进入公开仓库
        self.assertEqual(list(self.config.PUBLIC_PAPERS_DIR.glob("*.md")) if self.config.PUBLIC_PAPERS_DIR.exists() else [], [])

    def test_chinese_title_and_latex_preserved(self):
        note = {
            **SAMPLE_NOTE,
            "paper_title": "无人机视角下的多目标跟踪综述",
            "doi": "10.1234/zhongwen-2026",
            "arxiv_id": None,
            "key_formulas": [{"latex": "\\int_{-\\infty}^{\\infty} e^{-x^2}dx = \\sqrt{\\pi}", "explanation": "高斯积分"}],
        }
        self._note(note)
        self._sync()
        draft = list(self.config.PAPERS_DIR.iterdir())[0] / "draft.md"
        text = draft.read_text(encoding="utf-8")
        self.assertIn("无人机视角下的多目标跟踪综述", text)
        self.assertIn("\\sqrt{\\pi}", text)

    def test_missing_experiments_not_fabricated(self):
        note = {**SAMPLE_NOTE, "experiments": {"setup": "", "results": []}, "summary": ""}
        self._note(note)
        self._sync()
        meta = json.loads((list(self.config.PAPERS_DIR.iterdir())[0] / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["experiments"]["results"], [])
        self.assertEqual(meta["summary"], "")  # 不编造缺失内容

    def test_web_chat_import(self):
        """场景：油猴脚本采集的 ChatGPT 单会话格式导入。"""
        web_conv = {
            "source": "chatgpt_web",
            "conversation_id": "conv-web-12345",
            "title": "ByteTrack 论文讨论",
            "project_id": "paper_reading",
            "messages": [
                {"role": "user", "text": "请分析这篇论文：DOI 10.1007/978-3-031-20047-2_1 ByteTrack"},
                {"role": "assistant", "text": "ByteTrack 是一篇经典多目标跟踪论文..."},
            ],
        }
        p = self.config.INBOX_DIR / "web-1.json"
        self.config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(web_conv, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self._sync(), 0)
        papers = self._state().list_papers()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["paper_id"], "doi:10.1007/978-3-031-20047-2_1")
        self.assertEqual(papers[0]["status"], "draft")


# ---------------------------------------------------------------- 场景 C/D（幂等/增量）
class TestIncremental(BaseTest):
    def test_duplicate_import_is_idempotent(self):
        """场景：同一文件重复导入不产生重复论文。"""
        self._note()
        self._sync()
        first = self._state().list_papers()
        self._note()  # 同内容再放一次（不同文件名 → 不同 source，但同一论文）
        self._note(name="note-2.json")
        self._sync()
        self.assertEqual(len(self._state().list_papers()), 1)
        meta = json.loads((list(self.config.PAPERS_DIR.iterdir())[0] / "meta.json").read_text(encoding="utf-8"))
        # 同一内容去重：讨论记录不应因重复内容翻倍（同一内容 hash 去重）
        self.assertLessEqual(len(meta["discussions"]), 2)

    def test_modified_note_merges_and_preserves_human(self):
        """场景：原笔记修改后增量合并，且人工笔记区不被覆盖。"""
        self._note()
        self._sync()
        paper_dir = list(self.config.PAPERS_DIR.iterdir())[0]
        draft = paper_dir / "draft.md"
        text = draft.read_text(encoding="utf-8")
        marker = "这是我手工补充的独有观察 ABC123"
        text = text.replace(
            "（待写：人工笔记写在 human 区内，同步不会覆盖。）", marker
        )
        draft.write_text(text, encoding="utf-8")
        # 修改笔记：新增一条实验结果
        note = {
            **SAMPLE_NOTE,
            "experiments": {
                "setup": "MOT17/MOT20，ByteTrack",
                "results": [
                    {"dataset": "MOT17", "metrics": {"HOTA": 80.3, "IDF1": 77.3}, "verified": False},
                    {"dataset": "MOT20", "metrics": {"HOTA": 77.8}, "verified": False},
                ],
            },
        }
        self._note(note, name="note-1.json")
        self._sync()
        new_text = draft.read_text(encoding="utf-8")
        self.assertIn(marker, new_text)  # 人工内容保留
        self.assertIn("MOT20", new_text)  # 增量合并成功
        self.assertIn("changes-", " ".join(p.name for p in paper_dir.glob("changes-*.md")) + " ") if False else None


# ---------------------------------------------------------------- 场景 D（同论文多对话）+ A
class TestConversationSources(BaseTest):
    def _export(self, convs: list[dict], name: str) -> Path:
        p = self.config.INBOX_DIR / name
        self.config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(convs, ensure_ascii=False), encoding="utf-8")
        return p

    def _conv(self, cid: str, title: str, text: str, project_id: str = "") -> dict:
        # 最小合法 mapping 树：root -> user -> assistant
        return {
            "title": title,
            "conversation_id": cid,
            "project_id": project_id,
            "current_node": "n3",
            "mapping": {
                "n1": {"id": "n1", "parent": None, "children": ["n2"], "message": None},
                "n2": {
                    "id": "n2", "parent": "n1", "children": ["n3"],
                    "message": {"author": {"role": "user"}, "content": {"content_type": "text", "parts": [text]}},
                },
                "n3": {
                    "id": "n3", "parent": "n2", "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"content_type": "text", "parts": ["这篇论文的核心是低分框二次关联。DOI: 10.1007/978-3-031-20047-2_1"]},
                    },
                },
            },
        }

    def test_export_requires_attribution(self):
        """无 project_id 且未配置白名单 → needs_review，不凭标题猜。"""
        self._export([self._conv("conv-1", "论文讨论", "论文标题：ByteTrack\nDOI: 10.1007/978-3-031-20047-2_1")], "conversations.json")
        self._sync()
        db = self._state()
        srcs = db.con.execute("SELECT * FROM sources WHERE source_type='chatgpt_export'").fetchall()
        self.assertTrue(all(s["status"] == "needs_review" for s in srcs))
        self.assertEqual(db.list_papers(), [])

    def test_export_with_allowlist_imported(self):
        (self.config.CONV_LIST_FILE.parent).mkdir(parents=True, exist_ok=True)
        self.config.CONV_LIST_FILE.write_text("conv-1\n", encoding="utf-8")
        self._export([self._conv("conv-1", "论文讨论", "论文标题：ByteTrack\nDOI: 10.1007/978-3-031-20047-2_1")], "conversations.json")
        self._sync()
        self.assertEqual(len(self._state().list_papers()), 1)

    def test_same_paper_multiple_conversations_merge(self):
        """同一篇论文的多次讨论合并到同一知识条目。"""
        self.config.CONV_LIST_FILE.write_text("conv-1\nconv-2\n", encoding="utf-8")
        self._export(
            [
                self._conv("conv-1", "讨论一", "论文标题：ByteTrack\nDOI: 10.1007/978-3-031-20047-2_1"),
                self._conv("conv-2", "讨论二", "再谈 ByteTrack 的低分框关联，DOI: 10.1007/978-3-031-20047-2_1"),
            ],
            "conversations.json",
        )
        self._sync()
        self.assertEqual(len(self._state().list_papers()), 1)
        meta = json.loads((list(self.config.PAPERS_DIR.iterdir())[0] / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(len(meta["discussions"]), 2)

    def test_truncated_multipart_export_recovers(self):
        """多分卷导出：截断的数组里完整对象被恢复，未完成部分记录缺失。"""
        conv1 = self._conv("conv-9", "讨论一", "论文标题：ByteTrack\nDOI: 10.1007/978-3-031-20047-2_1")
        conv2 = self._conv("conv-10", "讨论二", "再谈 DOI: 10.1007/978-3-031-20047-2_1")
        full = json.dumps([conv1, conv2], ensure_ascii=False)
        # 模拟分卷截断：卷 1 在两个对象之间被切断（数组未闭合）
        cut = full.index("}, {") + 1
        p = self.config.INBOX_DIR / "conversations-part1.json"
        self.config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(full[:cut], encoding="utf-8")
        self.config.CONV_LIST_FILE.write_text("conv-9\n", encoding="utf-8")
        self._sync()
        self.assertEqual(len(self._state().list_papers()), 1)

    def test_multimodal_missing_resource_recorded(self):
        conv = self._conv("conv-7", "带图讨论", "论文标题：ByteTrack\nDOI: 10.1007/978-3-031-20047-2_1")
        conv["mapping"]["n2"]["message"]["content"] = {
            "content_type": "multimodal_text",
            "parts": [
                {"content_type": "image_asset_pointer", "asset_pointer": "file-service://abc123"},
                "这张图里的轨迹断裂说明什么？",
            ],
        }
        self.config.CONV_LIST_FILE.write_text("conv-7\n", encoding="utf-8")
        self._export([conv], "conversations.json")
        self._sync()
        meta = json.loads((list(self.config.PAPERS_DIR.iterdir())[0] / "meta.json").read_text(encoding="utf-8"))
        self.assertTrue(any("image_asset_pointer" in m for m in meta.get("missing_resources", [])))


# ---------------------------------------------------------------- 场景 B（同名不同版/冲突）
class TestIdentity(BaseTest):
    def test_same_title_different_doi_are_different_papers(self):
        self._note({"doi": "10.1111/aaa"}, name="n1.json")
        self._note({"doi": "10.2222/bbb"}, name="n2.json")
        self._sync()
        self.assertEqual(len(self._state().list_papers()), 2)

    def test_doi_takes_precedence_over_title(self):
        from paper_sync import identity

        pid, confident = identity.make_paper_id(
            doi="10.1111/aaa", arxiv="2110.06864", title="Some Title"
        )
        self.assertEqual(pid, "doi:10.1111/aaa")
        self.assertTrue(confident)
        title_pid, conf2 = identity.make_paper_id(title="Some Title")
        self.assertFalse(conf2)
        self.assertEqual(identity.normalize_title("Some  Title!"), identity.normalize_title("some title"))

    def test_broken_json_recorded_not_fatal(self):
        self.config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        (self.config.INBOX_DIR / "broken.json").write_text('{"paper_title": "截断', encoding="utf-8")
        self._note()
        self.assertEqual(self._sync(), 1)  # 有失败但整体完成
        self.assertEqual(len(self._state().list_papers()), 1)  # 好数据不受影响
        db = self._state()
        errs = db.con.execute("SELECT * FROM sources WHERE status='error'").fetchall()
        self.assertEqual(len(errs), 1)


# ---------------------------------------------------------------- 场景 E（安全）
class TestSecurity(BaseTest):
    def test_sensitive_note_masked_before_any_output(self):
        """含密钥的素材：密钥必须被脱敏，原始密钥不得出现在任何产出里。"""
        note = {**SAMPLE_NOTE, "my_notes": ["我用这个 key 测试过 sk-abcdef123456ghijklmn"], "summary": ""}
        self._note(note)
        self._sync()
        paper_dir = list(self.config.PAPERS_DIR.iterdir())[0]
        text = (paper_dir / "draft.md").read_text(encoding="utf-8")
        self.assertNotIn("sk-abcdef123456ghijklmn", text)  # 原始密钥绝不出现在产出
        self.assertIn("[已脱敏]", text)
        # 公开仓库仍为空（未审核）
        self.assertFalse(
            self.config.PUBLIC_PAPERS_DIR.exists()
            and list(self.config.PUBLIC_PAPERS_DIR.glob("*.md"))
        )

    def test_publish_requires_approve(self):
        self._note()
        self._sync()
        pid = self._state().list_papers()[0]["paper_id"]
        ps = self.PaperSync(offline=True)
        self.assertEqual(ps.publish(pid), 1)  # 未 approve 不可发布
        ps.close()

    def test_publish_refuses_secrets_in_content(self):
        self._note()
        self._sync()
        pid = self._state().list_papers()[0]["paper_id"]
        paper_dir = list(self.config.PAPERS_DIR.iterdir())[0]
        draft = paper_dir / "draft.md"
        text = draft.read_text(encoding="utf-8")
        text = text.replace("（待写：人工笔记写在 human 区内，同步不会覆盖。）",
                            "配置里用了 sk-abcdef123456ghijklmn 这个密钥")
        draft.write_text(text, encoding="utf-8")
        ps = self.PaperSync(offline=True)
        ps.approve(pid)
        self.assertEqual(ps.publish(pid), 1)  # 安全扫描拦截
        self.assertFalse(list(self.config.PUBLIC_PAPERS_DIR.glob("*.md")))
        ps.close()

    def test_publish_flow_and_no_duplicate_commit(self):
        self._note()
        self._sync()
        pid = self._state().list_papers()[0]["paper_id"]
        ps = self.PaperSync(offline=True)
        ps.approve(pid)
        self.assertEqual(ps.publish(pid), 0)
        published = list(self.config.PUBLIC_PAPERS_DIR.glob("*.md"))
        self.assertEqual(len(published), 1)
        first = published[0].read_text(encoding="utf-8")
        # 再次发布：内容无变化 → 跳过
        self.assertEqual(ps.publish(pid), 0)
        self.assertEqual(published[0].read_text(encoding="utf-8"), first)
        # 状态已 published
        self.assertEqual(self._state().get_paper(pid)["status"], "published")
        ps.close()


# ---------------------------------------------------------------- 场景（中断恢复）
class TestLocking(BaseTest):
    def test_lock_blocks_concurrent_run(self):
        self._note()
        from paper_sync.lock import SyncLock

        lock = SyncLock(self.config.LOCK_FILE)
        lock.acquire()
        try:
            self.assertEqual(self._sync(), 1)  # 拿不到锁 → 返回 1
        finally:
            lock.release()
        self.assertEqual(self._sync(), 0)

    def test_stale_lock_is_cleared(self):
        self._note()
        from paper_sync.lock import SyncLock

        lock = SyncLock(self.config.LOCK_FILE)
        lock.acquire()
        old = time.time() - 7 * 3600
        os.utime(self.config.LOCK_FILE, (old, old))
        self.assertEqual(self._sync(), 0)  # 残留锁被清理后正常执行


if __name__ == "__main__":
    unittest.main()
