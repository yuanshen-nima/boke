"""本地 HTTP 接收服务：接收浏览器油猴脚本推送的 ChatGPT 对话，写入 inbox 并触发同步。

基于 Python 标准库 http.server 实现，零外部依赖。
启动命令：
  python -m paper_sync serve --port 8765
"""

from __future__ import annotations

import json
import logging
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config
from .pipeline import PaperSync

MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50MB 上限


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return cleaned[:48] or "unnamed"


def _llm_ready() -> bool:
    """检测 AI 归纳配置是否可用；不可用时自动降级为离线确定性提取，避免同步整体失败。"""
    try:
        if not config.load_private_config().get("ai", {}).get("enabled", True):
            return False
        cfg = config.load_deepseek_config()
        return bool(cfg.get("base_url") and cfg.get("api_key") and cfg.get("model"))
    except Exception:
        return False


class InboxRequestHandler(BaseHTTPRequestHandler):
    auto_sync: bool = True
    server_version = "PaperSyncInbox/1.0"

    def log_message(self, format: str, *args) -> None:
        # 重定向请求日志到 logger
        logging.getLogger("paper_sync.server").info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        try:
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(raw)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            logging.getLogger("paper_sync.server").info(
                "客户端已提前断开连接（%s: %s），本地数据已安全写入", type(e).__name__, e
            )

    def do_OPTIONS(self) -> None:
        """处理浏览器跨域预检请求。"""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """健康检查或状态查询。"""
        if self.path in ("/", "/health", "/ping"):
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "paper_sync_inbox",
                    "inbox_dir": str(config.INBOX_DIR),
                    "auto_sync": self.auto_sync,
                },
            )
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not Found"})

    def do_POST(self) -> None:
        """接收网页端推送的会话或笔记 JSON。"""
        if self.path not in ("/api/inbox", "/inbox", "/api/sync"):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Endpoint not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid Content-Length"})
            return

        if content_length > MAX_PAYLOAD_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "Payload too large"})
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"Invalid JSON body: {e}"})
            return

        if not isinstance(data, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON root must be an object"})
            return

        # 确保 inbox 目录存在
        config.ensure_dirs()
        cid = data.get("conversation_id") or data.get("id") or data.get("paper_title") or "chat"
        title = data.get("title") or data.get("paper_title") or ""
        ts = int(time.time())
        file_stem = f"chatgpt-web-{_safe_name(str(cid))}-{ts}"
        target_path = config.INBOX_DIR / f"{file_stem}.json"

        try:
            target_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"Failed to write file: {e}"})
            return

        result = {
            "ok": True,
            "message": "已成功保存到 inbox 并已启动后台同步处理",
            "file": target_path.name,
            "conversation_id": cid,
            "title": title,
            "sync_status": "success",
        }

        self._send_json(HTTPStatus.OK, result)

        # 异步触发同步管线，避免大文件/大模型解析耗时导致浏览器端请求超时或提前断开
        if self.auto_sync:
            def _background_sync():
                try:
                    ps = PaperSync(offline=not _llm_ready())
                    sync_ret = ps.sync()
                    ps.close()
                    logging.getLogger("paper_sync.server").info(
                        "后台同步完成: %s (返回码: %d)", target_path.name, sync_ret
                    )
                except Exception as e:
                    logging.getLogger("paper_sync.server").error("Auto sync failed: %s", e)

            import threading
            threading.Thread(target=_background_sync, daemon=True).start()


def run_server(host: str = "127.0.0.1", port: int = 8765, auto_sync: bool = True) -> None:
    config.ensure_dirs()
    log = config.get_logger()
    server_addr = (host, port)
    handler_class = InboxRequestHandler
    handler_class.auto_sync = auto_sync

    httpd = ThreadingHTTPServer(server_addr, handler_class)
    log.info("PaperSync 本地接收服务已启动: http://%s:%d", host, port)
    log.info("油猴脚本数据接收端点: http://%s:%d/api/inbox", host, port)
    log.info("按 Ctrl+C 停止服务")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("正在停止服务...")
    finally:
        httpd.server_close()
        log.info("服务已停止")
