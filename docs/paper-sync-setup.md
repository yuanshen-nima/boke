# 论文知识库 · 安装与环境配置

## 前置条件（博客环境已具备）

- Python（Anaconda 3.14，`D:\develop_tool\anaconda3\python.exe`）
- Node.js + pnpm（博客构建用）
- DeepSeek API key：已配置在 `digest/config.json`（paper_sync 直接复用，不重复存放密钥）

## 初始化

```bash
# 1. 数据目录会在首次运行时自动创建（默认 仓库外 ../paper_sync_data/）
python -m paper_sync sync          # inbox 为空，直接通过

# 2. （可选）配置 ChatGPT 项目归属
#    编辑 <数据目录>/config.json：
{
  "project_ids": ["在导出数据中出现的 project_id"],
  "ai": { "enabled": true, "max_chars": 60000 }
}
#    或维护对话白名单 <数据目录>/conversation_ids.txt（每行一个对话 ID）

# 3. （可选）同一文件/对话对应已有论文的人工映射
#    <数据目录>/manual_map.json：{ "note:xxx.md": "doi:10.xxxx/yyyy" }

# 4. 测试
python -m paper_sync test          # 离线测试套件，19 个用例
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PAPER_SYNC_DATA_DIR` | `<仓库>/../paper_sync_data` | 私有数据目录位置 |
| `PAPER_SYNC_PUBLIC_DIR` | `<仓库>/src/content/papers` | 发布目标（测试用） |
| `PAPER_SYNC_NO_GIT` | 未设置 | 设为 1 时发布只写文件不执行 git（测试用） |

## AI 开关

`<数据目录>/config.json` 的 `ai.enabled: false` 或命令行 `--offline`：
不调用任何外部 API，使用确定性提取（仅标识符/标题/结构化字段），适合离线与测试。
