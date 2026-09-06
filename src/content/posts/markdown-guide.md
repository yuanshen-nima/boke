---
title: Markdown 写作与排版示例
published: 2026-09-06
description: 一篇覆盖常用语法的示例文章：代码块、表格、公式、提示块、GitHub 卡片，写作时可以随时回来抄。
tags: [Markdown, 写作]
category: 博客使用指南
draft: false
---

这篇是写作速查：把博客支持的常用 Markdown 语法都演示一遍，写文章时可以随时回来抄。

## 基础排版

行内元素：**加粗**、_斜体_、~~删除线~~、`行内代码`，还有[链接](https://astro.build)。

> 引用块：好的写作是不断删减的艺术。

列表也自然支持：

1. 有序列表项
2. 第二项
3. 第三项

## 代码块

代码块由 [Expressive Code](https://expressivecode.com/) 渲染，支持语法高亮、行号、语言徽标和一键复制。

```ts title="src/utils/date-utils.ts" ins={2} del={5}
// 新写法：正确处理时区
export function formatDateToYYYYMMDD(date: Date): string {
	return date.toISOString().slice(0, 10);
}

// 旧写法：有跨时区偏移问题（已废弃）
function badFormat(date: Date): string {
	return date.toLocaleDateString();
}
```

```js collapse={1-3}
// 折叠的样板代码（点击标题栏展开）
const config = await loadBoilerplate();
setup(config);

// 正文始终可见
console.log("Hello, blog!");
```

## 表格

| 语法 | 用途 | 示例 |
| ---- | ---- | ---- |
| `**text**` | 加粗 | **text** |
| `` `code` `` | 行内代码 | `code` |
| `> text` | 引用 | 见上文 |
| `$x^2$` | 行内公式 | $x^2$ |

## 数学公式

KaTeX 支持行内公式 $E = mc^2$ 和独立公式块：

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

## 提示块

:::note
`note`：普通补充说明。
:::

:::tip
`tip`：小技巧，读者可以跳过但看了会更好。
:::

:::caution
`caution`：需要特别注意的地方，比如破坏性操作。
:::

## GitHub 仓库卡片

::github{repo="saicaca/fuwari"}

直接在文章里内嵌仓库卡片，写技术文时很方便。

## 图片与封面

在 frontmatter 中加一行 `image: ./cover.jpg`（把图片放在文章同目录）即可作为文章封面。图片点击后支持灯箱放大预览。
