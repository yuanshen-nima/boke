# 我的技术博客

基于 [Astro](https://astro.build/) + [Fuwari](https://github.com/saicaca/fuwari) 主题的个人技术博客，部署在 Cloudflare Pages，全流程免费。

内置功能：明暗主题、全文搜索（Pagefind）、文章目录、标签/分类/归档、RSS、代码块增强（高亮/行号/折叠/复制）、数学公式、字数统计与阅读时长、Giscus 评论（可选）、SEO（sitemap / OG / JSON-LD）。

## 快速开始

```bash
pnpm install   # 安装依赖（需要 Node.js 20+ 和 pnpm）
pnpm dev       # 本地开发，http://localhost:4321 实时预览
pnpm build     # 构建产物到 dist/（含搜索索引）
```

## 日常写作

```bash
pnpm new-post my-post-name   # 在 src/content/posts/ 生成新文章模板
pnpm dev                     # 边写边预览
git push                     # 发布：Cloudflare 自动构建上线
```

文章是 Markdown 文件，头部 frontmatter 示例：

```markdown
---
title: 文章标题
published: 2026-09-06
description: 一句话摘要，会显示在列表和搜索里
tags: [Astro, 随笔]
category: 技术笔记
draft: false        # true 则不发布
---

正文从这里开始……
```

更多排版语法（提示块、GitHub 卡片、公式、折叠代码块）见《Markdown 写作与排版示例》一文。

## 常用定制位置

| 想改什么 | 改哪里 |
| -------- | ------ |
| 站点名称、简介、语言、主题色 | `src/config.ts` → `siteConfig` |
| 导航栏链接 | `src/config.ts` → `navBarConfig` |
| 头像、昵称、个人简介、社交链接 | `src/config.ts` → `profileConfig` |
| 头像/横幅图片 | `src/assets/images/` |
| 部署域名 | `astro.config.mjs` → `site` |
| 文章 | `src/content/posts/` |
| 关于页面 | `src/content/spec/about.md` |
| 中文界面文案 | `src/i18n/languages/zh_CN.ts` |

## 评论系统（Waline，支持图片上传）

评论用 [Waline](https://waline.js.org/)：支持匿名/昵称邮箱评论、粘贴与拖拽上传图片、表情包，自带垃圾评论管理后台。前端组件在 `src/components/comment/Waline.svelte`，配置在 `src/config.ts` → `commentConfig`（`walineServerURL` 填后端地址后评论区自动显示）。

### 后端部署（一次性，约 15 分钟）

1. 注册 [LeanCloud 国际版](https://console.leancloud.app/)（邮箱即可），创建应用（开发版免费），进入 设置 → 应用凭证，记下 **AppID / AppKey / 服务器地址**
2. 登录 [Vercel](https://vercel.com/)（用 GitHub 账号），打开 Waline 官方一键部署模板 <https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fwalinejs%2Fwaline%2Ftree%2Fmain%2Fexample>，环境变量填：
   - `LEAN_ID` = AppID
   - `LEAN_KEY` = AppKey
   - `LEAN_SERVER` = 服务器地址
3. Deploy 完成后得到 `xxx.vercel.app` 地址，填入 `src/config.ts` → `commentConfig.walineServerURL` 并推送
4. 评论管理后台：`https://xxx.vercel.app/ui`（首次注册的账号即管理员）

> 图片上传默认以 base64 存入数据库（免费额度够用）；后续可到 Waline 后台 → 设置 → 图片上传 配置七牛/Cloudinary 图床。
> 想切回 GitHub Discussions 评论：`commentConfig.provider` 改为 `"giscus"` 并把 `giscusConfig.enable` 改为 `true`。

## 首页精选与热门榜

- **精选文章**：文章 frontmatter 加一行 `pinned: true`，该文会出现在首页顶部「精选文章」区，并从下方分页列表移除（不重复展示）；删除该行即取消精选
- **文章阅读量**：文章页的阅读量由[不蒜子](https://busuanzi.ibruce.info/)统计，脚本加载失败时自动隐藏
- **热门文章榜**（侧栏，可选）：构建时从 Cloudflare Web Analytics 取近 30 天访问最多的 5 篇文章。启用步骤：
  1. Cloudflare 仪表板 → 该 Pages 项目 → Web Analytics 开启统计
  2. 创建 API Token（权限 Account → Web Analytics → Read），记下 Account ID 和站点 siteTag（统计代码 URL 中的参数）
  3. 在 Pages 项目 Settings → 环境变量（构建时）添加：
     - `CF_WEBANALYTICS_ACCOUNT_ID`
     - `CF_WEBANALYTICS_TOKEN`
     - `CF_WEBANALYTICS_SITE_TAG`
  4. 重新部署后侧栏出现「热门文章」；未配置时该模块自动隐藏，不影响构建

## 部署到 Cloudflare Pages

1. 把本项目推送到 GitHub 仓库
2. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) → Workers & Pages → Create → Pages → **Connect to Git**，选择该仓库
3. 构建设置：框架预设选 **Astro**（构建命令 `npm run build`，输出目录 `dist`）
4. 点 Save and Deploy，约一分钟后得到 `项目名.pages.dev` 免费域名
5. 把该域名填回 `astro.config.mjs` 的 `site` 并推送一次

之后每次 `git push` 都会自动构建发布。绑定自定义域名：Pages 项目 → Custom domains → 添加域名（域名 DNS 托管在 Cloudflare 时自动配置）。

## 致谢

- [Fuwari](https://github.com/saicaca/fuwari) — saicaca 开源的博客主题（MIT License）

## 每日对话日报（自动化）

每天 23:30 自动提取当天 **ZCode** 与 **Codex（ChatGPT）** 的对话，经大模型归纳成《AI 对话日报》，**通过两道安全关卡后自动发布**，否则降级为草稿。

### 发布安全策略

1. **关卡一（确定性扫描）**：`digest/security.py` 用正则扫描成稿中的 API 密钥、数据库连接串、私钥、绝对路径、内网 IP、邮箱等，命中即降级草稿。提示词约束不能替代确定性扫描
2. **关卡二（LLM 复审）**：另一个提示词以审核员身份复审语义级风险（未公开科研数据、项目代号等），未通过同样只存草稿
3. **项目黑名单**：`digest/config.json` → `security.blocked_projects` 里列出的项目目录，其会话整体不进入素材（如 `["codex"]` 可排除全部科研项目对话）
4. **敏感词**：`security.sensitive_keywords` 里出现即转草稿
5. 人工确认安全后：把文章 frontmatter 的 `draft` 改为 `false` 推送，或用 `python digest/run.py --date X --force` 强制发布

### 数据备份

- **文章**：GitHub 仓库即备份（每次发布都有提交历史）
- **评论**：`digest/backup.py` 每日把 Waline 全部评论数据（Neon 数据库）dump 到 `digest/work/backup/`，保留最近 30 份；手动执行：`python digest/backup.py`
- 恢复：Neon 控制台可重置数据库，再用备份 JSON 导回

- 手动运行：`python digest/run.py`（`--date YYYY-MM-DD` 补某天；`--no-llm` 不调 API 出简版；`--no-push` 只生成不发布）
- API 配置：`digest/config.json`（OpenAI 兼容协议，base_url / model / api_key，已被 gitignore，密钥不进仓库）
- 计划任务：双击 `digest/install-task.bat` 注册（默认 23:30，可传参数改时间如 `install-task.bat 22:00`）；删除：`schtasks /Delete /TN BlogDailyDigest /F`
- 日志：`digest/work/run.log`；素材快照：`digest/work/material-日期.json`
- 前提：到点时电脑开机且已登录 Windows；错过则当天不生成，事后可 `--date` 补发
