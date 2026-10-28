"""确定性安全扫描与发布拦截。

原则：LLM 的提示词约束不能替代确定性的密钥扫描和隐私检查。
publish 流程中，文章必须先通过本模块扫描（以及可选的 LLM 复审）才会发布，
否则一律降级为草稿（draft: true），等待人工审核。
"""

import json
import re
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent

# (正则, 名称, 类别)  类别: secret=凭据泄露 privacy=隐私/内网信息
SCAN_PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{16,}", "API 密钥（sk- 开头）", "secret"),
    (r"gh[pousr]_[A-Za-z0-9]{30,}", "GitHub Token", "secret"),
    (r"AKIA[0-9A-Z]{16}", "AWS AccessKey", "secret"),
    (r"npg_[A-Za-z0-9_]{16,}", "Neon 数据库密码", "secret"),
    (r"glpat-[A-Za-z0-9_-]{16,}", "GitLab Token", "secret"),
    (r"xox[bpars]-[A-Za-z0-9-]{10,}", "Slack Token", "secret"),
    (r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", "JWT", "secret"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥", "secret"),
    (r"(?i)(api[_-]?key|apikey|secret|passwd|password|pwd|access[_-]?token)\s*[=:：]\s*[\"']?[^\s\"']{12,}", "凭据赋值", "secret"),
    (r"(?i)(postgresql|postgres|mysql|mongodb)(\+srv)?://[^\s\"']+", "数据库连接串", "secret"),
    (r"https?://[^\s/:@\"']+:[^@\s\"']+@", "URL 内嵌凭据", "secret"),
    (r"(?<![A-Za-z0-9])[A-Za-z]:\\(?![|<>])[^\s\"'）)】，。]{3,}", "Windows 绝对路径", "privacy"),
    (r"(?<![A-Za-z0-9])/(?:home|Users|root)/[^\s\"'）)】，。]{3,}", "Unix 绝对路径", "privacy"),
    (r"(?<![A-Za-z0-9])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![A-Za-z0-9.])", "内网 IP", "privacy"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "邮箱地址", "privacy"),
]


def _mask(sample: str) -> str:
    sample = " ".join(sample.split())
    if len(sample) <= 8:
        return sample[:2] + "***"
    return sample[:6] + "***(" + str(len(sample)) + " 字符)"


def scrub(text: str) -> str:
    """把素材中疑似密钥的字符串替换为占位符（发送给第三方模型前的强制脱敏）。"""
    for pat, _name, kind in SCAN_PATTERNS:
        if kind != "secret":
            continue
        text = re.sub(pat, "[已脱敏]", text)
    return text


def load_security_config() -> dict:
    """读取 config.json 的 security 段，缺省全部放行。"""
    cfg_path = DIGEST_DIR / "config.json"
    defaults = {
        "blocked_projects": [],  # 这些项目目录的会话整体跳过，不进入素材
        "sensitive_keywords": [],  # 归纳结果出现这些词即转草稿（如未公开的项目代号）
    }
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        sec = cfg.get("security") or {}
        defaults.update({k: v for k, v in sec.items() if k in defaults})
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def filter_sessions(sessions: list, sec_cfg: dict) -> tuple[list, list]:
    """按项目黑名单过滤素材会话，返回 (保留的会话, 被拦截的描述)。"""
    blocked = [p.lower() for p in sec_cfg.get("blocked_projects", [])]
    kept, dropped = [], []
    for s in sessions:
        project = (s.get("project") or "").lower()
        if project and project in blocked:
            dropped.append(f"{s.get('source', '?')} 项目 {s.get('project')}（{s.get('title', '')[:20]}）")
        else:
            kept.append(s)
    return kept, dropped


def scan(text: str, extra_keywords: list | None = None) -> list[dict]:
    """对最终文章做确定性扫描，返回命中列表（样例已脱敏）。"""
    findings = []
    for pattern, name, kind in SCAN_PATTERNS:
        m = re.search(pattern, text)
        if m:
            findings.append({"kind": kind, "name": name, "sample": _mask(m.group(0))})
    for kw in extra_keywords or []:
        if kw and kw.lower() in text.lower():
            findings.append({"kind": "keyword", "name": f"敏感词：{kw}", "sample": kw})
    return findings
