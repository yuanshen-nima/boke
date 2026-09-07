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

## 开启评论（Giscus，可选）

1. 博客的 GitHub 仓库需要是**公开**仓库
2. 仓库 Settings → General → Features 勾选 **Discussions**
3. 安装 [giscus App](https://github.com/apps/giscus)
4. 打开 [giscus.app/zh-CN](https://giscus.app/zh-CN)，填入仓库名，选择映射方式 `pathname`、分类 `Announcements`，页面会生成 `repo` / `repoId` / `category` / `categoryId` 四个参数
5. 填入 `src/config.ts` → `giscusConfig`，并把 `enable` 改为 `true`

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

每天 23:30 自动提取当天 **ZCode** 与 **Codex（ChatGPT）** 的对话，经大模型归纳成《AI 对话日报》自动发布。

- 手动运行：`python digest/run.py`（`--date YYYY-MM-DD` 补某天；`--no-llm` 不调 API 出简版；`--no-push` 只生成不发布）
- API 配置：`digest/config.json`（OpenAI 兼容协议，base_url / model / api_key，已被 gitignore，密钥不进仓库）
- 计划任务：双击 `digest/install-task.bat` 注册（默认 23:30，可传参数改时间如 `install-task.bat 22:00`）；删除：`schtasks /Delete /TN BlogDailyDigest /F`
- 日志：`digest/work/run.log`；素材快照：`digest/work/material-日期.json`
- 前提：到点时电脑开机且已登录 Windows；错过则当天不生成，事后可 `--date` 补发
