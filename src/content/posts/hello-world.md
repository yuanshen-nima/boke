---
title: 我的博客搭建记：Astro + Fuwari + Cloudflare Pages
published: 2026-09-06
description: 从零到上线，记录这个博客的技术选型和搭建过程，全部免费。
tags: [博客, Astro, Cloudflare]
category: 随笔
draft: false
---

欢迎来到我的博客！这是第一篇文章，记录一下这个站点的技术选型和搭建过程。

## 技术选型

| 环节 | 选择 | 理由 |
| ---- | ---- | ---- |
| 框架 | [Astro](https://astro.build/) | 内容型网站最优解，默认零 JS、加载快、SEO 好 |
| 主题 | [Fuwari](https://github.com/saicaca/fuwari) | 颜值高、功能全、中文友好 |
| 写作 | Markdown | 纯文本、版本可控、专注内容 |
| 部署 | [Cloudflare Pages](https://pages.cloudflare.com/) | 免费、国内访问速度好、push 自动发布 |
| 评论 | [Giscus](https://giscus.app/zh-CN) | 基于 GitHub Discussions，免费无广告 |

## 它是如何工作的

整个博客是一个**静态站点**：写作时只关心 Markdown 文件，构建时 Astro 把它们渲染成纯 HTML 页面。

:::note
静态站点没有服务器、没有数据库，访问速度只受 CDN 影响，也几乎没有被攻击的面。
:::

发布流程只有三步：

1. 在 `src/content/posts/` 下新建一篇 `.md` 文件
2. 本地运行 `pnpm dev` 实时预览
3. `git push` 之后，Cloudflare 自动构建并上线，约一分钟后全网可见

## 内置了哪些功能

- 明暗双主题，跟随系统也可手动切换
- 全文搜索（构建时生成静态索引，无需后端）
- 文章目录、标签、分类、归档
- 代码块语法高亮、行号、折叠、一键复制
- RSS 订阅与 sitemap
- 字数统计与阅读时长估算
- 数学公式（KaTeX）支持

:::tip
想看看各种排版效果，可以阅读下一篇《Markdown 写作与排版示例》。
:::

## 接下来

把占位的站点名、作者信息、头像换成自己的，配置好评论系统，然后开始安心写作。
