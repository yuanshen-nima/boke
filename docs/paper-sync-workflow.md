# 论文知识库 · 日常工作流

## 场景 B：新增一篇论文（推荐日常方式）

1. 在 ChatGPT「论文阅读」项目对话结束时，让 AI 输出结构化总结并保存为 `.json`（提示词见 `docs/chatgpt-paper-export-prompt.md`）
2. 导入并同步：
   ```bash
   python -m paper_sync import-note D:\path\to\note.json
   ```
   （传目录可批量；文件也可以直接丢进 inbox 后执行 `python -m paper_sync sync`）
3. 检查草稿：`python -m paper_sync list --status draft` → `show <paper_id>`
   草稿在 `<数据目录>/papers/<paper_id>/draft.md`，人工笔记写在 human 区（同步永不覆盖）
4. 核验公式与实验数字后审核发布：
   ```bash
   python -m paper_sync approve <paper_id>
   python -m paper_sync publish <paper_id>
   ```
5. push 自动触发 Cloudflare 构建，约 1 分钟后 `/papers/` 可见

## 场景 A：历史批量导入

1. ChatGPT 网页版 → Settings → Data controls → **Export data**（邮件附 zip）
2. 解压或直接：
   ```bash
   python -m paper_sync import-export D:\path\to\conversations.json
   # 或整个 zip；支持 conversations-part1.json 等分卷
   ```
3. 归属确认：无 project_id 字段且未配置白名单的会话进入 `needs_review`，不会猜测。
   把确认属于「论文阅读」的对话 ID 加入 `<数据目录>/conversation_ids.txt` 后重新 `sync`
4. 同一论文的多次讨论自动合并（DOI/arXiv/标题识别），冲突字段生成 `changes-*.md` 差异报告

## 场景 C/D：幂等与更新

- 同一批输入重复执行：哈希相同直接跳过，不产生重复论文或空提交
- 同一论文新增讨论：合并进同一条目；人工编辑区原样保留

## 场景 E：发布安全

- `publish` 前有确定性安全扫描（密钥/连接串/路径/内网 IP/邮箱），命中即拒绝（`--force` 可越权，慎用）
- 未 approve 的论文 publish 会直接拒绝；draft 永不进入公开仓库与站点构建

## 定时同步（可选）

```bash
schtasks /Create /F /TN "PaperSync" /SC DAILY /ST 21:00 /TR "\"<仓库>\paper_sync\install-paper-task.bat\""
```
`install-paper-task.bat` 只同步与备份，**不自动发布**；与 23:30 的日报任务错峰。
