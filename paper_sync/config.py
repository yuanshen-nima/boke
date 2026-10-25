"""路径、私有配置与日志。私有数据目录在公开仓库之外。"""

import json
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# 私有数据目录：默认仓库外 ../paper_sync_data，可用环境变量覆盖
DATA_DIR = Path(
    os.environ.get("PAPER_SYNC_DATA_DIR", str(REPO_ROOT.parent / "paper_sync_data"))
)

INBOX_DIR = DATA_DIR / "inbox"
PAPERS_DIR = DATA_DIR / "papers"  # 私有草稿（每篇论文一个子目录）
STATE_DB = DATA_DIR / "state.sqlite"
LOG_DIR = DATA_DIR / "logs"
LOCK_FILE = DATA_DIR / ".lock"
MANUAL_MAP_FILE = DATA_DIR / "manual_map.json"  # {conversation_key|source_key: paper_id}
CONV_LIST_FILE = DATA_DIR / "conversation_ids.txt"  # 用户维护的「论文阅读」对话 ID 清单

PUBLIC_PAPERS_DIR = Path(
    os.environ.get("PAPER_SYNC_PUBLIC_DIR", str(REPO_ROOT / "src" / "content" / "papers"))
)
DIGEST_CONFIG = REPO_ROOT / "digest" / "config.json"  # 复用已有 DeepSeek 配置


def ensure_dirs() -> None:
    for d in (DATA_DIR, INBOX_DIR, PAPERS_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_private_config() -> dict:
    """私有配置（数据目录内，不进仓库）。"""
    cfg_path = DATA_DIR / "config.json"
    defaults = {
        "project_ids": [],  # ChatGPT「论文阅读」项目的 project_id（导出数据含此字段时使用）
        "ai": {"enabled": True, "max_chars": 60000},  # 关闭后使用离线确定性提取
    }
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        for k, v in cfg.items():
            defaults[k] = v
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def load_deepseek_config() -> dict:
    """复用每日日报的 DeepSeek 配置（base_url/api_key/model），不新建密钥存储。"""
    cfg = json.loads(DIGEST_CONFIG.read_text(encoding="utf-8"))
    for key in ("base_url", "api_key", "model"):
        if not cfg.get(key):
            raise RuntimeError(f"digest/config.json 缺少 {key}，无法调用 AI 归纳")
    return cfg


def load_conversation_allowlist() -> set[str]:
    if not CONV_LIST_FILE.exists():
        return set()
    return {
        line.strip()
        for line in CONV_LIST_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def load_manual_map() -> dict:
    if not MANUAL_MAP_FILE.exists():
        return {}
    try:
        return json.loads(MANUAL_MAP_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_logger() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("paper_sync")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "paper-sync.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger
