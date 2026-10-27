"""数据源适配层。

SourceAdapter 是预留接口（Source C）：未来若出现官方授权的 Projects 读取 API，
实现一个新适配器接入 pipeline 即可。当前不存在这样的公开 API，
本模块不实现任何私有接口抓取（见 docs/paper-sync-limitations.md）。
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedMessage:
    role: str  # user | assistant | system | tool
    text: str
    time: str = ""


@dataclass
class ParsedConversation:
    conversation_key: str  # 会话唯一标识（conversation_id 或内容哈希）
    title: str = ""
    project_id: str = ""  # 官方字段，可能为空；为空时需对话 ID 清单或人工确认
    messages: list[ParsedMessage] = field(default_factory=list)
    missing_resources: list[str] = field(default_factory=list)  # 无法提取的附件/图片记录

    def full_text(self) -> str:
        lines = []
        for m in self.messages:
            who = "用户" if m.role == "user" else ("助手" if m.role == "assistant" else m.role)
            lines.append(f"{who}：{m.text}")
        return "\n\n".join(lines)

    def find_paper_report(self) -> str | None:
        """从会话消息中寻找现成的高质量论文精读长文。"""
        for m in self.messages:
            if m.role != "assistant":
                continue
            t = m.text.strip()
            if len(t) < 800:
                continue
            # 特征 1：明确以论文精读/深度解读为标题
            if re.search(r"^#\s*(论文精读|论文解读|深度解读)", t, re.MULTILINE):
                return t
            # 特征 2：包含总体深度解读或多级章节分析
            if ("总体深度解读" in t or "一、研究目标" in t) and ("二、创新方法" in t or "核心方法" in t):
                return t
        return None


def genui_to_markdown(raw_json: str) -> str:
    """将 ChatGPT 的 genui 交互图表组件（charts_widget_v2）转为标准 Markdown 表格。"""
    try:
        obj = json.loads(raw_json)
        cw = obj.get("charts_widget_v2", {}).get("content", {})
        if not cw:
            return ""
        meta = cw.get("meta", {})
        title = meta.get("title", "")
        desc = meta.get("description", "")
        series = cw.get("series", [])
        data = cw.get("data", [])
        x_key = cw.get("xKey", "")

        lines = []
        if title:
            lines.append(f"**{title}**")
        if desc:
            lines.append(f"*{desc}*")
        lines.append("")

        x_col = "类别"
        if x_key == "dataset":
            x_col = "数据集"
        elif x_key == "stage":
            x_col = "阶段"

        headers = [x_col]
        for s in series:
            headers.append(s.get("label", s.get("dataKey", "")))
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in data:
            x_val = str(row.get(x_key, ""))
            vals = [x_val]
            for s in series:
                k = s.get("dataKey", "")
                vals.append(str(row.get(k, "")))
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)
    except Exception:
        return ""


def clean_chatgpt_artifacts(text: str) -> str:
    """清理 ChatGPT 特有的内部标记与自定义组件标签，还原标准 Markdown。"""
    if not text:
        return ""

    # 1. genui charts -> Markdown table
    def _replace_genui(m):
        raw = m.group(1)
        md = genui_to_markdown(raw)
        return "\n\n" + md + "\n\n" if md else ""

    text = re.sub(r"[\ue200\ue201]?genui[\ue202\ue203](.*?)[\ue200\ue201]", _replace_genui, text, flags=re.DOTALL)

    # 2. 还原 ChatGPT 内部链接标记：\ue200url\ue202Title\ue202Url\ue201 -> [Title](Url)
    text = re.sub(r"[\ue200\ue201]?url[\ue202\ue203](.*?)[\ue202\ue203](.*?)[\ue200\ue201]", r"[\1](\2)", text)

    # 3. 实体标记：\ue200entity\ue202["type","Name",...]\ue201 -> Name
    text = re.sub(r"[\ue200\ue201]?entity[\ue202\ue203]\[\"[^\"]*\",\"([^\"]*)\"[^\]]*\][\ue200\ue201]", r"\1", text)

    # 4. 文件引用与搜索引用标记：彻底清除
    text = re.sub(r"[\ue200\ue201]?filecite[\ue202\ue203].*?[\ue200\ue201]", "", text)
    text = re.sub(r"[\ue200\ue201]?cite[\ue202\ue203].*?[\ue200\ue201]", "", text)
    text = re.sub(r"[\ue200\ue201]?image_group[\ue202\ue203].*?[\ue200\ue201]", "", text)

    # 5. 去除多余的 PUA 控制字符 (\ue200 - \ue20f)
    text = re.sub(r"[\ue200-\ue20f]", "", text)

    # 6. 去除 ChatGPT 自定义组件标签
    text = re.sub(r"<MemoryCite\s*/>", "", text)
    text = re.sub(r"<FileCite[^>]*/>", "", text)
    text = re.sub(r"<AsyncImage[^>]*/>", "", text)

    # 7. 转换 Math 公式：\[ \] -> $$ $$, \( \) -> $ $
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\n\1\n$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)

    # 8. 修复被反斜杠转义的 Markdown 加粗标记 \*\* -> **
    text = re.sub(r"\\\*\\\*", "**", text)

    # 9. 清理多余连续换行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_report_meta(text: str) -> dict:
    """从论文精读报告正文或头部解析结构化元信息。"""
    meta: dict = {}
    m = re.search(r"(?:\*\*论文名称[：:]\*\*|论文名称[：:])\s*(.+)", text)
    if m:
        meta["title"] = m.group(1).strip()
    m = re.search(r"(?:\*\*中文译名[：:]\*\*|中文译名[：:])\s*(.+)", text)
    if m:
        meta["chinese_title"] = m.group(1).strip()
    m = re.search(r"(?:\*\*作者[：:]\*\*|作者[：:])\s*(.+)", text)
    if m:
        meta["authors"] = [a.strip() for a in re.split(r"[、,，]", m.group(1)) if a.strip()]
    m = re.search(r"(?:\*\*机构[：:]\*\*|机构[：:])\s*(.+)", text)
    if m:
        meta["institution"] = m.group(1).strip()
    m = re.search(
        r"(?:\*\*开源地址[：:]\*\*|开源地址[：:]|代码仓库[：:])\s*(?:\[.*?\]\((https?://[^\s\)]+)\)|(https?://\S+))",
        text,
    )
    if m:
        meta["github_url"] = (m.group(1) or m.group(2) or "").strip()
    m = re.search(r"## 总体深度解读\s*\n\n(.*?)(?=\n\n|\Z)", text, re.DOTALL)
    if m:
        meta["summary"] = re.sub(r"[\*#\[\]]", "", m.group(1)).strip()
    return meta


class SourceError(Exception):
    """源数据损坏、截断或不可解析。"""


def parse_source(path: Path) -> tuple[list[ParsedConversation], str]:
    """按扩展名/文件名分发到具体适配器。返回 (会话列表, source_type)。"""
    p = Path(path)
    name = p.name.lower()
    # ChatGPT 官方导出：zip 包，或 conversations.json（含 conversations-partN.json 分卷）
    if p.suffix.lower() == ".zip" or name.startswith(("conversations", "chatgpt_export", "chatgpt-export")):
        return parse_chatgpt_export(p), "chatgpt_export"
    if p.suffix.lower() == ".json":
        return parse_json_source(p)
    if p.suffix.lower() in (".md", ".markdown"):
        return [parse_note_md(p)], "note_md"
    raise SourceError(f"不支持的输入类型：{p.name}（支持 zip / conversations.json / .json / .md）")


# ---------------------------------------------------------------- Source C 接口
class SourceAdapter:
    """未来官方授权接口的适配器基类。当前不存在可用的 ChatGPT Projects API。"""

    name = "base"

    def list_conversations(self) -> list[ParsedConversation]:  # pragma: no cover
        raise NotImplementedError("当前无官方 Projects API，等待平台支持后实现")


# ---------------------------------------------------------------- Source A
def _iter_json_values(text: str):
    """容错解析：支持单个值、拼接的多个 JSON 值、以及被分卷截断的 JSON 数组。"""
    dec = json.JSONDecoder()
    idx, n = 0, len(text)
    values = []
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = dec.raw_decode(text, idx)
            values.append(obj)
            idx = end
        except json.JSONDecodeError:
            # 截断的数组：截取到最后一个完整对象为止
            tail = text[idx:]
            if tail.lstrip().startswith("["):
                repaired = _repair_truncated_array(tail)
                if repaired:
                    values.extend(repaired)
                    return values, True
            raise
    return values, False


def _repair_truncated_array(text: str) -> list:
    """尽力恢复被截断的 JSON 数组：按顶层对象边界切分，逐个解析成功的。"""
    dec = json.JSONDecoder()
    items = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj, _ = dec.raw_decode(text[start : i + 1])
                    items.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return items


def _walk_messages(conv: dict) -> tuple[list[ParsedMessage], list[str]]:
    """从 mapping 树按 current_node 回溯出主分支消息。"""
    mapping = conv.get("mapping") or {}
    current = conv.get("current_node")
    if not current and mapping:
        # 找没有 children 的节点作为末端
        for nid, node in mapping.items():
            if not node.get("children"):
                current = nid
                break
    chain = []
    node = mapping.get(current or "")
    while node:
        chain.append(node)
        node = mapping.get(node.get("parent") or "")
    chain.reverse()

    messages, missing = [], []
    for node in chain:
        msg = node.get("message") or {}
        role = (msg.get("author") or {}).get("role") or ""
        content = msg.get("content") or {}
        ctype = content.get("content_type", "")
        # 优先读取 ChatGPT 导出的高质量标准 Markdown
        dil = msg.get("metadata", {}).get("model_dil_v2", {})
        fb = dil.get("fallbackMarkdown") if isinstance(dil, dict) else None
        if fb and isinstance(fb, str) and fb.strip():
            text = clean_chatgpt_artifacts(fb.strip())
        elif ctype == "text":
            parts = content.get("parts") or []
            text = clean_chatgpt_artifacts("\n".join(str(p) for p in parts if isinstance(p, str) and p.strip()))
        else:
            text = ""
        if text.strip() and role in ("user", "assistant"):
            messages.append(ParsedMessage(role=role, text=text.strip()))
        elif ctype == "multimodal_text":
            # 导出数据不含可下载的图片本体，只记录缺失资源
            for part in content.get("parts") or []:
                if isinstance(part, dict) and part.get("content_type") in (
                    "image_asset_pointer",
                    "audio_transcription",
                ):
                    missing.append(
                        f"多模态资源（{part.get('content_type')}，id={part.get('asset_pointer', '?')[:24]}）"
                    )
    # 时间戳：取首条消息时间
    return messages, missing


def _conv_key(conv: dict, raw: str) -> str:
    cid = conv.get("conversation_id") or conv.get("id")
    if cid:
        return str(cid)
    import hashlib

    return "hash:" + hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:16]


def parse_chatgpt_export(path: Path) -> list[ParsedConversation]:
    """解析 ChatGPT 官方导出：zip（内含 conversations.json）、单文件或分卷 JSON。"""
    texts: list[str] = []
    p = Path(path)
    if p.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(p) as zf:
                names = [
                    n
                    for n in zf.namelist()
                    if n.endswith(".json") and "conversation" in n.lower()
                ]
                if not names:
                    raise SourceError(f"zip 中找不到 conversations.json：{p.name}")
                for n in sorted(names):
                    texts.append(zf.read(n).decode("utf-8", "replace"))
        except zipfile.BadZipFile as e:
            raise SourceError(f"损坏的 zip 文件 {p.name}：{e}") from e
    else:
        texts.append(p.read_text(encoding="utf-8-sig", errors="replace"))

    convs: list[ParsedConversation] = []
    errors: list[str] = []
    truncated_total = False
    for ti, text in enumerate(texts):
        try:
            values, truncated = _iter_json_values(text)
            truncated_total = truncated or truncated_total
        except json.JSONDecodeError as e:
            errors.append(f"第 {ti + 1} 个 JSON 分卷无法解析：{e}")
            continue
        items: list[dict] = []
        for v in values:
            if isinstance(v, dict):
                items.append(v)
            elif isinstance(v, list):
                items.extend(x for x in v if isinstance(x, dict))
        for item in items:
            if "mapping" not in item:
                continue  # 导出中的其他 json（user.json 等）跳过
            messages, missing = _walk_messages(item)
            key = _conv_key(item, text[:4096])
            conv = ParsedConversation(
                conversation_key=key,
                title=str(item.get("title") or ""),
                project_id=str(item.get("project_id") or ""),
                messages=messages,
                missing_resources=missing,
            )
            convs.append(conv)
    if errors and not convs:
        raise SourceError("；".join(errors))
    if truncated_total:
        # 有分卷截断：能恢复的已恢复，调用方可在日志中看到
        for c in convs:
            c.missing_resources.append("源文件疑似分卷截断，部分消息可能缺失")
    return convs


# ---------------------------------------------------------------- Source B
def parse_web_messages(data: dict, path: Path) -> ParsedConversation:
    """解析浏览器端油猴脚本提取的会话消息列表。"""
    raw_msgs = data.get("messages") or []
    messages = []
    for m in raw_msgs:
        role = m.get("role", "user")
        text = m.get("text") or m.get("content") or ""
        if isinstance(text, str) and text.strip():
            messages.append(
                ParsedMessage(
                    role=role,
                    text=clean_chatgpt_artifacts(text.strip()),
                    time=str(m.get("time") or ""),
                )
            )
    cid = data.get("conversation_id") or data.get("id") or ("web:" + path.stem)
    return ParsedConversation(
        conversation_key=str(cid),
        title=str(data.get("title") or path.stem),
        project_id=str(data.get("project_id") or ""),
        messages=messages,
        missing_resources=list(data.get("missing_resources") or []),
    )


def parse_json_source(path: Path) -> tuple[list[ParsedConversation], str]:
    """智能解析 JSON 文件：优先区分 ChatGPT 网页端单会话、ChatGPT 官方导出与单篇结构化笔记。"""
    try:
        content = path.read_text(encoding="utf-8-sig")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise SourceError(f"JSON 无法解析 {path.name}：{e}") from e
    if not isinstance(data, dict):
        raise SourceError(f"JSON 顶层应为对象：{path.name}")

    # 1. 顶层包含 mapping：ChatGPT 官方单个会话导出对象
    if "mapping" in data:
        messages, missing = _walk_messages(data)
        key = _conv_key(data, content[:4096])
        conv = ParsedConversation(
            conversation_key=key,
            title=str(data.get("title") or path.stem),
            project_id=str(data.get("project_id") or ""),
            messages=messages,
            missing_resources=missing,
        )
        return [conv], "chatgpt_web"

    # 2. 包含 messages 列表：油猴脚本提取的标准会话结构
    if "messages" in data and isinstance(data["messages"], list):
        return [parse_web_messages(data, path)], "chatgpt_web"

    # 3. 默认单篇结构化笔记
    return parse_note_json_data(data, path), "note_json"


def parse_note_json_data(data: dict, path: Path) -> list[ParsedConversation]:
    lines = [f"论文标题：{data.get('paper_title', '')}"]
    if data.get("authors"):
        lines.append("作者：" + "、".join(str(a) for a in data["authors"]))
    if data.get("year"):
        lines.append(f"年份：{data['year']}")
    if data.get("venue"):
        lines.append(f"发表场所：{data['venue']}")
    if data.get("doi"):
        lines.append(f"DOI：{data['doi']}")
    if data.get("arxiv_id"):
        lines.append(f"arXiv：{data['arxiv_id']}")
    if data.get("paper_url"):
        lines.append(f"论文地址：{data['paper_url']}")
    if data.get("github_url"):
        lines.append(f"代码：{data['github_url']}")
    for key, label in (
        ("summary", "摘要"),
        ("background", "研究背景"),
        ("problem", "主要问题"),
        ("method", "核心方法"),
        ("contributions", "创新贡献"),
        ("limitations", "论文局限"),
        ("my_notes", "我的笔记"),
    ):
        v = data.get(key)
        if v:
            lines.append(f"## {label}\n{json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}")
    for i, f in enumerate(data.get("key_formulas") or []):
        lines.append(f"## 公式 {i + 1}\n$$\n{f.get('latex', '')}\n$$\n说明：{f.get('explanation', '')}")
    exp = data.get("experiments") or {}
    if exp:
        lines.append(f"## 实验设置\n{exp.get('setup', '')}")
        for r in exp.get("results") or []:
            lines.append(f"实验结果：{json.dumps(r, ensure_ascii=False)}")
    text = "\n\n".join(lines)
    conv = ParsedConversation(
        conversation_key=str(data.get("source_conversation_id") or ("note:" + path.name)),
        title=str(data.get("paper_title") or path.stem),
        messages=[ParsedMessage(role="user", text=text)],
        missing_resources=[],
    )
    return [conv]


def parse_note_json(path: Path) -> list[ParsedConversation]:
    """单篇结构化笔记（JSON，schema 见 docs/chatgpt-paper-export-prompt.md）。

    整个 JSON 作为一条「会话」进入管线：字段序列化为文本，供归纳层提取。
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise SourceError(f"笔记 JSON 无法解析 {path.name}：{e}") from e
    if not isinstance(data, dict):
        raise SourceError(f"笔记 JSON 顶层应为对象：{path.name}")
    return parse_note_json_data(data, path)


def parse_note_md(path: Path) -> ParsedConversation:
    """Markdown 笔记：frontmatter 提取元信息，正文原样保留。"""
    text = path.read_text(encoding="utf-8-sig")
    title = path.stem
    project_id = ""
    body = text
    if text.startswith("---"):
        import re

        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if m:
            body = text[m.end() :]
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    if k in ("title", "论文标题"):
                        title = v.strip()
                    elif k in ("project_id",):
                        project_id = v.strip()
    return ParsedConversation(
        conversation_key=f"note:{path.name}",
        title=title,
        project_id=project_id,
        messages=[ParsedMessage(role="user", text=body.strip())],
        missing_resources=[],
    )
