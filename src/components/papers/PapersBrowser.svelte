<script lang="ts">
	// 论文知识库筛选组件：搜索 / 年份 / 场所 / 主题 过滤 + 排序（Svelte 5 runes）
	type PaperItem = {
		slug: string;
		title: string;
		description: string;
		year?: number;
		venue?: string;
		doi?: string;
		arxiv?: string;
		paperUrl?: string;
		githubUrl?: string;
		topics: string[];
		tags: string[];
		updated?: string;
	};

	let { papers }: { papers: PaperItem[] } = $props();

	let query = $state("");
	let yearFilter = $state("");
	let venueFilter = $state("");
	let topicFilter = $state("");
	let sortBy = $state("year-desc");
	let showAll = $state(false);
	const PAGE = 20;

	const years = $derived(
		[...new Set(papers.map((p) => p.year).filter((y): y is number => !!y))].sort((a, b) => b - a),
	);
	const venues = $derived(
		[...new Set(papers.map((p) => p.venue).filter((v): v is string => !!v))].sort((a, b) =>
			a.localeCompare(b),
		),
	);
	const topics = $derived([...new Set(papers.flatMap((p) => p.topics))].sort());

	const filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		let list = papers.filter((p) => {
			if (yearFilter && String(p.year ?? "") !== yearFilter) return false;
			if (venueFilter && p.venue !== venueFilter) return false;
			if (topicFilter && !p.topics.includes(topicFilter)) return false;
			if (q) {
				const hay = [p.title, p.description, p.venue, ...(p.topics ?? []), ...(p.tags ?? [])]
					.join(" ")
					.toLowerCase();
				if (!hay.includes(q)) return false;
			}
			return true;
		});
		list = [...list].sort((a, b) => {
			if (sortBy === "year-asc") return (a.year ?? 0) - (b.year ?? 0);
			if (sortBy === "updated-desc") return (b.updated ?? "").localeCompare(a.updated ?? "");
			if (sortBy === "title-asc") return a.title.localeCompare(b.title);
			return (b.year ?? 0) - (a.year ?? 0);
		});
		return list;
	});
	const visible = $derived(showAll ? filtered : filtered.slice(0, PAGE));
</script>

<div class="flex flex-col gap-3">
	<div class="flex flex-wrap gap-2 items-center">
		<input
			type="search"
			placeholder="搜索标题 / 摘要 / 标签…"
			bind:value={query}
			class="transition rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm
			       outline-none focus:ring-2 ring-[var(--primary)] min-w-56 flex-1"
		/>
		<select bind:value={yearFilter}
			class="transition rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none focus:ring-2 ring-[var(--primary)]">
			<option value="">全部年份</option>
			{#each years as y}<option value={String(y)}>{y}</option>{/each}
		</select>
		<select bind:value={venueFilter}
			class="transition rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none focus:ring-2 ring-[var(--primary)] max-w-44">
			<option value="">全部场所</option>
			{#each venues as v}<option value={v}>{v}</option>{/each}
		</select>
		<select bind:value={topicFilter}
			class="transition rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none focus:ring-2 ring-[var(--primary)] max-w-44">
			<option value="">全部主题</option>
			{#each topics as t}<option value={t}>{t}</option>{/each}
		</select>
		<select bind:value={sortBy}
			class="transition rounded-lg bg-black/5 dark:bg-white/10 px-3 py-2 text-sm outline-none focus:ring-2 ring-[var(--primary)]">
			<option value="year-desc">年份 新→旧</option>
			<option value="year-asc">年份 旧→新</option>
			<option value="updated-desc">最近更新</option>
			<option value="title-asc">标题排序</option>
		</select>
	</div>

	<div class="text-sm text-black/40 dark:text-white/40">
		共 {papers.length} 篇 · 当前显示 {filtered.length} 篇
	</div>

	{#if filtered.length === 0}
		<div class="text-center py-10 text-black/40 dark:text-white/40">没有匹配的论文</div>
	{:else}
		<div class="flex flex-col">
			{#each visible as p (p.slug)}
				<a
					href={`/papers/${p.slug}/`}
					class="group flex flex-col gap-1 py-3 px-3 -mx-3 rounded-lg border-b-[1px] border-dashed
					       border-[var(--line-divider)] last:border-0 transition
					       hover:bg-black/[0.03] dark:hover:bg-white/[0.03]"
				>
					<div class="flex items-baseline justify-between gap-3">
						<span
							class="font-bold text-black/85 dark:text-white/85 transition
							       group-hover:text-[var(--primary)]"
						>
							{p.title}
						</span>
						<span class="text-sm text-black/35 dark:text-white/35 whitespace-nowrap shrink-0">
							{p.year ?? ""}{p.venue ? ` · ${p.venue}` : ""}
						</span>
					</div>
					{#if p.description}
						<span class="text-sm text-black/50 dark:text-white/50 line-clamp-2">{p.description}</span>
					{/if}
					<div class="flex flex-wrap gap-1.5">
						{#each p.topics as t}
							<span
								class="text-xs rounded-md bg-[var(--primary)]/10 text-[var(--primary)] px-1.5 py-0.5"
							>
								{t}
							</span>
						{/each}
						{#each (p.tags ?? []).slice(0, 4) as t}
							<span class="text-xs rounded-md bg-black/5 dark:bg-white/10 px-1.5 py-0.5
							             text-black/50 dark:text-white/50">
								{t}
							</span>
						{/each}
					</div>
				</a>
			{/each}
		</div>
		{#if filtered.length > PAGE && !showAll}
			<button
				class="btn-card mx-auto mt-2"
				onclick={() => (showAll = true)}
			>
				显示全部 {filtered.length} 篇
			</button>
		{/if}
	{/if}
</div>
