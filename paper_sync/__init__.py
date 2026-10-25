"""paper_sync：论文知识库同步引擎。

私有数据（inbox/状态库/草稿/日志）保存在仓库外的数据目录，
只有通过人工审核（approve + publish）的清理版内容才会导出到公开仓库。

数据源适配：Source A = ChatGPT 官方数据导出；Source B = 单篇结构化笔记；
Source C = 预留的官方授权接口适配器基类（当前不存在这样的公开 API，
见 docs/paper-sync-limitations.md，不得虚构实时读取能力）。
"""

__version__ = "0.1.0"
