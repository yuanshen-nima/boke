"""论文同一性判定：DOI > arXiv ID > 规范化标题 > 人工映射。

paper_id 是全局唯一键。匹配不确定（无标识符且标题近似）时返回 needs_review 标记，
绝不使用对话标题或文件名直接断言同一性。
"""

import hashlib
import re
import unicodedata

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>，。；]+", re.IGNORECASE)
ARXIV_URL_RE = re.compile(r"\barxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(v\d+)?", re.IGNORECASE)


def normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi\s*[:：]\s*", "", doi)
    return doi.rstrip(".,;）)")


def normalize_arxiv(aid: str) -> str:
    aid = aid.strip().lower()
    return re.sub(r"v\d+$", "", aid)


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).lower()
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)  # 去标点（保留中英文与数字）
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_hash(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()[:16]


def make_paper_id(
    *, doi: str = "", arxiv: str = "", title: str = ""
) -> tuple[str, bool]:
    """返回 (paper_id, confident)。无标识符时用标题哈希并视为需人工确认。"""
    if doi:
        return f"doi:{normalize_doi(doi)}", True
    if arxiv:
        return f"arxiv:{normalize_arxiv(arxiv)}", True
    if title.strip():
        return f"title:{title_hash(title)}", False  # 仅标题：可信度低，需人工确认
    return "", False


def find_identifiers(text: str) -> tuple[str, str]:
    """从自由文本中提取 DOI / arXiv ID。"""
    doi = ""
    m = DOI_RE.search(text)
    if m:
        doi = normalize_doi(m.group(0))
    arxiv = ""
    m = ARXIV_URL_RE.search(text)
    if m:
        arxiv = normalize_arxiv(m.group(1))
    return doi, arxiv
