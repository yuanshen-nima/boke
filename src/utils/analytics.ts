// 构建时从 Cloudflare Web Analytics（RUM）取热门页面，供侧栏“热门文章”榜使用。
// 需要三个环境变量（在 Cloudflare Pages 构建环境或本地 .env 中设置）：
//   CF_WEBANALYTICS_ACCOUNT_ID - Cloudflare 账户 ID（仪表板右侧栏）
//   CF_WEBANALYTICS_TOKEN      - API Token（权限：Account / Web Analytics / Read）
//   CF_WEBANALYTICS_SITE_TAG   - Web Analytics 站点标签（统计代码 URL 里的 siteTag 参数）
// 任一缺失或查询失败时返回空数组，热门榜整体不渲染，不影响构建。

export interface HotPage {
	path: string;
	views: number;
}

export async function fetchTopPages(days = 30, limit = 10): Promise<HotPage[]> {
	const accountId = import.meta.env.CF_WEBANALYTICS_ACCOUNT_ID;
	const token = import.meta.env.CF_WEBANALYTICS_TOKEN;
	const siteTag = import.meta.env.CF_WEBANALYTICS_SITE_TAG;
	if (!accountId || !token || !siteTag) {
		return [];
	}

	const since = new Date(Date.now() - days * 86_400_000).toISOString();
	const query = `query($accountTag: String!, $siteTag: String!, $since: Time!) {
		viewer {
			accounts(filter: { accountTag: $accountTag }) {
				rumAdaptiveGroups(
					limit: ${limit}
					filter: { siteTag: $siteTag, datetime_geq: $since }
					orderBy: [sum_pageViews_DESC]
				) {
					sum { pageViews }
					dimensions { sitePath }
				}
			}
		}
	}`;

	try {
		const resp = await fetch("https://api.cloudflare.com/client/v4/graphql", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${token}`,
			},
			body: JSON.stringify({
				query,
				variables: { accountTag: accountId, siteTag, since },
			}),
		});
		const data = await resp.json();
		if (data.errors?.length) {
			console.warn(
				"[hot-posts] Web Analytics 查询失败:",
				JSON.stringify(data.errors),
			);
			return [];
		}
		const groups =
			data?.data?.viewer?.accounts?.[0]?.rumAdaptiveGroups ?? [];
		return groups.map((g: any) => ({
			path: g.dimensions.sitePath as string,
			views: g.sum.pageViews as number,
		}));
	} catch (err) {
		console.warn("[hot-posts] Web Analytics 请求失败:", err);
		return [];
	}
}
