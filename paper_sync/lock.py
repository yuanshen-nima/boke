"""进程锁：防止多个同步进程同时修改状态。锁超过 LOCK_STALE_HOURS 视为残留。"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

LOCK_STALE_HOURS = 6


class SyncLock:
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self._acquired = False

    def acquire(self) -> None:
        if self.lock_file.exists():
            info = {}
            try:
                info = json.loads(self.lock_file.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                pass
            mtime = self.lock_file.stat().st_mtime
            stale = datetime.now() - datetime.fromtimestamp(mtime) > timedelta(
                hours=LOCK_STALE_HOURS
            )
            if stale:
                self.lock_file.unlink(missing_ok=True)
            else:
                raise RuntimeError(
                    f"另一个同步进程可能正在运行（锁 {self.lock_file}，"
                    f"创建于 {info.get('started', '?')}）。确认无进程后可手动删除该文件。"
                )
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(
            json.dumps({"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}),
            encoding="utf-8",
        )
        self._acquired = True

    def release(self) -> None:
        if self._acquired:
            self.lock_file.unlink(missing_ok=True)
            self._acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
