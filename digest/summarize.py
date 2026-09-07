"""调用 OpenAI 兼容 API，把 extract.py 产出的对话素材归纳成博客文章。

配置来自 digest/config.json（OpenAI 兼容协议）：
{
  "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "api_key":  "xxxx",
  "model":    "glm-4.6",
  "temperature": 0.4
}
仅用标准库实现，无需安装依赖。
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent

# 发给模型前素材总字符上限（超出会截断）
MAX_MATERIAL_CHARS = 80_000

SYSTEM_PROMPT = """你是一位中文技术博客的主编。你收到的是博主某一天与多个 AI 编程助手（ZCode、Codex 等）的真实对话素材。
任务：把这些对话归纳成一篇可以直接发布在个人博客上的《AI 对话日报》。

要求：
1. 简体中文，Markdown 格式，篇幅 600~1500 字。
2. 按话题聚类组织（合并讨论同一主题的多个会话），不要逐会话流水账。
3. 每个话题讲清楚：博主在做什么、得出了什么结论或进展、还遗留什么问题。
4. 语气自然，用第一人称"我"，像博主本人在回顾一天的工作；不要出现"素材""对话记录显示"这类字眼。
5. 严禁出现文件绝对路径、API 密钥、密码、内网地址等敏感信息。项目名称可以保留，但不要大段引用原文。
6. 结构：开头 2~3 句引言；中间若干个 ## 小节；结尾一个"## 今日要点"小节，用 3~5 条列表总结。
7. 只输出正文 Markdown，不要输出 frontmatter，不要使用一级标题 #（标题由系统生成），从小节标题 ## 开始。"""


def load_config() -> dict:
    cfg_path = DIGEST_DIR / "config.json"
    if not cfg_path.exists():
        raise RuntimeError(
            "缺少 digest/config.json：请复制 digest/config.example.json 为 digest/config.json 并填入 API 配置"
        )
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("base_url", "api_key", "model"):
        if not cfg.get(key) or str(cfg[key]).startswith("在这里"):
            raise RuntimeError(f"digest/config.json 的 {key} 尚未配置")
    return cfg


def _chat_once(cfg: dict, messages: list) -> str:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": cfg["model"],
            "messages": messages,
            "temperature": cfg.get("temperature", 0.4),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError("模型返回了空内容")
    return content.strip()


def chat(cfg: dict, messages: list, retries: int = 1) -> str:
    last_err = None
    for _ in range(retries + 1):
        try:
            return _chat_once(cfg, messages)
        except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError) as err:
            last_err = err
    raise RuntimeError(f"LLM API 调用失败（已重试 {retries} 次）：{last_err}")


def compact_material(material: dict) -> str:
    lines = []
    for s in material["sessions"]:
        lines.append(
            f"## 会话（{s['source']} · 项目 {s['project']} · {s['time']} 开始）主题：{s['title']}"
        )
        for t in s["turns"]:
            lines.append(f"用户：{t['q']}")
            for a in t["a"]:
                lines.append(f"助手：{a}")
        lines.append("")
    text = "\n".join(lines)
    if len(text) > MAX_MATERIAL_CHARS:
        text = text[:MAX_MATERIAL_CHARS] + "\n…(素材过长，其余已截断)"
    return text


def summarize(material: dict, cfg: dict) -> str:
    prompt = (
        f"以下是博主 {material['date']} 这一天与 AI 助手的全部对话素材"
        f"（共 {len(material['sessions'])} 个会话）。请归纳成博客文章。\n\n"
        f"{compact_material(material)}"
    )
    return chat(
        cfg,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
