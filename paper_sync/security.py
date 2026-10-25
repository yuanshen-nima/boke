"""安全扫描桥接：复用每日日报已验证的确定性扫描器（digest/security.py）。"""

from pathlib import Path
import sys

_DIGEST_DIR = Path(__file__).resolve().parents[1] / "digest"
if str(_DIGEST_DIR) not in sys.path:
    sys.path.insert(0, str(_DIGEST_DIR))

from security import scan, scrub  # noqa: E402,F401  noqa: 复用单一实现，避免模式漂移
