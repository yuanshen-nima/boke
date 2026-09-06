<script lang="ts">
	import { onMount } from "svelte";

	let {
		repo,
		repoId,
		category,
		categoryId,
		mapping = "pathname",
	}: {
		repo: string;
		repoId: string;
		category: string;
		categoryId: string;
		mapping?: string;
	} = $props();

	let container: HTMLDivElement;

	// Giscus 的主题跟随站点：html 上的 dark class 由 Fuwari 的主题切换逻辑维护
	function currentGiscusTheme(): string {
		return document.documentElement.classList.contains("dark")
			? "dark"
			: "light";
	}

	onMount(() => {
		const script = document.createElement("script");
		script.src = "https://giscus.app/client.js";
		script.setAttribute("data-repo", repo);
		script.setAttribute("data-repo-id", repoId);
		script.setAttribute("data-category", category);
		script.setAttribute("data-category-id", categoryId);
		script.setAttribute("data-mapping", mapping);
		script.setAttribute("data-strict", "0");
		script.setAttribute("data-reactions-enabled", "1");
		script.setAttribute("data-emit-metadata", "0");
		script.setAttribute("data-input-position", "top");
		script.setAttribute("data-theme", currentGiscusTheme());
		script.setAttribute("data-lang", "zh-CN");
		script.setAttribute("crossorigin", "anonymous");
		script.async = true;
		container.appendChild(script);

		const observer = new MutationObserver(() => {
			const iframe = container.querySelector<HTMLIFrameElement>(
				"iframe.giscus-frame",
			);
			iframe?.contentWindow?.postMessage(
				{ giscus: { setConfig: { theme: currentGiscusTheme() } } },
				"https://giscus.app",
			);
		});
		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["class"],
		});

		return () => {
			observer.disconnect();
			script.remove();
			container.innerHTML = "";
		};
	});
</script>

<div bind:this={container} class="min-h-40"></div>
