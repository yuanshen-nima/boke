# ChatGPT「论文阅读」单篇结构化导出提示词

在 ChatGPT 项目对话结束时，直接粘贴以下提示词，把输出保存为 `.json` 文件，
然后 `python -m paper_sync import-note 文件.json` 即可进入知识库流程。

---

请把我们在本对话中对这篇论文的全部讨论整理为单一 JSON 对象输出（不要额外解释文字）。
要求：只使用对话中真实出现的信息，禁止编造；不确定的字段填 null 或空数组；
每个实验数字都要保留来源；公式使用 LaTeX。Schema：

```json
{
  "paper_title": "论文英文标题",
  "authors": ["作者"],
  "year": 2024,
  "venue": "会议或期刊，未知填空串",
  "doi": "如 10.1007/xxx，未知填空串",
  "arxiv_id": "如 2304.06808，未知填空串",
  "paper_url": "官方地址",
  "github_url": "代码仓库",
  "summary": "3~5 句中文核心摘要",
  "background": "研究背景",
  "problem": "核心问题",
  "method": "方法原理，保留英文术语",
  "key_formulas": [{"latex": "...", "explanation": "中文解释"}],
  "contributions": ["创新贡献逐条"],
  "experiments": {
    "setup": "数据集与实验设置",
    "results": [{"dataset": "MOT17", "metrics": {"HOTA": 80.3}, "source": "paper 原文 / 你此前的分析 / 我的推测"}]
  },
  "limitations": ["论文不足"],
  "my_notes": ["我在对话中提出的个人观点与启发"],
  "unverified": ["对话中未能与原文核对、需要我人工确认的结论"],
  "source_conversation_id": "如果界面上能看到会话 ID 则填写，否则 null"
}
```

---

保存后进入 `python -m paper_sync publish` 流程前，请人工核对 `unverified` 与所有实验数字。
