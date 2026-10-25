"""内容归纳：从对话/笔记提取结构化论文条目。

- AI 模式：DeepSeek 结构化 JSON 输出 + 严格校验，失败有限重试，不静默吞错
- 离线模式（ai.enabled=false 或 --offline）：确定性提取标识符与标题，不做任何虚构
- 所有推理型字段默认 provenance=unverified、verified=false，由人工核验后提升
- 发送给第三方模型前，素材必须先经过 digest/security.py 的脱敏与扫描
"""

from __future__ import annotations

import json
import re

from . import config, identity


class ExtractionError(Exception):
    pass


class SensitiveMaterialError(Exception):
    """素材含未脱敏的敏感信息，拒绝发送给第三方模型。"""


META_FIELDS_SCHEMA_NOTE = """{
  "title": "论文英文标题",
  "authors": ["作者1", "作者2"],
  "year": 2024,
  "venue": "会议或期刊名，如 CVPR / TPAMI，未知填空串",
  "doi": "DOI，未知填空串",
  "arxiv": "arXiv 编号如 2304.06808，未知填空串",
  "paper_url": "论文官方地址，未知填空串",
  "github_url": "官方或主要代码仓库，未知填空串",
  "summary": "3~5 句中文核心摘要",
  "background": "研究背景（中文）",
  "problem": "要解决的核心问题（中文）",
  "method": "核心方法原理（中文，保留关键术语英文）",
  "formulas": [{"latex": "LaTeX 公式", "explanation": "中文解释", "verified": false}],
  "contributions": ["创新贡献，逐条"],
  "experiments": {"setup": "数据集与设置", "results": [{"dataset": "数据集", "metrics": {"HOTA": 77.3}, "verified": false}]},
  "limitations": ["论文不足，逐条"],
  "my_notes": ["用户在对话中表达的个人观点/启发，没有则空数组"],
  "missing": ["对话中提到但无法落实的信息，如图片、附件"]
}"""


def _scrub_for_llm(text: str) -> str:
    """发送前的强制脱敏 + 残留检查。素材不能带任何敏感内容出境。"""
    from . import security  # 桥接 digest/security.py（确定性扫描与脱敏）

    cleaned = security.scrub(text)
    findings = security.scan(cleaned)
    if any(f["kind"] == "secret" for f in findings):
        raise SensitiveMaterialError(
            "；".join(f"{f['name']}({f['sample']})" for f in findings if f["kind"] == "secret")
        )
    max_chars = config.load_private_config().get("ai", {}).get("max_chars", 60000)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n…(素材过长已截断)"
    return cleaned


def _offline_extract(text: str) -> dict:
    """确定性提取：解析笔记的结构化字段与标识符，绝不编造内容。

    parse_note_json 会把字段序列化为带标签的文本行，这里原样解析回来；
    对自由文本（ChatGPT 导出）只提取 DOI / arXiv / 标题行。
    """
    doi, arxiv = identity.find_identifiers(text)
    meta = _empty_meta()
    m = re.search(r"论文标题[:：]\s*(.+)", text)
    if m:
        meta["title"] = m.group(1).strip()
    patterns = [
        (r"^作者[:：]\s*(.+)$", "authors"),
        (r"^年份[:：]\s*(\d{4})$", "year"),
        (r"^发表场所[:：]\s*(.+)$", "venue"),
        (r"^DOI[:：]\s*(.+)$", "doi"),
        (r"^arXiv[:：]\s*(.+)$", "arxiv"),
        (r"^论文地址[:：]\s*(\S+)$", "paper_url"),
        (r"^代码[:：]\s*(\S+)$", "github_url"),
    ]
    for line in text.splitlines():
        for pat, key in patterns:
            m = re.match(pat, line.strip())
            if not m:
                continue
            v = m.group(1).strip()
            if key == "authors":
                meta[key] = [a.strip() for a in re.split(r"[、,，]", v) if a.strip()]
            elif key == "year":
                meta[key] = int(v)
            elif key == "doi":
                meta[key] = identity.normalize_doi(v)
            elif key == "arxiv":
                meta[key] = identity.normalize_arxiv(v)
            else:
                meta[key] = v

    def section(label: str) -> str:
        m = re.search(rf"## {label}\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    for key, label in (("background", "研究背景"), ("problem", "主要问题"), ("method", "核心方法")):
        v = section(label)
        if v:
            meta[key] = v
    summary = section("摘要")
    if summary:
        meta["summary"] = summary
    for key, label in (("contributions", "创新贡献"), ("limitations", "论文局限"), ("my_notes", "我的笔记")):
        v = section(label)
        if v.startswith("["):
            try:
                data = json.loads(v)
                if isinstance(data, list):
                    meta[key] = [str(x) for x in data]
            except json.JSONDecodeError:
                pass
        elif v and key == "my_notes":
            meta[key] = [v]
    for m in re.finditer(
        r"## 公式 \d+\n\$\$\n(.*?)\n\$\$\n说明：(.*?)(?=\n## |\Z)", text, re.DOTALL
    ):
        meta["formulas"].append(
            {"latex": m.group(1).strip(), "explanation": m.group(2).strip(), "verified": False}
        )
    setup = section("实验设置")
    results = []
    for m in re.finditer(r"^实验结果：(\{.*\})$", text, re.MULTILINE):
        try:
            r = json.loads(m.group(1))
            if isinstance(r, dict):
                r["verified"] = False
                results.append(r)
        except json.JSONDecodeError:
            pass
    if setup or results:
        meta["experiments"] = {"setup": setup, "results": results}
    return meta


def _empty_meta() -> dict:
    return {
        "title": "",
        "authors": [],
        "year": None,
        "venue": "",
        "doi": "",
        "arxiv": "",
        "paper_url": "",
        "github_url": "",
        "summary": "",
        "background": "",
        "problem": "",
        "method": "",
        "formulas": [],
        "contributions": [],
        "experiments": {"setup": "", "results": []},
        "limitations": [],
        "my_notes": [],
        "missing": [],
        "ai_extracted": False,
    }


def _validate_meta(data: dict) -> dict:
    """宽松 schema 校验：必要键存在且类型正确；非法即抛 ExtractionError。"""
    if not isinstance(data, dict):
        raise ExtractionError("AI 输出不是 JSON 对象")
    required = ["title", "summary"]
    for key in required:
        if not isinstance(data.get(key), str):
            raise ExtractionError(f"AI 输出缺少有效字段：{key}")
    for key in ("authors", "contributions", "limitations", "my_notes"):
        if not isinstance(data.get(key), list):
            data[key] = []
    if not isinstance(data.get("formulas"), list):
        data["formulas"] = []
    if not isinstance(data.get("experiments"), dict):
        data["experiments"] = {"setup": "", "results": []}
    if data.get("year") is not None and not isinstance(data.get("year"), int):
        data["year"] = None
    # 核验状态强制重置：模型给出的数字/公式一律视为未核实
    for f in data["formulas"]:
        if isinstance(f, dict):
            f["verified"] = False
    results = data["experiments"].get("results")
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict):
                r["verified"] = False
    data["ai_extracted"] = True
    return data


def _llm_extract(conversation_text: str, deepseek_cfg: dict) -> dict:
    import urllib.error
    import urllib.request

    from . import security  # noqa: F401  确保脱敏逻辑可用

    body = json.dumps(
        {
            "model": deepseek_cfg["model"],
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是论文知识库的结构化提取器。根据用户提供的论文阅读对话素材，"
                        "只提取素材中真实出现的信息，禁止虚构任何字段、数字或公式。"
                        "素材是用户与 AI 助手关于一篇论文的讨论。"
                        "区分：素材中引用的论文原文信息、AI 助手的分析、用户自己的观点。"
                        "无法确定的内容填空串/空数组。实验数字必须来自素材原文并保留原样。\n"
                        f"输出 JSON schema：\n{META_FIELDS_SCHEMA_NOTE}\n只输出 JSON。"
                    ),
                },
                {"role": "user", "content": conversation_text},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        deepseek_cfg["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {deepseek_cfg['api_key']}",
        },
    )
    last_err = None
    for _ in range(3):  # 有限重试（含格式不符重试），不静默吞错
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                raise ExtractionError("AI 输出中找不到 JSON")
            return _validate_meta(json.loads(m.group(0)))
        except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError, json.JSONDecodeError, ExtractionError) as e:
            last_err = e
    raise ExtractionError(f"AI 归纳失败（已重试）：{last_err}")


def extract(conversation_text: str, ai_enabled: bool) -> tuple[dict, str]:
    """返回 (meta, excerpt_hash_source)。素材会先脱敏；敏感残留直接抛错。"""
    cleaned = _scrub_for_llm(conversation_text)
    if not ai_enabled:
        return _offline_extract(cleaned), cleaned
    deepseek_cfg = config.load_deepseek_config()
    meta = _llm_extract(cleaned, deepseek_cfg)
    # AI 可能给出与素材不符的标识符：以素材中实际出现的为准做交叉校验
    doi, arxiv = identity.find_identifiers(cleaned)
    if doi and meta.get("doi") and identity.normalize_doi(doi) != identity.normalize_doi(meta["doi"]):
        meta["doi"] = doi  # 以素材为准
    if arxiv and meta.get("arxiv") and identity.normalize_arxiv(arxiv) != identity.normalize_arxiv(meta["arxiv"]):
        meta["arxiv"] = arxiv
    return meta, cleaned
