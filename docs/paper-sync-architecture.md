# 论文知识库同步系统 · 架构

## 数据流

```
ChatGPT 官方导出 (zip/conversations.json)  ─┐
                                            ├─→ inbox/（仓库外私有目录）
单篇结构化笔记 (json/md)                  ─┘        │
                                                 ▼
                                    paper_sync sync（幂等，sha256 去重）
                                                 │
                          识别（DOI > arXiv > 标题 > 人工映射）
                                                 │
                       归纳（DeepSeek 结构化 JSON / 离线确定性提取）
                                                 │  发送前强制脱敏
                                                 ▼
                          私有草稿 paper_sync_data/papers/<id>/
                            meta.json + draft.md（machine/human 双区）
                                                 │
                            人工审核：approve（明确的人工标记）
                                                 │
                            publish：安全扫描 → 导出 src/content/papers/
                                                 │
                                    git push → Cloudflare 自动构建
```

## 模块职责（paper_sync/）

| 模块 | 职责 |
|---|---|
| `config.py` | 仓库外数据目录、私有配置、复用 digest 的 DeepSeek 配置、日志 |
| `sources.py` | Source A（ChatGPT 导出：zip/单文件/分卷/截断恢复）、Source B（笔记 json/md）、SourceAdapter 接口（Source C 预留） |
| `identity.py` | 论文同一性：DOI > arXiv > 规范化标题哈希；标识符从文本提取 |
| `normalize.py` | 归纳层：LLM 结构化提取（schema 校验、有限重试）或离线确定性提取；发送前脱敏 |
| `render.py` | 草稿渲染/合并（machine/human 双区、冲突差异报告）、公开版渲染 |
| `security.py` | 桥接 digest/security.py 的确定性扫描与脱敏（单一实现，避免模式漂移） |
| `state.py` | SQLite 同步状态（papers / sources / events 三表） |
| `pipeline.py` | 编排：sync / approve / publish；进程锁；git 推送（含代理回退） |
| `lock.py` | 跨进程锁（残留锁 6 小时自动清理） |

## 隐私边界

- 私有数据目录默认 `<仓库>/../paper_sync_data/`（可用 `PAPER_SYNC_DATA_DIR` 覆盖），内含 inbox、state.sqlite、草稿、日志、配置
- 草稿（未审核内容）只存在于私有目录；公开仓库只有审核通过并清理后的 `src/content/papers/*.md`
- `digest/config.json`（含 API key）与私有目录均被 .gitignore 排除
