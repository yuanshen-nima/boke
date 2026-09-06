import type {
	ExpressiveCodeConfig,
	LicenseConfig,
	NavBarConfig,
	ProfileConfig,
	SiteConfig,
} from "./types/config";
import { LinkPreset } from "./types/config";

export const siteConfig: SiteConfig = {
	title: "我的技术博客",
	subtitle: "记录 · 思考 · 分享",
	lang: "zh_CN", // Language code, e.g. 'en', 'zh_CN', 'ja', etc.
	themeColor: {
		hue: 250, // Default hue for the theme color, from 0 to 360. e.g. red: 0, teal: 200, cyan: 250, pink: 345
		fixed: false, // Hide the theme color picker for visitors
	},
	banner: {
		enable: false,
		src: "assets/images/demo-banner.png", // Relative to the /src directory. Relative to the /public directory if it starts with '/'
		position: "center", // Equivalent to object-position, only supports 'top', 'center', 'bottom'. 'center' by default
		credit: {
			enable: false, // Display the credit text of the banner image
			text: "", // Credit text to be displayed
			url: "", // (Optional) URL link to the original artwork or artist's page
		},
	},
	toc: {
		enable: true, // Display the table of contents on the right side of the post
		depth: 2, // Maximum heading depth to show in the table, from 1 to 3
	},
	favicon: [
		// Leave this array empty to use the default favicon
		// {
		//   src: '/favicon/icon.png',    // Path of the favicon, relative to the /public directory
		//   theme: 'light',              // (Optional) Either 'light' or 'dark', set only if you have different favicons for light and dark mode
		//   sizes: '32x32',              // (Optional) Size of the favicon, set only if you have favicons of different sizes
		// }
	],
};

export const navBarConfig: NavBarConfig = {
	links: [
		LinkPreset.Home,
		LinkPreset.Archive,
		LinkPreset.About,
		{
			name: "GitHub",
			url: "https://github.com/yourname", // TODO: 改成你的 GitHub 主页或仓库地址
			external: true, // Show an external link icon and will open in a new tab
		},
	],
};

export const profileConfig: ProfileConfig = {
	avatar: "assets/images/demo-avatar.png", // TODO: 替换为你的头像，放到 src/assets/images/ 下
	name: "博主", // TODO: 改成你的名字/昵称
	bio: "欢迎来到我的小站，这里记录我的学习笔记与思考。",
	links: [
		{
			name: "GitHub",
			icon: "fa6-brands:github",
			url: "https://github.com/yourname", // TODO: 改成你的 GitHub 主页
		},
		{
			name: "Email",
			icon: "fa6-regular:envelope",
			url: "mailto:your@email.com", // TODO: 改成你的邮箱
		},
	],
};

export const licenseConfig: LicenseConfig = {
	enable: true,
	name: "CC BY-NC-SA 4.0",
	url: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
};

// Giscus 评论配置：到 https://giscus.app/zh-CN 生成参数后填入，并打开 enable
// 前置条件：GitHub 仓库为公开仓库，并在仓库 Settings -> General -> Features 中开启 Discussions
export const giscusConfig = {
	enable: false, // 配置完成后改为 true 即可在文章底部显示评论
	repo: "yourname/your-repo", // 例如 "octocat/my-blog"
	repoId: "", // giscus.app 生成
	category: "Announcements", // giscus.app 生成，一般选 Announcements 或 General
	categoryId: "", // giscus.app 生成
	mapping: "pathname",
};

export const expressiveCodeConfig: ExpressiveCodeConfig = {
	// Note: Some styles (such as background color) are being overridden, see the astro.config.mjs file.
	// Please select a dark theme, as this blog theme currently only supports dark background color
	theme: "github-dark",
};
