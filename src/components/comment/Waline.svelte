<script lang="ts">
	import { onMount } from "svelte";
	import { init } from "@waline/client";
	import "@waline/client/waline.css";

	let {
		serverURL,
		path = undefined,
	}: {
		serverURL: string;
		path?: string | undefined;
	} = $props();

	let container: HTMLDivElement;

	onMount(() => {
		const waline = init({
			el: container,
			serverURL,
			path,
			lang: "zh-CN",
			// 跟随站点暗色模式：Fuwari 在 html 上切换 dark class
			dark: "html.dark",
			emoji: [
				"//unpkg.com/@waline/emojis@1.2.0/weibo",
				"//unpkg.com/@waline/emojis@1.2.0/bilibili",
			],
			search: "BiliBili", // 评论框内置表情包/梗图搜索，弥补图片上传
			metaInfo: ["nick", "mail", "link"],
		});
		return () => {
			waline?.destroy();
		};
	});
</script>

<div bind:this={container} class="waline-container min-h-40"></div>

<style>
	.waline-container :global(.wl-panel) {
		border-radius: 0.75rem;
	}
</style>
