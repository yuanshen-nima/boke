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
import re
import urllib.error
import urllib.request
from pathlib import Path

DIGEST_DIR = Path(__file__).resolve().parent

# 发给模型前素材总字符上限（超出会截断）
MAX_MATERIAL_CHARS = 80_000

SYSTEM_PROMPT = """你是一位中文技术博客的主编。你收到的是博主某一天与多个 AI 编程助手（ZCode、Codex 等）的真实对话素材。
任务：把这些对话归纳成一篇重点突出的《AI 对话日报》，直接发布在个人博客上。

核心原则：日报的价值在于"重点"，不在于"全面"。读者只想知道今天最重要的事是什么、得出了什么结论、还剩什么问题。宁可短而锋利，不要长而平铺。

写作要求：
1. 简体中文，Markdown，总长 400~900 字。
2. 开头必须是"## 今日重点"小节：用 1~3 条加粗列表给出当天最重要的结论或进展，每条一句话说清"事情 + 结果/意义"。这是全文最重要的部分。
3. 之后按重要性递减组织正文小节（## 标题）：最重要的话题写足细节（做了什么、关键结论、数字证据）；次要话题一段带过；琐碎话题直接舍弃。
4. 大刀阔斧舍弃：环境配置、报错排查、反复重试、无结论的讨论、纯过程性内容，一律不写——除非它们产生了最终结论或教训。
5. 每个小节优先写结论和决策，而不是过程：做了什么决定、为什么、接下来干什么。
6. 语气自然，第一人称"我"，像博主本人在回顾一天；不要出现"素材""对话记录显示"这类字眼。
7. 严禁出现文件绝对路径、API 密钥、密码、内网地址等敏感信息；不要大段引用原文。
8. 如果当天确有遗留，在结尾加"## 待办与疑问"小节（3 条以内）；没有则整个小节省略。
9. 只输出正文 Markdown，不要输出 frontmatter，不要使用一级标题 #（标题由系统生成），从"## 今日重点"开始。"""


def load_config() -> dict:
    cfg_path = DIGEST_DIR / "config.json"
    if not cfg_path.exists():
        raise RuntimeError(
            "缺少 digest/config.json：请复制 digest/config.example.json 为 digest/config.json 并填入 API 配置"
        )
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
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


def chat(cfg: dict, messages: list, retries: int = 2, backoff: int = 10) -> str:
    last_err = None
    for i in range(retries + 1):
        try:
            return _chat_once(cfg, messages)
        except Exception as err:
            # 网络类异常种类繁多（URLError/超时/IncompleteRead 等），统一重试
            last_err = err
            if i < retries:
                import time

                time.sleep(backoff * (i + 1))
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


REVIEW_PROMPT = """你是一名严格的内容安全审核员。下面是一篇即将发布到博客私密专区（配有密码锁保护）的《AI 对话日报》。
请逐句审查是否存在以下高危风险：
1. API 密钥、token、密码、数据库连接串等凭据（包括被部分遮掩的）
2. 本地文件绝对路径（如 C:\\Users\\...）、内网 IP、内网服务地址与端口
3. 他人隐私、真实姓名、私人账号与通讯方式

只输出 JSON，格式：{"safe": true/false, "reasons": ["原因1", ...]}。没有上述高危风险则 reasons 为空数组。"""


def safety_review(article: str, cfg: dict) -> dict:
    """LLM 复审（第二道关）。返回 {"safe": bool, "reasons": [...]}，解析失败按不安全处理。"""
    raw = chat(
        cfg,
        [
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": article},
        ],
        retries=1,
    )
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0))
        return {"safe": bool(data.get("safe")), "reasons": list(data.get("reasons") or [])}
    except (AttributeError, ValueError, TypeError):
        return {"safe": False, "reasons": ["安全复审输出无法解析，按不安全处理"]}
